from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.models.agent_session import AgentSession
from app.models.agent import Agent
from app.providers.credentials import CredentialProvider, DownstreamCredential


class LocalCredentialProvider(CredentialProvider):
    """
    Credential broker for local SUTRA Git HTTP Basic Auth.
    The agent uses its existing SUTRA AgentSession token as transport credential.
    """

    def __init__(self, db: Session):
        self.db = db

    def issue_agent_token(
        self,
        agent_id: str,
        session_id: str,
        owner: str,
        repo: str,
        sutra_capabilities: List[str],
        max_ttl_seconds: int = 600,
    ) -> DownstreamCredential:
        now = datetime.now(timezone.utc)
        effective_ttl = min(max_ttl_seconds, 600)  # max 10 min
        expires_at = now + timedelta(seconds=effective_ttl)

        # Retrieve session
        session = self.db.scalar(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.agent_id == agent_id,
                AgentSession.status == "active",
            )
        )
        if not session:
            raise ValueError("Active AgentSession not found for local credential issuance")

        perms = {
            "repository.read": "true" if "repository.read" in sutra_capabilities else "false",
            "repository.write": "true" if "repository.write" in sutra_capabilities else "false",
        }

        clone_url = f"https://github.com/{owner}/{repo}.git"

        return DownstreamCredential(
            token=session.token_prefix,  # or session token
            token_type="basic",
            expires_at=expires_at,
            effective_ttl_seconds=effective_ttl,
            repository=f"{owner}/{repo}",
            permissions=perms,
            clone_url=clone_url,
            provider_token_id=session.id,
        )

    def revoke_credential(
        self,
        session_id: str,
        token_or_id: str,
    ) -> bool:
        session = self.db.scalar(
            select(AgentSession).where(AgentSession.id == session_id)
        )
        if session:
            session.status = "revoked"
            session.revoked_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False

    def revoke_all_session_credentials(
        self,
        session_id: str,
    ) -> int:
        return 1 if self.revoke_credential(session_id, session_id) else 0
