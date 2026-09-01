# SUTRA Phase 3 Interface Specification & Architecture Core

**Phase:** 3 — Interface Specification & Module Contracts  
**Date:** 2026-08-31  
**Status:** Interface & Type Specification (No implementation code written)

---

## 1. Architecture Refinements & Approved Directives

This specification incorporates the architectural decisions approved in Phase 2 with explicit amendments:

1. **D1 (Hybrid Providers):** `LocalRepositoryProvider` for existing bare repos; `GitHubRepositoryProvider` for external repositories.
2. **D2 (GitHub App):** Organization-level GitHub App identity with private key JWT authentication.
3. **D3 (Required SUTRA Policy Check):** GitHub rulesets enforce SUTRA Policy Check Run as a required status check.
4. **D4 (Direct GitHub Transport):** Agents push/clone directly against `github.com` using SUTRA-brokered downstream credentials.
5. **D5 (SUTRA-Controlled Merge):** Merge authorization rests solely with SUTRA; agents cannot merge.

### Crucial Security & Operational Amendments:
- **Token Lifetime Reality:** GitHub App Installation Access Tokens natively have a fixed 1-hour expiration. SUTRA enforces an **effective maximum TTL $\le$ 10 minutes** by actively managing issuance records in Redis, refusing reuse or renewal past 10 minutes, and explicitly calling `DELETE /installation/token` upon session termination or the 10-minute deadline.
- **Push vs. Merge Distinction:** Pushes to agent feature branches reach GitHub *before* SUTRA evaluates them. SUTRA observes the push via webhook, creates a pending/failing Check Run, and prevents the resulting Change from becoming mergeable until all policy, review, and approval gates pass.
- **Interface Separation:** `RepositoryProvider`, `CredentialProvider`, and `WebhookEventAdapter` are strictly segregated abstractions.
- **Minimal Capability Mapping:** `repository.write` maps strictly to `contents:write`. It does NOT grant `pull_requests:write`, `administration:write`, or merge permissions.
- **Plan Capability Detection:** Detects repository plan tiers (GitHub Free vs Team vs Enterprise) to adaptively configure branch rulesets vs legacy branch protection.

---

## 2. Capability & Permission Mapping Matrix

| SUTRA Capability | Target GitHub App Permission | Downstream Token Permission | Can Agent Merge? | Can Agent Bypass Rulesets? |
|------------------|------------------------------|-----------------------------|:----------------:|:--------------------------:|
| `repository.read` | `contents:read`, `metadata:read` | `contents:read`, `metadata:read` | **No** | **No** |
| `repository.write` | `contents:write`, `metadata:read` | `contents:write`, `metadata:read` | **No** | **No** |
| `change.create` | SUTRA Control Plane Only | (No GitHub permission) | **No** | **No** |
| `change.commit` | SUTRA Control Plane Only | (No GitHub permission) | **No** | **No** |
| `pull_request.create` | `pull_requests:write` (SUTRA App only) | (Not granted to agent token) | **No** | **No** |
| `pull_request.merge` | `contents:write`, `pull_requests:write` (SUTRA App only) | **NEVER GRANTED TO AGENT** | **No** | **No** |
| `knowledge_graph.*` | SUTRA Control Plane Only | (No GitHub permission) | **No** | **No** |

---

## 3. Core Interface Specifications (Python Protocols / ABCs)

### A. `RepositoryProvider` (Substrate Operations)

