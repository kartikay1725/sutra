from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent, get_current_agent_session
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_file import ChangeFile
from app.models.repository import Repository
from app.models.user import User
from app.core.config import settings
from app.services.authorization_service import AuthorizationService
from app.services.change_service import ChangeService


router = APIRouter(
    prefix="/v1/changes",
    tags=["changes"],
)


class CreateChangeRequest(BaseModel):
    repository_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    )

    intent: str = Field(
        min_length=1,
        max_length=5000,
    )

    base_commit: str | None = Field(
        default=None,
        min_length=7,
        max_length=64,
        pattern=r"^[0-9a-f]{7,64}$",
    )

    risk_level: str = Field(
        default="unknown",
        pattern=r"^(unknown|low|medium|high|critical)$",
    )

    task_id: str | None = None
    branch: str | None = None
    base_branch: str | None = None


class AttachCommitRequest(BaseModel):
    resulting_commit: str = Field(
        min_length=7,
        max_length=64,
        pattern=r"^[0-9a-f]{7,64}$",
    )


class CommitProvenanceResponse(BaseModel):
    source: str = "sutra"
    tracked: bool = True
    identity_type: str = "human"
    actor_id: str | None = None
    actor_name: str | None = None
    agent: dict | None = None
    session: dict | None = None
    task: dict | None = None


class CommitDetailResponse(BaseModel):
    sha: str
    message: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    committed_at: str | None = None
    provenance: CommitProvenanceResponse | None = None


class ChangeResponse(BaseModel):
    id: str
    repository_id: str
    repository_name: str | None = None
    actor_id: str
    actor_type: str
    actor_name: str
    intent: str
    title: str | None = None
    description: str | None = None
    base_commit: str | None
    resulting_commit: str | None
    status: str
    risk_level: str | None = "unknown"
    branch: str | None = None
    base_branch: str | None = None
    task_id: str | None = None
    task_title: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    agent_session_id: str | None = None
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    commits: list[CommitDetailResponse] = []
    checks: list[dict] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pull_request_id: str | None = None
    pull_request_title: str | None = None
    pull_request_status: str | None = None


class ChangeEventResponse(BaseModel):
    id: str
    change_id: str
    actor_id: str | None
    event_type: str
    from_status: str | None
    to_status: str | None
    reason: str | None
    metadata_json: str
    created_at: datetime


class ChangeFileResponse(BaseModel):
    path: str
    filename: str | None = None
    status: str | None = None
    operation: str
    additions: int = 0
    deletions: int = 0
    patch: str | None = None


