from datetime import datetime, timezone
import json
import re
from typing import Optional, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent_session
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.discussion import Discussion, DiscussionComment
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.authorization_service import AuthorizationService

router = APIRouter(
    prefix="/v1/repositories/{owner_name}/{repo_name}/discussions",
    tags=["discussions"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class DiscussionCreateRequest(BaseModel):
    title: str = Field(..., max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="General", max_length=64)
    task_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    author_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class DiscussionCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    task_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    author_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class DiscussionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    author_id: str
    author_name: str = "Author"
    author_type: str = "human"
    title: str
    body: str
    category: str
    task_id: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    github_url: str | None = None
    created_at: datetime
    updated_at: datetime


class DiscussionCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    discussion_id: str
    author_id: str
    author_name: str = "Author"
    author_type: str = "human"
    body: str
    task_id: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    created_at: datetime
    updated_at: datetime


def get_discussion_principal(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> tuple[str, Union[User, Agent], Optional[AgentSession]]:
    """
    Authenticate either:
      - a human User via standard JWT Bearer token
      - an active AgentSession via `sutra_session_...` token
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token.strip()

    # Agent Session
    if token.startswith("sutra_session_"):
        session = get_current_agent_session(authorization=authorization, db=db)
        agent = db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Agent is inactive or revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return "agent", agent, session

    # Human User JWT
    credentials = HTTPAuthorizationCredentials(scheme=scheme, credentials=token)
    user = get_current_user(credentials=credentials, db=db)
    return "user", user, None


def _get_repository(owner_name: str, repo_name: str, db: Session) -> Repository:
    repo = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            Actor.name == owner_name,
            Repository.name == repo_name,
            Repository.deleted_at.is_(None),
        )
    )
    if not repo:
        repo = db.scalar(
            select(Repository)
            .join(Actor, Actor.id == Repository.owner_id)
            .where(
                Actor.name == owner_name,
                Repository.slug == repo_name.lower(),
                Repository.deleted_at.is_(None),
            )
        )

    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


def _authorize_discussion_access(
    principal_type: str,
    principal: Union[User, Agent],
    repo: Repository,
    action: str,
    db: Session,
) -> None:
    if principal_type == "user":
        if repo.owner_id != principal.id:
            if action == "read" and repo.visibility == "public":
                return
            if repo.visibility == "private":
                raise HTTPException(status_code=404, detail="Repository not found")
            raise HTTPException(status_code=403, detail="Forbidden")
        return

    # Agent path
    agent = principal
    if not agent.is_active or agent.status != "active":
        raise HTTPException(status_code=401, detail="Agent is inactive or revoked")

    from app.models.agent_repository_access import AgentRepositoryAccess
    access = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.agent_id == agent.id,
            AgentRepositoryAccess.repository_id == repo.id,
            AgentRepositoryAccess.enabled.is_(True),
        )
    )

    if repo.visibility == "private" and not access and repo.owner_id != agent.owner_id:
        raise HTTPException(status_code=404, detail="Repository not found")


def _get_or_create_actor(entity_id: str, entity_name: str, entity_type: str, db: Session) -> Actor:
    actor = db.get(Actor, entity_id)
    if not actor:
        actor = Actor(
            id=entity_id,
            owner_id=entity_id,
            type=entity_type,
            name=entity_name,
            capabilities=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "discussion.read",
                "discussion.create",
                "discussion.comment",
            ]),
        )
        db.add(actor)
        db.flush()
    return actor


def _format_discussion(d: Discussion, db: Session, repo: Repository) -> DiscussionResponse:
    actor = db.get(Actor, d.author_id)
    author_name = actor.name if actor else "Unknown"
    author_type = actor.type if actor else "human"

    task_id = None
    session_id = None
    agent_id = None

    if author_type == "agent":
        agent_id = d.author_id

    if "[SUTRA Agent:" in d.body:
        agent_match = re.search(r"\[SUTRA Agent:\s*([^\]]+)\]", d.body)
        if agent_match:
            author_type = "agent"
            author_name = agent_match.group(1).strip()
        tid_match = re.search(r"Task ID:\s*([a-f0-9\-]+)", d.body)
        if tid_match and tid_match.group(1).lower() != "none":
            task_id = tid_match.group(1).strip()
        sid_match = re.search(r"Session ID:\s*([a-f0-9\-]+)", d.body)
        if sid_match and sid_match.group(1).lower() != "none":
            session_id = sid_match.group(1).strip()
        aid_match = re.search(r"Agent ID:\s*([a-f0-9\-]+)", d.body)
        if aid_match and aid_match.group(1).lower() != "none":
            agent_id = aid_match.group(1).strip()

    owner_actor = db.get(Actor, repo.owner_id)
    owner_name = owner_actor.name if owner_actor else "repository"
    github_url = f"https://github.com/{owner_name}/{repo.name}/discussions"

    return DiscussionResponse(
        id=d.id,
        repository_id=d.repository_id,
        author_id=d.author_id,
        author_name=author_name,
        author_type=author_type,
        title=d.title,
        body=d.body,
        category=d.category,
        task_id=task_id,
        session_id=session_id,
        agent_id=agent_id,
        github_url=github_url,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


def _format_comment(c: DiscussionComment, db: Session) -> DiscussionCommentResponse:
    actor = db.get(Actor, c.author_id)
    author_name = actor.name if actor else "Unknown"
    author_type = actor.type if actor else "human"

    task_id = None
    session_id = None
    agent_id = None

    if author_type == "agent":
        agent_id = c.author_id

    if "[SUTRA Agent:" in c.body:
        agent_match = re.search(r"\[SUTRA Agent:\s*([^\]]+)\]", c.body)
        if agent_match:
            author_type = "agent"
            author_name = agent_match.group(1).strip()
        tid_match = re.search(r"Task ID:\s*([a-f0-9\-]+)", c.body)
        if tid_match and tid_match.group(1).lower() != "none":
            task_id = tid_match.group(1).strip()
        sid_match = re.search(r"Session ID:\s*([a-f0-9\-]+)", c.body)
        if sid_match and sid_match.group(1).lower() != "none":
            session_id = sid_match.group(1).strip()
        aid_match = re.search(r"Agent ID:\s*([a-f0-9\-]+)", c.body)
        if aid_match and aid_match.group(1).lower() != "none":
            agent_id = aid_match.group(1).strip()

    return DiscussionCommentResponse(
        id=c.id,
        discussion_id=c.discussion_id,
        author_id=c.author_id,
        author_name=author_name,
        author_type=author_type,
        body=c.body,
        task_id=task_id,
        session_id=session_id,
        agent_id=agent_id,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post(
    "",
    response_model=DiscussionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion(
    owner_name: str,
    repo_name: str,
    payload: DiscussionCreateRequest,
    principal_data=Depends(get_discussion_principal),
    db: Session = Depends(get_db),
):
    principal_type, principal, session = principal_data
    repo = _get_repository(owner_name, repo_name, db)
    _authorize_discussion_access(principal_type, principal, repo, "write", db)

    body = payload.body
    author_id = principal.id

    if principal_type == "agent":
        _get_or_create_actor(principal.id, principal.name, "agent", db)
        task_info = f"Task ID: {payload.task_id}" if payload.task_id else "Task ID: None"
        header = f"[SUTRA Agent: {principal.name}]\nAgent ID: {principal.id}\nSession ID: {session.id}\n{task_info}\n\n"
        body = header + body
    else:
        _get_or_create_actor(principal.id, principal.username, "human", db)

    if payload.task_id:
        task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.repository_id == repo.id))
        if not task:
            raise HTTPException(status_code=404, detail="Linked task not found in this repository")
        if principal_type == "agent" and task.assigned_agent_id != principal.id:
            raise HTTPException(status_code=403, detail="Agent is not assigned to this task")

    discussion = Discussion(
        repository_id=repo.id,
        author_id=author_id,
        title=payload.title,
        body=body,
        category=payload.category,
    )
    db.add(discussion)
    db.commit()
    db.refresh(discussion)

    try:
        from app.services import knowledge_graph_service
        knowledge_graph_service.index_engineering_lifecycle(db, repo)
        db.commit()
    except Exception:
        pass

    return _format_discussion(discussion, db, repo)


@router.get(
    "",
    response_model=list[DiscussionResponse],
)
def list_discussions(
    owner_name: str,
    repo_name: str,
    category: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal_data=Depends(get_discussion_principal),
    db: Session = Depends(get_db),
):
    principal_type, principal, _ = principal_data
    repo = _get_repository(owner_name, repo_name, db)
    _authorize_discussion_access(principal_type, principal, repo, "read", db)

    stmt = select(Discussion).where(Discussion.repository_id == repo.id)
    if category and category != "View all discussions":
        stmt = stmt.where(Discussion.category == category)

    stmt = stmt.order_by(Discussion.created_at.desc()).limit(limit).offset(offset)
    discussions = db.scalars(stmt).all()

    return [_format_discussion(d, db, repo) for d in discussions]


@router.get(
    "/{discussion_id}",
    response_model=DiscussionResponse,
)
def get_discussion(
    owner_name: str,
    repo_name: str,
    discussion_id: str,
    principal_data=Depends(get_discussion_principal),
    db: Session = Depends(get_db),
):
    principal_type, principal, _ = principal_data
    repo = _get_repository(owner_name, repo_name, db)
    _authorize_discussion_access(principal_type, principal, repo, "read", db)

    discussion = db.scalar(
        select(Discussion).where(
            Discussion.id == discussion_id,
            Discussion.repository_id == repo.id,
        )
    )
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    return _format_discussion(discussion, db, repo)


@router.post(
    "/{discussion_id}/comments",
    response_model=DiscussionCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion_comment(
    owner_name: str,
    repo_name: str,
    discussion_id: str,
    payload: DiscussionCommentCreateRequest,
    principal_data=Depends(get_discussion_principal),
    db: Session = Depends(get_db),
):
    principal_type, principal, session = principal_data
    repo = _get_repository(owner_name, repo_name, db)
    _authorize_discussion_access(principal_type, principal, repo, "write", db)

    discussion = db.scalar(
        select(Discussion).where(
            Discussion.id == discussion_id,
            Discussion.repository_id == repo.id,
        )
    )
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    body = payload.body
    author_id = principal.id

    if payload.task_id:
        task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.repository_id == repo.id))
        if not task:
            raise HTTPException(status_code=404, detail="Linked task not found in this repository")
        if principal_type == "agent" and task.assigned_agent_id != principal.id:
            raise HTTPException(status_code=403, detail="Agent is not assigned to this task")

    if principal_type == "agent":
        _get_or_create_actor(principal.id, principal.name, "agent", db)
        task_info = f"Task ID: {payload.task_id}" if payload.task_id else "Task ID: None"
        header = f"[SUTRA Agent: {principal.name}]\nAgent ID: {principal.id}\nSession ID: {session.id}\n{task_info}\n\n"
        body = header + body
    else:
        _get_or_create_actor(principal.id, principal.username, "human", db)

    comment = DiscussionComment(
        discussion_id=discussion.id,
        author_id=author_id,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return _format_comment(comment, db)


@router.get(
    "/{discussion_id}/comments",
    response_model=list[DiscussionCommentResponse],
)
def get_discussion_comments(
    owner_name: str,
    repo_name: str,
    discussion_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal_data=Depends(get_discussion_principal),
    db: Session = Depends(get_db),
):
    principal_type, principal, _ = principal_data
    repo = _get_repository(owner_name, repo_name, db)
    _authorize_discussion_access(principal_type, principal, repo, "read", db)

    discussion = db.scalar(
        select(Discussion).where(
            Discussion.id == discussion_id,
            Discussion.repository_id == repo.id,
        )
    )
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    stmt = (
        select(DiscussionComment)
        .where(DiscussionComment.discussion_id == discussion.id)
        .order_by(DiscussionComment.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    comments = db.scalars(stmt).all()

    return [_format_comment(c, db) for c in comments]

