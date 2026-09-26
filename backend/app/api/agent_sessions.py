from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.user import User

router = APIRouter(prefix="/v1/agents", tags=["agent-sessions"])


class AgentSessionListItem(BaseModel):
    session_id: str
    agent_id: str
    token_prefix: str
    status: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None


@router.get(
    "/{agent_id}/sessions",
    response_model=list[AgentSessionListItem],
)
def list_agent_sessions(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id)
    )

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    sessions = db.scalars(
        select(AgentSession)
        .where(AgentSession.agent_id == agent_id)
        .order_by(AgentSession.created_at.desc())
    ).all()

    return [
        AgentSessionListItem(
            session_id=session.id,
            agent_id=session.agent_id,
            token_prefix=session.token_prefix,
            status=session.status,
            created_at=session.created_at,
            expires_at=session.expires_at,
            last_seen_at=session.last_seen_at,
            revoked_at=session.revoked_at,
        )
        for session in sessions
    ]