def _to_change_response(change: Change, actor: Actor | None, db: Session) -> ChangeResponse:
    import json
    from app.models.pull_request import PullRequest
    from app.models.task import Task
    from app.models.agent import Agent
    from app.services.code_provenance_service import CodeProvenanceService

    files = db.scalars(
        select(ChangeFile).where(ChangeFile.change_id == change.id)
    ).all()
    pr = db.scalar(
        select(PullRequest).where(PullRequest.source_change_id == change.id)
    )
    repo = db.scalar(
        select(Repository).where(Repository.id == change.repository_id)
    )

    # If change has commits but no ChangeFiles stored yet, synchronize from provider
    if not files and repo and change.base_commit and change.resulting_commit:
        from app.services.pull_request_service import PullRequestService
        files = PullRequestService(db).sync_change_files_from_provider(repo, change)

    meta = {}
    if change.metadata_json:
        try:
            meta = json.loads(change.metadata_json)
        except Exception:
            meta = {}

    # Resolve task linkage
    task = None
    if meta.get("task_id"):
        task = db.scalar(select(Task).where(Task.id == meta["task_id"]))
    if not task:
        task = db.scalar(
            select(Task).where(
                Task.repository_id == change.repository_id,
                Task.resulting_change_id == change.id,
            )
        )
    if not task:
        task = db.scalar(
            select(Task).where(Task.resulting_change_id == change.id)
        )

    # Actor details
    if not actor:
        actor = db.scalar(select(Actor).where(Actor.id == change.actor_id))

    actor_id = actor.id if actor else change.actor_id
    actor_type = actor.type if actor else "human"
    actor_name = actor.name if actor else (meta.get("agent_name") or actor_id)

    # Agent details
    agent_id = meta.get("agent_id")
    agent_name = meta.get("agent_name")
    agent_session_id = meta.get("agent_session_id")

    if task:
        if not agent_id and task.assigned_agent_id:
            agent_id = task.assigned_agent_id
        if not agent_session_id and task.claimed_by_session_id:
            agent_session_id = task.claimed_by_session_id

    if agent_id and not agent_name:
        agent_obj = db.scalar(select(Agent).where(Agent.id == agent_id))
        if agent_obj:
            agent_name = agent_obj.name

    if actor_type == "agent" and not agent_name:
        agent_name = actor_name

    # Branch details
    branch = meta.get("branch") or (pr.source_branch if pr else None)
    base_branch = (
        meta.get("base_branch")
        or (pr.target_branch if pr else None)
        or (getattr(repo, "default_branch", None) if repo else "main")
    )

    # Title & description
    title = meta.get("title") or (change.intent.splitlines()[0] if change.intent else f"Change {change.id[:8]}")
    description = meta.get("description") or change.intent

    # Commits with authoritative SUTRA/GitHub provenance
    commits: list[CommitDetailResponse] = []
    if change.resulting_commit:
        prov = CodeProvenanceService(db).resolve_commit(
            repository_id=change.repository_id,
            commit_sha=change.resulting_commit,
        )
        provenance_resp = CommitProvenanceResponse(
            source=prov.get("source", "sutra"),
            tracked=prov.get("tracked", True),
            identity_type=prov.get("identity_type", "unknown"),
            actor_id=prov.get("actor_id"),
            actor_name=prov.get("actor_name"),
            agent=prov.get("agent"),
            session=prov.get("session"),
            task=prov.get("task"),
        )
        commits.append(
            CommitDetailResponse(
                sha=change.resulting_commit,
                message=change.intent,
                author_name=actor_name,
                committed_at=change.updated_at.isoformat() if change.updated_at else None,
                provenance=provenance_resp,
            )
        )

    return ChangeResponse(
        id=change.id,
        repository_id=change.repository_id,
        repository_name=repo.name if repo else None,
        actor_id=actor_id,
        actor_type=actor_type,
        actor_name=actor_name,
        intent=change.intent,
        title=title,
        description=description,
        base_commit=change.base_commit,
        resulting_commit=change.resulting_commit,
        status=change.status,
        risk_level=change.risk_level or "unknown",
        branch=branch,
        base_branch=base_branch,
        task_id=task.id if task else None,
        task_title=task.title if task else None,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_session_id=agent_session_id,
        files_changed=len(files),
        additions=sum(f.additions for f in files),
        deletions=sum(f.deletions for f in files),
        commits=commits,
        checks=[],
        created_at=change.created_at,
        updated_at=change.updated_at,
        pull_request_id=pr.id if pr else None,
        pull_request_title=pr.title if pr else None,
        pull_request_status=pr.status if pr else None,
    )


# ---------------------------------------------------------------------------
# LIST CHANGES
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[ChangeResponse],
)
def list_changes(
    owner: str | None = None,
    repo: str | None = None,
    actor_type: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
    agent_id: str | None = None,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if owner and repo:
        repository = db.scalar(
            select(Repository)
            .join(Actor, Actor.id == Repository.owner_id)
            .where(
                Actor.name == owner,
                (Repository.slug == repo.lower()) | (Repository.name == repo),
                Repository.deleted_at.is_(None)
            )
        )
        if not repository:
            # Fallback by slug/name/id directly
            repository = db.scalar(
                select(Repository).where(
                    (Repository.slug == repo.lower()) | (Repository.name == repo) | (Repository.id == repo),
                    Repository.deleted_at.is_(None)
                )
            )
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Enforce private repository IDOR protection
        if repository.visibility == "private" and repository.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Repository not found")

        stmt = (
            select(Change, Actor)
            .join(Actor, Actor.id == Change.actor_id, isouter=True)
            .join(Repository, Repository.id == Change.repository_id)
            .where(Change.repository_id == repository.id)
        )
    else:
        # Scope global change listing to repositories owned by or visible to current_user
        stmt = (
            select(Change, Actor)
            .join(Actor, Actor.id == Change.actor_id, isouter=True)
            .join(Repository, Repository.id == Change.repository_id)
            .where(
                (Repository.owner_id == current_user.id) | (Repository.visibility == "public"),
                Repository.deleted_at.is_(None),
            )
        )

    # Optional query filters
    if status and status != "all":
        stmt = stmt.where(Change.status == status)

    if risk_level and risk_level != "all":
        stmt = stmt.where(Change.risk_level == risk_level)

    if actor_type and actor_type != "all":
        if actor_type == "agent":
            stmt = stmt.where(
                (Actor.type == "agent") | 
                (Change.metadata_json.like('%"agent_id"%'))
            )
        elif actor_type in ("human", "user"):
            stmt = stmt.where(
                (Actor.type != "agent") & 
                (~Change.metadata_json.like('%"agent_id"%'))
            )

    if agent_id:
        stmt = stmt.where(
            (Change.actor_id == agent_id) | 
            (Change.metadata_json.like(f'%"agent_id": "{agent_id}"%'))
        )

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            Change.intent.ilike(term) | 
            Actor.name.ilike(term) | 
            Repository.name.ilike(term) |
            Change.metadata_json.ilike(term)
        )

    results = db.execute(stmt.order_by(Change.updated_at.desc())).all()

    responses = []
    for change, actor in results:
        responses.append(_to_change_response(change, actor, db))
    return responses


