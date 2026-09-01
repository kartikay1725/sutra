from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union


@dataclass(frozen=True)
class NormalizedPushEvent:
    provider_type: str  # "local" | "github"
    repository_owner: str
    repository_name: str
    ref: str
    before_sha: str
    after_sha: str
    is_created: bool
    is_deleted: bool
    is_forced: bool
    pusher_username: str
    commit_shas: List[str] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedPullRequestEvent:
    provider_type: str  # "local" | "github"
    repository_owner: str
    repository_name: str
    pr_number: int
    action: str  # "opened" | "synchronize" | "closed" | "reopened"
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    is_merged: bool = False
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class WebhookEventAdapter(ABC):
    """
    Substrate-specific webhook verification and event normalization adapter.
    """

    @abstractmethod
    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: str,
    ) -> bool:
        """Cryptographically verify webhook authenticity (e.g. HMAC-SHA256)."""
        ...

    @abstractmethod
    def parse_event(
        self,
        event_type_header: str,
        payload: Dict[str, Any],
    ) -> Optional[Union[NormalizedPushEvent, NormalizedPullRequestEvent, Any]]:
        """Normalize substrate-specific JSON payloads into unified SUTRA domain events."""
        ...
