from datetime import datetime, timedelta, timezone
import secrets
import logging

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.redis_service import redis_service
from app.db.session import get_db
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.api.agent_errors import (
    raise_session_required,
    raise_session_expired,
    raise_session_revoked,
    raise_agent_inactive,
)

logger = logging.getLogger("sutra.agent_session")

SESSION_TTL_MINUTES = 15
SESSION_IDLE_TIMEOUT_SECONDS = 120


def _utc_datetime(value: datetime) -> datetime:
    """
    Normalize database timestamps to timezone-aware UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise_session_required()

    scheme, _, token = authorization.partition(" ")  # type: ignore[union-attr]

    if scheme.lower() != "bearer" or not token:
        raise_session_required()

    return token.strip()  # type: ignore[return-value]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate_agent_token(
    token: str,
    db: Session,
) -> Agent:
    """
    Authenticate the long-lived agent credential.
    This credential is only accepted when creating a session.
    """
    prefix = token[:16]

    agents = db.scalars(
        select(Agent).where(
            Agent.is_active.is_(True),
            Agent.status == "active",
            Agent.token_prefix == prefix,
        )
    ).all()

    for agent in agents:
        if verify_password(token, agent.token_hash):
            agent.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return agent

    raise _unauthorized("Invalid agent credential")


def create_agent_session(
    agent: Agent,
    db: Session,
) -> tuple[AgentSession, str]:
    """
    Create a short-lived authenticated session for an agent.
    Writes durable audit record to PostgreSQL and accelerates ephemeral state via Redis.
    """
    now = datetime.now(timezone.utc)

    raw_token = (
        "sutra_session_"
        + secrets.token_urlsafe(32)
    )
    prefix = raw_token[:32]
    token_hash = hash_password(raw_token)

    session = AgentSession(
        agent_id=agent.id,
        token_hash=token_hash,
        token_prefix=prefix,
        status="active",
        created_at=now,
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
        last_seen_at=now,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # Populate Redis ephemeral session cache
    ttl_seconds = SESSION_TTL_MINUTES * 60
    try:
        redis_service.set(
            f"session:{prefix}",
            {
                "session_id": session.id,
                "agent_id": agent.id,
                "token_hash": token_hash,
                "status": "active",
                "expires_at": session.expires_at.isoformat(),
            },
            ex=ttl_seconds,
        )
    except Exception as e:
        logger.warning(f"Failed to cache agent session in Redis: {e}")

    return session, raw_token


def validate_agent_session_token(
    token: str,
    db: Session,
) -> AgentSession:
    """
    Validate an AgentSession token with Redis-backed revocation checking and fallback.
    """
    now = datetime.now(timezone.utc)
    prefix = token[:32]

    # 1. Check Redis for active session or fast lookup
    cached_session = None
    try:
        cached_session = redis_service.get(f"session:{prefix}")
    except Exception as e:
        logger.warning(f"Redis session lookup error: {e}")

    if cached_session:
        session_id = cached_session.get("session_id")
        # Check instant revocation marker
        try:
            if redis_service.exists(f"revoked_session:{session_id}"):
                raise_session_revoked()
        except HTTPException:
            raise
        except Exception:
            pass

    # 2. Authoritative PostgreSQL verification
    sessions = db.scalars(
        select(AgentSession)
        .where(
            AgentSession.token_prefix == prefix,
            AgentSession.status == "active",
        )
    ).all()

    for session in sessions:
        # Check instant revocation key
        try:
            if redis_service.exists(f"revoked_session:{session.id}"):
                raise_session_revoked()
        except HTTPException:
            raise
        except Exception:
            pass

        if not verify_password(token, session.token_hash):
            continue

        if session.revoked_at is not None:
            # Propagate to Redis revocation cache
            try:
                redis_service.set(f"revoked_session:{session.id}", "1", ex=SESSION_TTL_MINUTES * 60)
            except Exception:
                pass
            raise_session_revoked()

        expires_at = _utc_datetime(session.expires_at)
        last_seen_at = _utc_datetime(session.last_seen_at)

        if expires_at <= now:
            session.status = "expired"
            db.commit()
            raise_session_expired()

        idle_seconds = (now - last_seen_at).total_seconds()
        if idle_seconds > SESSION_IDLE_TIMEOUT_SECONDS:
            session.status = "expired"
            db.commit()
            raise_session_expired()

        agent = db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )

        if agent is None:
            session.status = "revoked"
            session.revoked_at = now
            db.commit()
            try:
                redis_service.set(f"revoked_session:{session.id}", "1", ex=SESSION_TTL_MINUTES * 60)
            except Exception:
                pass
            raise_agent_inactive()

        session.last_seen_at = now
        agent.last_used_at = now
        db.commit()

        return session

    raise_session_required()


def get_current_agent_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentSession:
    token = _extract_bearer_token(authorization)
    return validate_agent_session_token(token, db)


def get_current_agent(
    current_session: AgentSession = Depends(get_current_agent_session),
    db: Session = Depends(get_db),
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == current_session.agent_id,
            Agent.is_active.is_(True),
            Agent.status == "active",
        )
    )

    if agent is None:
        raise _unauthorized("Agent is inactive or revoked")

    return agent


def revoke_agent_session(
    session: AgentSession,
    db: Session,
) -> AgentSession:
    """
    Revoke an agent session immediately.
    Sets Redis revocation marker for 0ms distributed revocation across all workers.
    """
    now = datetime.now(timezone.utc)
    session.status = "revoked"

    if session.revoked_at is None:
        session.revoked_at = now

    db.commit()
    db.refresh(session)

    # Immediate Redis revocation key
    ttl_seconds = SESSION_TTL_MINUTES * 60
    try:
        redis_service.set(f"revoked_session:{session.id}", "1", ex=ttl_seconds)
        redis_service.delete(f"session:{session.token_prefix}")
    except Exception as e:
        logger.error(f"Failed to write revocation marker to Redis for session {session.id}: {e}")

    return session