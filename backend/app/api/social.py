from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.social import RepositoryStar, ActorFollow
from app.models.repository import Repository
from app.models.actor import Actor
from app.models.user import User


router = APIRouter(prefix="/v1", tags=["social"])


class StarResponse(BaseModel):
    actor_id: str
    repository_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class FollowResponse(BaseModel):
    follower_id: str
    following_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


@router.post("/repositories/{owner}/{repo}/star", status_code=status.HTTP_204_NO_CONTENT)
def star_repository(
    owner: str, repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    repository = db.query(Repository).join(Actor, Repository.owner_id == Actor.id).filter(
        Actor.name == owner, Repository.name == repo
    ).first()
    
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    existing = db.query(RepositoryStar).filter_by(
        actor_id=current_user.id,
        repository_id=repository.id
    ).first()

    if not existing:
        star = RepositoryStar(actor_id=current_user.id, repository_id=repository.id)
        db.add(star)
        db.commit()


@router.delete("/repositories/{owner}/{repo}/star", status_code=status.HTTP_204_NO_CONTENT)
def unstar_repository(
    owner: str, repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    repository = db.query(Repository).join(Actor, Repository.owner_id == Actor.id).filter(
        Actor.name == owner, Repository.name == repo
    ).first()
    
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    existing = db.query(RepositoryStar).filter_by(
        actor_id=current_user.id,
        repository_id=repository.id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()


@router.post("/users/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_actor = db.query(Actor).filter(Actor.name == username).first()
    if not target_actor:
        raise HTTPException(status_code=404, detail="User not found")
        
    if target_actor.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    existing = db.query(ActorFollow).filter_by(
        follower_id=current_user.id,
        following_id=target_actor.id
    ).first()

    if not existing:
        follow = ActorFollow(follower_id=current_user.id, following_id=target_actor.id)
        db.add(follow)
        db.commit()


@router.delete("/users/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_actor = db.query(Actor).filter(Actor.name == username).first()
    if not target_actor:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(ActorFollow).filter_by(
        follower_id=current_user.id,
        following_id=target_actor.id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