Location: `backend/app/providers/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass(frozen=True)
class ProviderRepoMetadata:
    provider_type: str  # "local" | "github"
    owner: str
    name: str
    default_branch: str
    is_private: bool
    clone_url: str
    external_id: Optional[str] = None
    capabilities: Optional[Dict[str, bool]] = None  # e.g., {"rulesets": True, "check_runs": True}


@dataclass(frozen=True)
class ProviderBranch:
    name: str
    commit_sha: str
    is_protected: bool


@dataclass(frozen=True)
class ProviderCommit:
    sha: str
    message: str
    author_name: str
    author_email: str
    committed_at: datetime
    parent_shas: List[str]
    tree_sha: str


@dataclass(frozen=True)
class ProviderDiffStat:
    files_changed: int
    additions: int
    deletions: int
    changed_files: List[Dict[str, Any]]


@dataclass(frozen=True)
class ProviderPullRequest:
    number: int
    title: str
    body: Optional[str]
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    is_merged: bool
    is_closed: bool
    mergeable: Optional[bool]
    html_url: str


@dataclass(frozen=True)
class ProviderMergeResult:
    success: bool
    merge_commit_sha: Optional[str]
    message: str


class RepositoryProvider(ABC):
    """Authoritative substrate interface for repository, commit, branch, PR, and merge operations."""

    @abstractmethod
    async def get_repository_metadata(self, owner: str, name: str) -> ProviderRepoMetadata:
        """Fetch repository details and detect plan capabilities."""
        ...

    @abstractmethod
    async def get_branch(self, owner: str, name: str, branch: str) -> Optional[ProviderBranch]:
        """Query branch existence and current HEAD commit."""
        ...

    @abstractmethod
    async def list_branches(self, owner: str, name: str) -> List[ProviderBranch]:
        """List all active branch references."""
        ...

    @abstractmethod
    async def get_commit(self, owner: str, name: str, sha: str) -> Optional[ProviderCommit]:
        """Fetch commit object details."""
        ...

    @abstractmethod
    async def get_diff_stats(self, owner: str, name: str, base: str, head: str) -> ProviderDiffStat:
        """Calculate diff stats (files, additions, deletions) between two refs/commits."""
        ...

    @abstractmethod
    async def read_file(self, owner: str, name: str, path: str, ref: str) -> bytes:
        """Read file contents at specified git ref."""
        ...

    @abstractmethod
    async def create_pull_request(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> ProviderPullRequest:
        """Create a pull request on the substrate."""
        ...

    @abstractmethod
    async def get_pull_request(self, owner: str, name: str, pr_number: int) -> Optional[ProviderPullRequest]:
        """Fetch pull request status and mergeability."""
        ...

    @abstractmethod
    async def merge_pull_request(
        self,
        owner: str,
        name: str,
        pr_number: int,
        commit_title: str,
        commit_message: str,
        expected_head_sha: str,
        method: str = "squash",  # "merge" | "squash" | "rebase"
    ) -> ProviderMergeResult:
        """Execute authoritative merge on the substrate."""
        ...
```

---

### B. `CredentialProvider` (Downstream Token Broker)

Location: `backend/app/providers/credentials.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict


@dataclass(frozen=True)
class DownstreamCredential:
    token: str
    token_type: str  # "bearer" | "basic" | "installation"
    expires_at: datetime  # Effective SUTRA expiration (<= 10 mins)
    effective_ttl_seconds: int
    repository: str
    permissions: Dict[str, str]
    clone_url: str
    provider_token_id: Optional[str] = None  # Underlying token reference for active revocation


class CredentialProvider(ABC):
    """Isolated downstream token issuance and active revocation broker."""

    @abstractmethod
    async def issue_agent_token(
        self,
        agent_id: str,
        session_id: str,
        owner: str,
        repo: str,
        sutra_capabilities: list[str],
        max_ttl_seconds: int = 600,  # Max 10 minutes
    ) -> DownstreamCredential:
        """
        Issue a strictly scoped, short-lived downstream credential.
        Maps SUTRA capabilities to minimal provider permissions.
        Enforces <= 10 min effective lifetime regardless of provider maximums.
        """
        ...

    @abstractmethod
    async def revoke_credential(
        self,
        session_id: str,
        token_or_id: str,
    ) -> bool:
        """
        Actively revoke the downstream credential on the provider substrate.
        Calls provider token deletion APIs where supported.
        """
        ...

    @abstractmethod
    async def revoke_all_session_credentials(
        self,
        session_id: str,
    ) -> int:
        """Revoke all downstream tokens associated with a SUTRA AgentSession."""
        ...
```

---

### C. `WebhookEventAdapter` (Ingestion & Normalization)

Location: `backend/app/providers/events.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass(frozen=True)
class NormalizedPushEvent:
    provider_type: str
    repository_owner: str
    repository_name: str
    ref: str
    before_sha: str
    after_sha: str
    is_created: bool
    is_deleted: bool
    is_forced: bool
    pusher_username: str
    commit_shas: List[str]
    raw_payload: Dict[str, Any]


@dataclass(frozen=True)
class NormalizedPullRequestEvent:
    provider_type: str
    repository_owner: str
    repository_name: str
    pr_number: int
    action: str  # "opened" | "synchronize" | "closed" | "reopened"
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    is_merged: bool
    raw_payload: Dict[str, Any]


class WebhookEventAdapter(ABC):
    """Normalizes substrate-specific webhooks into unified SUTRA domain events."""

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
    ) -> Optional[NormalizedPushEvent | NormalizedPullRequestEvent | Any]:
        """Convert substrate webhook JSON into normalized SUTRA domain event."""
        ...
```

---

### D. `CheckService` (Policy State Surfacing)

Location: `backend/app/services/check_service.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any


class CheckStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CheckConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CheckRunReport:
    check_name: str  # e.g., "SUTRA / Policy & Authorization"
    head_sha: str
    status: CheckStatus
    conclusion: Optional[CheckConclusion]
    title: str
    summary: str
    details_url: str
    external_id: str  # SUTRA Change ID or PR ID


class CheckService(ABC):
    """Surfaces SUTRA policy, review, and authorization gates to external PR check runs."""

    @abstractmethod
    async def report_policy_decision(
        self,
        owner: str,
        name: str,
        head_sha: str,
        change_id: str,
        policy_decision: Any,  # PolicyDecision
        review_status: str,
    ) -> str:
        """Create or update a Check Run on the substrate reflecting SUTRA policy state."""
        ...
```

