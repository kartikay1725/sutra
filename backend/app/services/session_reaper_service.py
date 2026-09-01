import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.agent_session import AgentSession

logger = logging.getLogger(__name__)

class SessionReaperService:
    IDLE_TIMEOUT_SECONDS = 120  # 2 minutes

    def revoke_idle_sessions(self, db: Session) -> int:
        """
        Find sessions where last_seen_at < now - 120s
        and status == 'active'.
        Mark them status='revoked', revoked_at=now.
        Return count of revoked sessions.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.IDLE_TIMEOUT_SECONDS)

        # We use SQLAlchemy update with returning rowcount (or just execute and get rowcount)
        result = db.execute(
            update(AgentSession)
            .where(
                AgentSession.status == "active",
                AgentSession.last_seen_at < cutoff,
            )
            .values(
                status="revoked",
                revoked_at=now,
            )
        )
        
        db.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Revoked {count} idle agent sessions.")
        return count

    def revoke_expired_sessions(self, db: Session) -> int:
        """
        Find sessions where expires_at < now
        and status == 'active'.
        Mark them revoked.
        """
        now = datetime.now(timezone.utc)

        result = db.execute(
            update(AgentSession)
            .where(
                AgentSession.status == "active",
                AgentSession.expires_at < now,
            )
            .values(
                status="revoked",
                revoked_at=now,
            )
        )
        
        db.commit()
        count = result.rowcount
        if count > 0:
            logger.info(f"Revoked {count} expired agent sessions.")
        return count
