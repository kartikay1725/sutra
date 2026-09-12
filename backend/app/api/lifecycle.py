"""Canonical Engineering Lifecycle Status API.

Exposes a unified lifecycle state model for Task -> AgentSession -> Change ->
Commit -> PR -> CI -> Governance -> Approval -> Merge -> Task completion.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import _resolve_raw_token, bearer_scheme
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.agent_session import AgentSession
from app.models.user import User
from app.services.lifecycle_status_service import LifecycleStatusService

router = APIRouter(
    prefix="/v1/lifecycle",
    tags=["lifecycle"],
)


def _resolve_caller_actor_id(request: Request, db: Session) -> Optional[str]:
    """Resolve caller actor ID from JWT user token, agent session token, or cookie."""
    auth_header = request.headers.get("Authorization")
    raw_token = None
    if auth_header:
        parts = auth_header.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1].strip()
        else:
            raw_token = auth_header.strip()

    if not raw_token:
        raw_token = request.cookies.get("sutra_session") or request.cookies.get("sutra_token")

    if not raw_token:
        return None

    # Try User JWT
    try:
        user_id, _ = decode_access_token(raw_token)
        user = db.get(User, user_id)
        if user:
            return user.id
    except Exception:
        pass

    # Try AgentSession
    try:
        from app.core.security import verify_password
        # Find active session matching token prefix
        prefix = raw_token[:32] if len(raw_token) >= 32 else raw_token
        sessions = db.query(AgentSession).filter(AgentSession.token_prefix == prefix, AgentSession.status == "active").all()
        for s in sessions:
            if verify_password(raw_token, s.token_hash):
                return s.agent_id
    except Exception:
        pass

    return None


@router.get("/status")
def get_lifecycle_status(
    request: Request,
    task_id: Optional[str] = Query(None, description="Task ID"),
    pull_request_id: Optional[str] = Query(None, description="Pull Request ID"),
    change_id: Optional[str] = Query(None, description="Change ID"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the canonical consolidated engineering lifecycle status."""
    if not task_id and not pull_request_id and not change_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of 'task_id', 'pull_request_id', or 'change_id' must be provided.",
        )

    actor_id = _resolve_caller_actor_id(request, db)
    svc = LifecycleStatusService(db)
    result = svc.get_lifecycle_status(
        task_id=task_id,
        pull_request_id=pull_request_id,
        change_id=change_id,
        actor_id=actor_id,
    )

    if result.get("status") == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Lifecycle status not found"),
        )

    return result
