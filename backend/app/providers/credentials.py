from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List


@dataclass(frozen=True)
class DownstreamCredential:
    token: str
    token_type: str  # "bearer" | "basic" | "installation"
    expires_at: datetime  # Effective SUTRA expiration timestamp (<= 10 mins)
    effective_ttl_seconds: int
    repository: str
    permissions: Dict[str, str]
    clone_url: str
    provider_token_id: Optional[str] = None  # Reference for active downstream revocation


class CredentialProvider(ABC):
    """
    Isolated downstream token broker interface for issuing and revoking
    transport credentials used by agents against repository substrates.
    """

    @abstractmethod
    def issue_agent_token(
        self,
        agent_id: str,
        session_id: str,
        owner: str,
        repo: str,
        sutra_capabilities: List[str],
        max_ttl_seconds: int = 600,  # Strict maximum 10 minutes
    ) -> DownstreamCredential:
        """
        Issue a strictly scoped, short-lived downstream credential.
        Maps SUTRA capabilities to minimal provider permissions.
        Enforces effective TTL <= 10 minutes regardless of substrate defaults.
        """
        ...

    @abstractmethod
    def revoke_credential(
        self,
        session_id: str,
        token_or_id: str,
    ) -> bool:
        """
        Actively revoke a specific downstream credential on the substrate.
        """
        ...

    @abstractmethod
    def revoke_all_session_credentials(
        self,
        session_id: str,
    ) -> int:
        """
        Revoke all downstream tokens associated with a SUTRA AgentSession.
        """
        ...
