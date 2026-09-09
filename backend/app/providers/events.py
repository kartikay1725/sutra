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
    repository_external_id: Optional[str] = None


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
    title: Optional[str] = None
    body: Optional[str] = None
    html_url: Optional[str] = None
    author_login: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    repository_external_id: Optional[str] = None


@dataclass(frozen=True)
class NormalizedCheckRunEvent:
    provider_type: str  # "local" | "github"
    repository_owner: str
    repository_name: str
    check_run_id: int
    name: str
    head_sha: str
    status: str  # "queued" | "in_progress" | "completed"
    conclusion: Optional[str]  # "success" | "failure" | "neutral" | "cancelled" | "skipped" | "timed_out" | "action_required" | None
    html_url: Optional[str] = None
    details_url: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    pull_request_numbers: List[int] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    repository_external_id: Optional[str] = None


@dataclass(frozen=True)
class NormalizedIssueEvent:
    provider_type: str  # "local" | "github"
    repository_owner: str
    repository_name: str
    action: str  # "opened" | "edited" | "closed" | "reopened"
    issue_id: str
    issue_number: int
    title: str
    body: str
    state: str  # "open" | "closed"
    html_url: str
    author_login: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    repository_external_id: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedIssueCommentEvent:
    provider_type: str  # "local" | "github"
    repository_owner: str
    repository_name: str
    action: str  # "created" | "edited" | "deleted"
    comment_id: str
    issue_number: int
    body: str
    html_url: str
    author_login: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    repository_external_id: Optional[str] = None
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
