from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.agent_session import AgentSession


def cleanup_agent_sessions(
    db: Session,
    *,
    retention_days: int = 7,
) -> int:
    """
    Remove expired/revoked agent sessions after the retention period.

    Active sessions are never removed.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be at least 1")

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=retention_days
    )

    result = db.execute(
        delete(AgentSession).where(
            AgentSession.status.in_(
                ("expired", "revoked")
            ),
            AgentSession.created_at < cutoff,
        )
    )

    db.commit()

    return result.rowcount or 0