---

### E. GitHub App Authentication Engine (`GitHubAppAuthService`)

Location: `backend/app/providers/github/auth.py`

```python
from datetime import datetime, timezone, timedelta
import jwt
import httpx


class GitHubAppAuthService:
    """Manages GitHub App JWT creation and Installation Token negotiation."""

    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.app_id = app_id
        self.private_key_pem = private_key_pem
        self.client = client or httpx.AsyncClient(base_url="https://api.github.com")

    def generate_app_jwt(self) -> str:
        """
        Generate RS256 JWT signed with GitHub App Private Key.
        Maximum lifetime: 10 minutes (per GitHub API requirements).
        """
        now = datetime.now(timezone.utc)
        payload = {
            "iat": int(now.timestamp()) - 60,  # 1 min in the past for clock drift
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    async def get_installation_id_for_repo(self, owner: str, repo: str) -> int:
        """Query repository installation ID via App JWT."""
        jwt_token = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        response = await self.client.get(f"/repos/{owner}/{repo}/installation", headers=headers)
        response.raise_for_status()
        return response.json()["id"]

    async def create_scoped_installation_token(
        self,
        installation_id: int,
        repositories: list[str],
        permissions: dict[str, str],
    ) -> dict:
        """
        Request an installation access token scoped to explicit repositories and permissions.
        Note: GitHub sets token lifetime to 1 hour; SUTRA enforces effective TTL <= 10 min.
        """
        jwt_token = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        }
        body = {
            "repositories": repositories,
            "permissions": permissions,
        }
        response = await self.client.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()  # contains "token", "expires_at", "permissions"
```

---

### F. Provider Selection & Resolution Engine (`ProviderRegistry`)

Location: `backend/app/providers/registry.py`

```python
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.providers.base import RepositoryProvider
from app.providers.credentials import CredentialProvider


class ProviderRegistry:
    """Resolves appropriate Provider instances based on Repository configuration."""

    def __init__(
        self,
        local_repo_provider: RepositoryProvider,
        local_cred_provider: CredentialProvider,
        github_repo_provider: RepositoryProvider,
        github_cred_provider: CredentialProvider,
    ):
        self.local_repo_provider = local_repo_provider
        self.local_cred_provider = local_cred_provider
        self.github_repo_provider = github_repo_provider
        self.github_cred_provider = github_cred_provider

    def resolve_repository_provider(self, repository: Repository) -> RepositoryProvider:
        provider_type = getattr(repository, "provider_type", "local") or "local"
        if provider_type == "github":
            return self.github_repo_provider
        return self.local_repo_provider

    def resolve_credential_provider(self, repository: Repository) -> CredentialProvider:
        provider_type = getattr(repository, "provider_type", "local") or "local"
        if provider_type == "github":
            return self.github_cred_provider
        return self.local_cred_provider
```

---

## 4. Plan & Capability Detection Strategy

GitHub features vary by account and repository plan tiers. The adapter performs runtime capability detection during repository connection:

```
                      Query GET /repos/{owner}/{repo}
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       [GitHub Free (Private)]                [GitHub Team / Enterprise / Public]
                 │                                       │
                 ▼                                       ▼
• Branch Rulesets: Limited / Basic       • Full Branch Rulesets Supported
• Direct merge bypass prevention:         • Require status checks: SUTRA Check Run
  Requires Classic Branch Protection     • Restrict bypass actors: SUTRA App Only
  or SUTRA Control-Plane enforcement     • SUTRA Check Run marked strictly Required
```

1. **Detection Routine:** When linking a GitHub repository, SUTRA queries `GET /repos/{owner}/{repo}` to inspect `plan`, `visibility`, and `permissions`.
2. **Graceful Fallback:** If rulesets are unavailable on the plan tier, SUTRA falls back to standard Classic Branch Protection API (`PUT /repos/{owner}/{repo}/branches/{branch}/protection`), ensuring required status checks are configured in all environments.

---

## 5. Security & Isolation Invariants

1. **SUTRA AgentSession is Sovereign:** Downstream GitHub tokens cannot authenticate to any SUTRA REST API endpoint.
2. **Zero Direct Merge Capability:** Downstream tokens granted to agents never carry `pull_requests:write` or merge capabilities.
3. **Effective 10-Minute Token Horizon:** All broker records stored in Redis enforce an active 10-minute expiry deadline.
4. **Immediate Distributed Revocation:** Agent session revocation instantly deletes the Redis token lease and sends an asynchronous `DELETE /installation/token` to GitHub.

---

*Phase 3 Interface Specification Complete. Stopped for review before implementation.*
