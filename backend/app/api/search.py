from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.session import get_db
from app.models.repository import Repository
from app.models.actor import Actor


router = APIRouter(prefix="/v1/search", tags=["search"])


class SearchResult(BaseModel):
    type: str # "repository" or "user"
    name: str
    description: str | None = None
    url: str


@router.get("", response_model=list[SearchResult])
def search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    results = []
    search_term = f"%{q}%"

    # Search repositories
    repos = (
        db.query(Repository, Actor.name.label("owner_name"))
        .join(Actor, Repository.owner_id == Actor.id)
        .filter(
            Repository.visibility == "public",
            or_(
                Repository.name.ilike(search_term),
                Repository.description.ilike(search_term)
            )
        )
        .limit(10)
        .all()
    )
    
    for repo, owner_name in repos:
        results.append({
            "type": "repository",
            "name": f"{owner_name}/{repo.name}",
            "description": repo.description,
            "url": f"/repositories/{owner_name}/{repo.name}"
        })

    # Search users / orgs
    actors = (
        db.query(Actor)
        .filter(Actor.name.ilike(search_term))
        .filter(Actor.type.in_(["user", "organization"]))
        .limit(10)
        .all()
    )
    
    for actor in actors:
        results.append({
            "type": actor.type,
            "name": actor.name,
            "description": "",
            "url": f"/profile/{actor.name}"
        })

    return results
