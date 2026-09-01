from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
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


class AttachCommitRequest(BaseModel):
    resulting_commit: str = Field(
        min_length=7,
        max_length=64,
        pattern=r"^[0-9a-f]{7,64}$",
    )


class ChangeResponse(BaseModel):
    id: str
    repository_id: str
    actor_id: str
    actor_type: str
    actor_name: str
    intent: str
    base_commit: str | None
    resulting_commit: str | None
    status: str
    risk_level: str | None = "unknown"
    additions: int = 0
    deletions: int = 0
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


def _to_change_response(change: Change, actor: Actor, db: Session) -> ChangeResponse:
    from app.models.pull_request import PullRequest
    files = db.scalars(
        select(ChangeFile).where(ChangeFile.change_id == change.id)
    ).all()
    pr = db.scalar(
        select(PullRequest).where(PullRequest.source_change_id == change.id)
    )
    return ChangeResponse(
        id=change.id,
        repository_id=change.repository_id,
        actor_id=actor.id,
        actor_type=actor.type,
        actor_name=actor.name,
        intent=change.intent,
        base_commit=change.base_commit,
        resulting_commit=change.resulting_commit,
        status=change.status,
        risk_level=change.risk_level or "unknown",
        additions=sum(f.additions for f in files),
        deletions=sum(f.deletions for f in files),
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if owner and repo:
        repository = db.scalar(
            select(Repository)
            .join(Actor, Actor.id == Repository.owner_id)
            .where(
                Actor.name == owner,
                Repository.slug == repo.lower(),
                Repository.deleted_at.is_(None)
            )
        )
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        stmt = select(Change, Actor).join(Actor, Actor.id == Change.actor_id)
        stmt = stmt.where(Change.repository_id == repository.id)
    else:
        stmt = select(Change, Actor).join(Actor, Actor.id == Change.actor_id)

    results = db.execute(stmt.order_by(Change.updated_at.desc())).all()

    stats = db.execute(
        select(
            ChangeFile.change_id,
            func.coalesce(func.sum(ChangeFile.additions), 0),
            func.coalesce(func.sum(ChangeFile.deletions), 0),
        ).group_by(ChangeFile.change_id)
    ).all()
    stats_map = {row[0]: (int(row[1]), int(row[2])) for row in stats}

    responses = []
    for change, actor in results:
        adds, dels = stats_map.get(change.id, (0, 0))
        responses.append(
            ChangeResponse(
                id=change.id,
                repository_id=change.repository_id,
                actor_id=actor.id,
                actor_type=actor.type,
                actor_name=actor.name,
                intent=change.intent,
                base_commit=change.base_commit,
                resulting_commit=change.resulting_commit,
                status=change.status,
                risk_level=change.risk_level,
                additions=adds,
                deletions=dels,
                created_at=change.created_at,
                updated_at=change.updated_at,
            )
        )
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
        reason="Change created by agent.",
        metadata={
            "intent": payload.intent,
            "risk_level": payload.risk_level,
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