# ---------------------------------------------------------------------------
# HUMAN CHANGE CREATION
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ChangeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_change(
    payload: CreateChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = db.scalar(
        select(Repository).where(
            Repository.id == payload.repository_id,
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    if repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this repository",
        )

    actor = db.scalar(
        select(Actor).where(
            Actor.owner_id == current_user.id,
            Actor.type == "human",
            Actor.name == current_user.username,
        )
    )

    if actor is None:
        actor = Actor(
            type="human",
            name=current_user.username,
            owner_id=current_user.id,
            capabilities=(
                '["repository.read",'
                '"repository.write",'
                '"change.create"]'
            ),
        )

        db.add(actor)
        db.flush()

    change = Change(
        repository_id=repository.id,
        actor_id=actor.id,
        intent=payload.intent,
        base_commit=payload.base_commit,
        status="proposed",
        risk_level=payload.risk_level,
        metadata_json="{}",
    )

    db.add(change)
    db.flush()

    ChangeService(db).transition_change(
        change=change,
        new_status="proposed",
        actor_id=actor.id,
        event_type="change.created",
        reason="Change created manually.",
        metadata={
            "intent": payload.intent,
            "risk_level": payload.risk_level,
        },
    )

    db.commit()
    db.refresh(change)

    return _to_change_response(change, actor, db)


# ---------------------------------------------------------------------------
# HUMAN COMMIT ATTACHMENT
# ---------------------------------------------------------------------------


@router.post(
    "/{change_id}/commit",
    response_model=ChangeResponse,
)
def attach_commit(
    change_id: str,
    payload: AttachCommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(Change, Actor, Repository)
        .join(
            Actor,
            Actor.id == Change.actor_id,
        )
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    change, actor, repository = result

    try:
        ChangeService(db).record_commit(
            change=change,
            repository=repository,
            actor=actor,
            resulting_commit=payload.resulting_commit,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _to_change_response(change, actor, db)


# ---------------------------------------------------------------------------
# AGENT COMMIT ATTACHMENT
#
# Agent-specific capability boundary:
#     change.commit
#
# The agent must:
#     1. Be authenticated.
#     2. Be active.
#     3. Own the repository.
#     4. Own the change.
#     5. Have the change.commit capability.
# ---------------------------------------------------------------------------


@router.post(
    "/{change_id}/agent-commit",
    response_model=ChangeResponse,
    summary="Record Agent Commit Evidence",
    description="Agent declares the resulting commit for a change. Requires AgentSession and `change.commit` capability. Does NOT approve or finalize the change.",
)
def attach_agent_commit(
    change_id: str,
    payload: AttachCommitRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(Change, Actor, Repository)
        .join(
            Actor,
            Actor.id == Change.actor_id,
        )
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Change.actor_id == current_agent.id,
            Actor.id == current_agent.id,
            Actor.type == "agent",
            Repository.owner_id == current_agent.owner_id,
            Repository.deleted_at.is_(None),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent change not found",
        )

    change, actor, repository = result

    if not current_agent.is_active or current_agent.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is inactive",
        )

    try:
        AuthorizationService.require(
            actor=actor,
            repository=repository,
            capability=AuthorizationService.CHANGE_COMMIT,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        ChangeService(db).record_commit(
            change=change,
            repository=repository,
            actor=actor,
            resulting_commit=payload.resulting_commit,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _to_change_response(change, actor, db)


# ---------------------------------------------------------------------------
# GET CHANGE
# ---------------------------------------------------------------------------


@router.get(
    "/{change_id}",
    response_model=ChangeResponse,
)
def get_change(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(Change, Actor, Repository)
        .join(
            Actor,
            Actor.id == Change.actor_id,
            isouter=True,
        )
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            (Repository.owner_id == current_user.id) | (Repository.visibility == "public"),
            Repository.deleted_at.is_(None),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    change, actor, _repository = result

    return _to_change_response(change, actor, db)


# ---------------------------------------------------------------------------
# CHANGE FILES
# ---------------------------------------------------------------------------


@router.get(
    "/{change_id}/files",
    response_model=list[ChangeFileResponse],
)
def get_change_files(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = db.scalar(
        select(Change)
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            (Repository.owner_id == current_user.id) | (Repository.visibility == "public"),
            Repository.deleted_at.is_(None),
        )
    )

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    files = db.scalars(
        select(ChangeFile).where(
            ChangeFile.change_id == change.id
        )
    ).all()

    repository = db.scalar(
        select(Repository).where(Repository.id == change.repository_id)
    )

    if not files and repository and change.base_commit and change.resulting_commit:
        from app.services.pull_request_service import PullRequestService
        files = PullRequestService(db).sync_change_files_from_provider(repository, change)

    patches_by_path = {}
    if repository and change.base_commit and change.resulting_commit:
        import subprocess
        from pathlib import Path
        repo_dir = Path(settings.repository_storage_path) / repository.storage_key
        if repo_dir.exists():
            res = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(repo_dir),
                    "diff",
                    "-u",
                    f"{change.base_commit}..{change.resulting_commit}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = res.stdout
            if not stdout:
                res2 = subprocess.run(
                    [
                        "git",
                        "--git-dir",
                        str(repo_dir),
                        "diff-tree",
                        "-p",
                        "-r",
                        change.resulting_commit,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                stdout = res2.stdout or ""

            if stdout:
                current_path = None
                current_lines = []
                for line in stdout.splitlines(keepends=True):
                    if line.startswith("diff --git "):
                        if current_path and current_lines:
                            patches_by_path[current_path] = "".join(current_lines).strip()
                        parts = line.strip().split(" ")
                        if len(parts) >= 4 and parts[3].startswith("b/"):
                            current_path = parts[3][2:]
                        elif len(parts) >= 3 and parts[2].startswith("a/"):
                            current_path = parts[2][2:]
                        else:
                            current_path = None
                        current_lines = [line]
                    else:
                        if current_path:
                            current_lines.append(line)
                if current_path and current_lines:
                    patches_by_path[current_path] = "".join(current_lines).strip()
        elif repository.provider_type == "github" and repository.provider_owner:
            try:
                from app.services.pull_request_service import PullRequestService
                prov = PullRequestService(db)._get_provider(repository)
                if prov:
                    stats = prov.get_diff_stats(
                        owner=repository.provider_owner,
                        name=repository.name,
                        base=change.base_commit,
                        head=change.resulting_commit,
                    )
                    for cf in (stats.changed_files if stats else []):
                        fn = cf.get("filename")
                        p = cf.get("patch")
                        if fn and p:
                            patches_by_path[fn] = p
            except Exception:
                pass

    return [
        ChangeFileResponse(
            path=file.path,
            filename=file.path,
            status=file.operation,
            operation=file.operation,
            additions=file.additions,
            deletions=file.deletions,
            patch=patches_by_path.get(file.path),
        )
        for file in files
    ]



# ---------------------------------------------------------------------------
# AGENT CHANGE CREATION
#
# Agent-specific capability boundary:
#     change.create
#
# The agent must:
#     1. Be authenticated.
#     2. Be active.
#     3. Own the repository.
#     4. Have the change.create capability.
# ---------------------------------------------------------------------------


@router.post(
    "/agent",
    response_model=ChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Change (Agent)",
    description="Agent declares intent to make a change. Requires AgentSession and `change.create` capability.",
)
def create_agent_change(
    payload: CreateChangeRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    import json
    from app.models.task import Task

    repository = db.scalar(
        select(Repository).where(
            Repository.id == payload.repository_id,
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    actor = db.scalar(
        select(Actor).where(
            Actor.id == current_agent.id,
            Actor.type == "agent",
            Actor.owner_id == current_agent.owner_id,
        )
    )

    if actor is None:
        from app.api.agent_errors import raise_agent_inactive
        raise_agent_inactive()

    if not current_agent.is_active or current_agent.status != "active":
        from app.api.agent_errors import raise_agent_inactive
        raise_agent_inactive()

    # Enforce task governance if task_id is provided
    task = None
    agent_session_id = None
    if payload.task_id:
        task = db.scalar(select(Task).where(Task.id == payload.task_id))
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        if task.assigned_agent_id != current_agent.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent is not assigned to this task",
            )
        if task.repository_id != payload.repository_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Task repository does not match change repository",
            )
        agent_session_id = task.claimed_by_session_id

    try:
        AuthorizationService.require(
            actor=actor,
            repository=repository,
            capability=AuthorizationService.CHANGE_CREATE,
            db=db,
        )
    except PermissionError as exc:
        from app.api.agent_errors import raise_capability_required
        raise_capability_required(
            capability=AuthorizationService.CHANGE_CREATE,
            repository_slug=repository.slug if repository else "",
        )

    clean_name = current_agent.name.lower().replace(" ", "-")
    branch = payload.branch or (f"agent/{clean_name}/task-{task.id[:8]}" if task else f"agent/{clean_name}/change")
    base_branch = payload.base_branch or getattr(repository, "default_branch", None) or "main"

    meta = {
        "source": "agent",
        "agent_id": current_agent.id,
        "agent_name": current_agent.name,
        "agent_session_id": agent_session_id,
        "branch": branch,
        "base_branch": base_branch,
    }
    if task:
        meta["task_id"] = task.id
        meta["task_title"] = task.title

    change = Change(
        repository_id=repository.id,
        actor_id=actor.id,
        intent=payload.intent,
        base_commit=payload.base_commit,
        status="proposed",
        risk_level=payload.risk_level,
        metadata_json=json.dumps(meta, sort_keys=True),
    )

    db.add(change)
    db.flush()

    if task:
        task.resulting_change_id = change.id
        if task.status == Task.STATUS_ASSIGNED:
            task.status = Task.STATUS_IN_PROGRESS
        task.updated_at = datetime.now(timezone.utc)

    ChangeService(db).transition_change(
        change=change,
        new_status="proposed",
        actor_id=actor.id,
        event_type="change.created",
        reason="Change created by agent.",
        metadata={
            "intent": payload.intent,
            "risk_level": payload.risk_level,
            "branch": branch,
            "base_branch": base_branch,
            **({"task_id": task.id} if task else {}),
        },
    )

    db.commit()
    db.refresh(change)

    return _to_change_response(change, actor, db)


# ---------------------------------------------------------------------------
# FINALIZE CHANGE
# ---------------------------------------------------------------------------


@router.post(
    "/{change_id}/finalize",
    response_model=ChangeResponse,
)
def finalize_change(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(Change, Actor, Repository)
        .join(
            Actor,
            Actor.id == Change.actor_id,
        )
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    change, actor, repository = result

    try:
        ChangeService(db).finalize_change(change)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _to_change_response(change, actor, db)


@router.post(
    "/{change_id}/agent-finalize",
    response_model=ChangeResponse,
)
def finalize_agent_change(
    change_id: str,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(Change, Actor, Repository)
        .join(
            Actor,
            Actor.id == Change.actor_id,
        )
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Change.actor_id == current_agent.id,
            Actor.id == current_agent.id,
            Actor.type == "agent",
            Repository.owner_id == current_agent.owner_id,
            Repository.deleted_at.is_(None),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent change not found",
        )

    change, actor, repository = result

    if not current_agent.is_active or current_agent.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is inactive",
        )

    try:
        AuthorizationService.require(
            actor=actor,
            repository=repository,
            capability=AuthorizationService.CHANGE_COMMIT,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        ChangeService(db).finalize_change(change)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _to_change_response(change, actor, db)



# ---------------------------------------------------------------------------
# CHANGE AUDIT EVENTS
#
# Read-only endpoint.
# There is intentionally no POST/PUT/PATCH/DELETE endpoint for events.
# ---------------------------------------------------------------------------


@router.get(
    "/{change_id}/events",
    response_model=list[ChangeEventResponse],
)
def get_change_events(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = db.scalar(
        select(Change)
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
    )

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    events = db.scalars(
        select(ChangeEvent)
        .where(
            ChangeEvent.change_id == change_id
        )
        .order_by(
            ChangeEvent.created_at.asc(),
            ChangeEvent.id.asc(),
        )
    ).all()

    return [
        ChangeEventResponse(
            id=event.id,
            change_id=event.change_id,
            actor_id=event.actor_id,
            event_type=event.event_type,
            from_status=event.from_status,
            to_status=event.to_status,
            reason=event.reason,
            metadata_json=event.metadata_json,
            created_at=event.created_at,
        )
        for event in events
    ]