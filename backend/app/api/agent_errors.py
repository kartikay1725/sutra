"""
SUTRA Agent Error Contract — Phase 5C
======================================

Defines the canonical, machine-readable denial structure that SUTRA returns
to agents on every authorization, lifecycle, and capability failure.

Design principles:
- Every denial teaches the legal next step (error_code + next_action).
- Never expose privileged bypass instructions.
- The "detail" field in HTTPException contains the AgentDenial dict so
  FastAPI's standard response schema remains valid.
- Retryable denials are those that may succeed after a state change
  (e.g. SESSION_REQUIRED) vs permanent denials (e.g. AGENT_ACTION_FORBIDDEN).
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

# Session / identity errors
SESSION_REQUIRED = "SESSION_REQUIRED"
SESSION_EXPIRED = "SESSION_EXPIRED"
SESSION_REVOKED = "SESSION_REVOKED"
AGENT_INACTIVE = "AGENT_INACTIVE"

# Authorization / capability errors
REPOSITORY_ACCESS_REQUIRED = "REPOSITORY_ACCESS_REQUIRED"
CAPABILITY_REQUIRED = "CAPABILITY_REQUIRED"

# Lifecycle errors
INVALID_LIFECYCLE_TRANSITION = "INVALID_LIFECYCLE_TRANSITION"
CHANGE_REQUIRED = "CHANGE_REQUIRED"
EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"

# Forbidden action errors (not retryable)
AGENT_ACTION_FORBIDDEN = "AGENT_ACTION_FORBIDDEN"

# Concurrency / integrity errors
STALE_HEAD = "STALE_HEAD"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"

# Policy errors
POLICY_BLOCKED = "POLICY_BLOCKED"


# ---------------------------------------------------------------------------
# Structured denial model
# ---------------------------------------------------------------------------

class AllowedAction(BaseModel):
    name: str
    method: str
    endpoint: str
    description: str = ""


class NextAction(BaseModel):
    operation: str
    method: str
    endpoint: str
    description: str = ""


class AgentDenial(BaseModel):
    """
    Machine-readable denial response returned to agents on any
    authorization, lifecycle, or capability failure.

    Wrapped inside the FastAPI `detail` field so the standard
    HTTP error schema remains valid:

        {"detail": {<AgentDenial fields>}}
    """
    error_code: str
    current_state: str
    reason: str
    missing_prerequisites: list[str] = []
    required_capabilities: list[str] = []
    allowed_actions: list[AllowedAction] = []
    next_action: NextAction | None = None
    retryable: bool = False
    http_status: int


# ---------------------------------------------------------------------------
# Pre-built denial factories
# ---------------------------------------------------------------------------

_SESSION_ACTIONS = [
    AllowedAction(
        name="create_session",
        method="POST",
        endpoint="/v1/agents/session",
        description="Authenticate with your permanent agent token to obtain a session.",
    )
]

_SESSION_NEXT = NextAction(
    operation="create_session",
    method="POST",
    endpoint="/v1/agents/session",
    description="Obtain an AgentSession token using your permanent agent credential.",
)

_CONTEXT_NEXT = NextAction(
    operation="get_context",
    method="GET",
    endpoint="/v1/agent/context",
    description="Retrieve your current session state, repository access, and allowed actions.",
)


def _http_denial(http_status: int, denial: AgentDenial) -> HTTPException:
    """Wrap an AgentDenial into a FastAPI HTTPException."""
    return HTTPException(
        status_code=http_status,
        detail=denial.model_dump(),
    )


def raise_session_required() -> None:
    """Agent must create a session first."""
    raise _http_denial(
        status.HTTP_401_UNAUTHORIZED,
        AgentDenial(
            error_code=SESSION_REQUIRED,
            current_state="unauthenticated",
            reason=(
                "No active agent session. "
                "Use your permanent agent token to create a session."
            ),
            missing_prerequisites=["active_agent_session"],
            allowed_actions=_SESSION_ACTIONS,
            next_action=_SESSION_NEXT,
            retryable=True,
            http_status=status.HTTP_401_UNAUTHORIZED,
        ),
    )


def raise_session_expired() -> None:
    """Session has expired."""
    raise _http_denial(
        status.HTTP_401_UNAUTHORIZED,
        AgentDenial(
            error_code=SESSION_EXPIRED,
            current_state="session_expired",
            reason=(
                "Your agent session has expired (absolute TTL or idle timeout). "
                "Create a new session."
            ),
            missing_prerequisites=["active_agent_session"],
            allowed_actions=_SESSION_ACTIONS,
            next_action=_SESSION_NEXT,
            retryable=True,
            http_status=status.HTTP_401_UNAUTHORIZED,
        ),
    )


def raise_session_revoked() -> None:
    """Session was explicitly revoked."""
    raise _http_denial(
        status.HTTP_401_UNAUTHORIZED,
        AgentDenial(
            error_code=SESSION_REVOKED,
            current_state="session_revoked",
            reason=(
                "Your agent session has been revoked. "
                "Contact the repository owner and create a new session if re-authorized."
            ),
            missing_prerequisites=["active_agent_session"],
            allowed_actions=_SESSION_ACTIONS,
            next_action=_SESSION_NEXT,
            retryable=False,
            http_status=status.HTTP_401_UNAUTHORIZED,
        ),
    )


def raise_agent_inactive() -> None:
    """Agent account is not active."""
    raise _http_denial(
        status.HTTP_401_UNAUTHORIZED,
        AgentDenial(
            error_code=AGENT_INACTIVE,
            current_state="agent_inactive",
            reason=(
                "Your agent account is inactive or has been revoked. "
                "No operations are permitted."
            ),
            missing_prerequisites=["active_agent_account"],
            retryable=False,
            http_status=status.HTTP_401_UNAUTHORIZED,
        ),
    )


def raise_repository_access_required(
    *,
    repository_slug: str = "",
    next_action: NextAction | None = None,
) -> None:
    """Agent has no repository access grant at all."""
    raise _http_denial(
        status.HTTP_403_FORBIDDEN,
        AgentDenial(
            error_code=REPOSITORY_ACCESS_REQUIRED,
            current_state="no_repository_access",
            reason=(
                f"You have no access grant for repository '{repository_slug}'. "
                "A human repository owner must grant you access via "
                "POST /v1/repositories/{owner}/{repo}/agents."
            ),
            missing_prerequisites=["repository_access_grant"],
            allowed_actions=[
                AllowedAction(
                    name="get_context",
                    method="GET",
                    endpoint="/v1/agent/context",
                    description="Check which repositories you currently have access to.",
                )
            ],
            next_action=next_action or _CONTEXT_NEXT,
            retryable=False,
            http_status=status.HTTP_403_FORBIDDEN,
        ),
    )


def raise_capability_required(
    *,
    capability: str,
    repository_slug: str = "",
    allowed_actions: list[AllowedAction] | None = None,
    next_action: NextAction | None = None,
) -> None:
    """Agent has a repository grant but is missing a specific capability."""
    raise _http_denial(
        status.HTTP_403_FORBIDDEN,
        AgentDenial(
            error_code=CAPABILITY_REQUIRED,
            current_state="insufficient_capabilities",
            reason=(
                f"Capability '{capability}' is required for this operation on "
                f"repository '{repository_slug}', but it is not in your grant. "
                "Contact the repository owner to update your access permissions."
            ),
            missing_prerequisites=[capability],
            required_capabilities=[capability],
            allowed_actions=allowed_actions or [
                AllowedAction(
                    name="get_context",
                    method="GET",
                    endpoint="/v1/agent/context",
                    description="Review your current capabilities.",
                )
            ],
            next_action=next_action or _CONTEXT_NEXT,
            retryable=False,
            http_status=status.HTTP_403_FORBIDDEN,
        ),
    )


def raise_invalid_lifecycle_transition(
    *,
    resource: str,
    current_status: str,
    attempted_status: str,
    valid_next: list[str] | None = None,
) -> None:
    """Invalid state machine transition attempted."""
    valid_desc = ", ".join(valid_next) if valid_next else "none"
    raise _http_denial(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        AgentDenial(
            error_code=INVALID_LIFECYCLE_TRANSITION,
            current_state=current_status,
            reason=(
                f"Cannot transition {resource} from '{current_status}' to "
                f"'{attempted_status}'. Valid next states: [{valid_desc}]."
            ),
            missing_prerequisites=[],
            next_action=_CONTEXT_NEXT,
            retryable=False,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    )


def raise_evidence_required(*, change_id: str = "") -> None:
    """Change must have a commit attached before this operation."""
    raise _http_denial(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        AgentDenial(
            error_code=EVIDENCE_REQUIRED,
            current_state="change_no_commit",
            reason=(
                "This operation requires the Change to have a resulting commit. "
                "Attach a commit first using PATCH /v1/changes/{id}/commit."
            ),
            missing_prerequisites=["resulting_commit"],
            allowed_actions=[
                AllowedAction(
                    name="attach_commit",
                    method="PATCH",
                    endpoint=f"/v1/changes/{change_id}/commit" if change_id else "/v1/changes/{id}/commit",
                    description="Attach the resulting commit SHA to this Change.",
                )
            ],
            next_action=NextAction(
                operation="attach_commit",
                method="PATCH",
                endpoint=f"/v1/changes/{change_id}/commit" if change_id else "/v1/changes/{id}/commit",
                description="Push your feature branch and attach the commit SHA.",
            ),
            retryable=True,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    )


def raise_human_approval_required(*, pull_request_id: str = "") -> None:
    """Merge requires human review approval — agent cannot self-approve."""
    raise _http_denial(
        status.HTTP_403_FORBIDDEN,
        AgentDenial(
            error_code=HUMAN_APPROVAL_REQUIRED,
            current_state="awaiting_human_approval",
            reason=(
                "This Pull Request requires human reviewer approval before merge. "
                "An authorized human must approve via POST /v1/pull-requests/{id}/approve. "
                "Agents cannot approve their own changes."
            ),
            missing_prerequisites=["human_reviewer_approval"],
            allowed_actions=[
                AllowedAction(
                    name="get_pull_request",
                    method="GET",
                    endpoint=f"/v1/pull-requests/{pull_request_id}" if pull_request_id else "/v1/pull-requests/{id}",
                    description="Check current Pull Request status.",
                )
            ],
            next_action=NextAction(
                operation="wait_for_human_approval",
                method="GET",
                endpoint=f"/v1/pull-requests/{pull_request_id}" if pull_request_id else "/v1/pull-requests/{id}",
                description="Poll PR status until status=approved, then re-attempt merge.",
            ),
            retryable=True,
            http_status=status.HTTP_403_FORBIDDEN,
        ),
    )


def raise_agent_action_forbidden(*, reason: str) -> None:
    """An operation that agents can never perform (e.g., self-approval)."""
    raise _http_denial(
        status.HTTP_403_FORBIDDEN,
        AgentDenial(
            error_code=AGENT_ACTION_FORBIDDEN,
            current_state="forbidden",
            reason=reason,
            missing_prerequisites=[],
            retryable=False,
            http_status=status.HTTP_403_FORBIDDEN,
        ),
    )


def raise_policy_blocked(
    *,
    policy_reason: str,
    reasons: list[str] | None = None,
) -> None:
    """Change is blocked by SUTRA policy."""
    raise _http_denial(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        AgentDenial(
            error_code=POLICY_BLOCKED,
            current_state="policy_blocked",
            reason=(
                f"Merge rejected: {policy_reason} "
                "Human review and explicit approval are required before this Change can be merged."
            ),
            missing_prerequisites=reasons or ["policy_approval"],
            allowed_actions=[
                AllowedAction(
                    name="get_context",
                    method="GET",
                    endpoint="/v1/agent/context",
                    description="Review current lifecycle state.",
                )
            ],
            next_action=NextAction(
                operation="wait_for_policy_resolution",
                method="GET",
                endpoint="/v1/agent/context",
                description="A human must resolve the policy block before merge can proceed.",
            ),
            retryable=False,
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
    )


def raise_stale_head(
    *,
    expected_sha: str = "",
    actual_sha: str = "",
) -> None:
    """Merge rejected because expected SHA does not match current PR head."""
    raise _http_denial(
        status.HTTP_409_CONFLICT,
        AgentDenial(
            error_code=STALE_HEAD,
            current_state="stale_head_sha",
            reason=(
                "The PR head has advanced since this operation was prepared. "
                f"Expected SHA '{expected_sha}' but current head is '{actual_sha}'. "
                "Refresh the PR and re-verify before retrying."
            ),
            missing_prerequisites=["current_head_sha"],
            next_action=NextAction(
                operation="refresh_pull_request",
                method="GET",
                endpoint="/v1/pull-requests/{id}",
                description="Get the current PR head SHA and re-prepare the merge.",
            ),
            retryable=True,
            http_status=status.HTTP_409_CONFLICT,
        ),
    )


def raise_idempotency_conflict(
    *,
    operation_key: str = "",
    existing_id: str = "",
) -> None:
    """Duplicate operation_key — return existing resource instead of creating."""
    raise _http_denial(
        status.HTTP_409_CONFLICT,
        AgentDenial(
            error_code=IDEMPOTENCY_CONFLICT,
            current_state="duplicate_operation",
            reason=(
                f"An operation with key '{operation_key}' already exists "
                f"(id: {existing_id}). "
                "Re-use the existing resource instead of creating a duplicate."
            ),
            missing_prerequisites=[],
            next_action=NextAction(
                operation="get_existing",
                method="GET",
                endpoint=f"/v1/changes/{existing_id}" if existing_id else "/v1/changes/{id}",
                description="Retrieve the existing resource.",
            ),
            retryable=False,
            http_status=status.HTTP_409_CONFLICT,
        ),
    )


# ---------------------------------------------------------------------------
# Generic factory for custom denials
# ---------------------------------------------------------------------------

def agent_denial(
    error_code: str,
    *,
    http_status_code: int,
    current_state: str,
    reason: str,
    missing_prerequisites: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    allowed_actions: list[dict[str, Any]] | None = None,
    next_action: dict[str, Any] | None = None,
    retryable: bool = False,
) -> HTTPException:
    """
    Generic factory for one-off structured denials.
    Returns an HTTPException (does not raise) so callers can `raise` it directly.
    """
    return _http_denial(
        http_status_code,
        AgentDenial(
            error_code=error_code,
            current_state=current_state,
            reason=reason,
            missing_prerequisites=missing_prerequisites or [],
            required_capabilities=required_capabilities or [],
            allowed_actions=[AllowedAction(**a) for a in (allowed_actions or [])],
            next_action=NextAction(**next_action) if next_action else None,
            retryable=retryable,
            http_status=http_status_code,
        ),
    )
