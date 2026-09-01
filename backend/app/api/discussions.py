from datetime import datetime, timezone
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.discussion import Discussion, DiscussionComment
from app.models.repository import Repository
from app.models.user import User
from app.models.actor import Actor

router = APIRouter(
    prefix="/v1/repositories/{owner_name}/{repo_name}/discussions",
    tags=["discussions"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class DiscussionCreateRequest(BaseModel):
    title: str = Field(..., max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    category: str = Field(..., max_length=64)
    author_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class DiscussionCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    author_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class DiscussionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    repository_id: str
    author_id: str
    title: str
    body: str
    category: str
    created_at: datetime
    updated_at: datetime


class DiscussionCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    discussion_id: str
    author_id: str
    body: str
    created_at: datetime
    updated_at: datetime


def get_repository_for_user(owner_name: str, repo_name: str, db: Session, user: User) -> Repository:
    repo = db.scalar(
        select(Repository).join(Actor, Actor.id == Repository.owner_id).where(
            Actor.name == owner_name,
            Repository.name == repo_name,
        )
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    if repo.visibility != "public" and repo.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    return repo


def _verify_actor(actor_id: str, current_user: User, db: Session) -> Actor:
    actor = db.get(Actor, actor_id)
    if not actor:
        raise HTTPException(status_code=400, detail="Invalid author_id")
    return actor


@router.post(
    "",
    response_model=DiscussionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_discussion(
    owner_name: str,
    repo_name: str,
    payload: DiscussionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(owner_name, repo_name, db, current_user)
    author_id = payload.author_id or current_user.id
    _verify_actor(author_id, current_user, db)

    discussion = Discussion(
        repository_id=repo.id,
        author_id=current_user.id,
        title=payload.title,
        body=payload.body,
        category=payload.category,
    )
    db.add(discussion)
    db.commit()
    db.refresh(discussion)
    return discussion


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(owner_name, repo_name, db, current_user)
    
    stmt = select(Discussion).where(Discussion.repository_id == repo.id)
    if category:
        stmt = stmt.where(Discussion.category == category)
        
    stmt = stmt.order_by(Discussion.created_at.desc()).limit(limit).offset(offset)
    discussions = db.scalars(stmt).all()
    
    return list(discussions)


@router.get(
    "/{discussion_id}",
    response_model=DiscussionResponse,
)
def get_discussion(
    owner_name: str,
    repo_name: str,
    discussion_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(owner_name, repo_name, db, current_user)
    discussion = db.scalar(
        select(Discussion).where(Discussion.id == discussion_id, Discussion.repository_id == repo.id)
    )
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return discussion


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(owner_name, repo_name, db, current_user)
    discussion = db.scalar(
        select(Discussion).where(Discussion.id == discussion_id, Discussion.repository_id == repo.id)
    )
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    author_id = payload.author_id or current_user.id
    _verify_actor(author_id, current_user, db)

    comment = DiscussionComment(
        discussion_id=discussion.id,
        author_id=author_id,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(owner_name, repo_name, db, current_user)
    discussion = db.scalar(
        select(Discussion).where(Discussion.id == discussion_id, Discussion.repository_id == repo.id)
    )
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    stmt = select(DiscussionComment).where(DiscussionComment.discussion_id == discussion.id).order_by(DiscussionComment.created_at.asc()).limit(limit).offset(offset)
    comments = db.scalars(stmt).all()
    
    return list(comments)
