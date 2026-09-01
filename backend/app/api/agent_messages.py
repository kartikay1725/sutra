from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.agent import Agent
from app.models.agent_message import AgentMessage
from app.models.user import User

router = APIRouter(
    prefix="/v1/agent-messages",
    tags=["agent_messages"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class AgentMessageCreateRequest(BaseModel):
    sender_agent_id: str = Field(pattern=UUID_PATTERN)
    receiver_agent_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    topic_id: str | None = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=10000)


class AgentMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    sender_agent_id: str
    receiver_agent_id: str | None
    topic_id: str | None
    content: str
    created_at: datetime


def _verify_agent_ownership(agent_id: str, user: User, db: Session) -> Agent:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # For this prototype, any user can act as their own agent or any agent they own
    # In a full robust implementation, we would check session tokens for the agent.
    if agent.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return agent


@router.post(
    "",
    response_model=AgentMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_message(
    payload: AgentMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sender = _verify_agent_ownership(payload.sender_agent_id, current_user, db)

    if payload.receiver_agent_id:
        receiver = db.get(Agent, payload.receiver_agent_id)
        if not receiver:
            raise HTTPException(status_code=404, detail="Receiver Agent not found")

    msg = AgentMessage(
        sender_agent_id=sender.id,
        receiver_agent_id=payload.receiver_agent_id,
        topic_id=payload.topic_id,
        content=payload.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.get(
    "",
    response_model=list[AgentMessageResponse],
)
def list_agent_messages(
    agent_id: str = Query(..., pattern=UUID_PATTERN),
    topic_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_agent_ownership(agent_id, current_user, db)

    # An agent sees messages they sent OR received (or broadcasted globally where receiver is None)
    # If a topic is specified, filter by that topic.
    stmt = select(AgentMessage).where(
        or_(
            AgentMessage.sender_agent_id == agent_id,
            AgentMessage.receiver_agent_id == agent_id,
        )
    )

    if topic_id:
        stmt = stmt.where(AgentMessage.topic_id == topic_id)

    stmt = stmt.order_by(AgentMessage.created_at.desc()).limit(limit).offset(offset)
    messages = db.scalars(stmt).all()
    
    return list(messages)
