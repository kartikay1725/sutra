from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.agent_dependencies import get_current_agent_session
from app.models.agent_session import AgentSession


router = APIRouter(
    prefix="/v1/agent-protocol",
    tags=["agent-protocol"],
)


# ---------------------------------------------------------------------------
# HANDSHAKE
# ---------------------------------------------------------------------------

class HandshakeRequest(BaseModel):
    protocol: str
    protocol_version: str
    client_name: str
    client_type: str


class HandshakeResponse(BaseModel):
    protocol: str
    protocol_version: str
    workflow: list[dict]
    session_instructions: dict
    capability_instructions: dict
    repository_instructions: dict
    knowledge_graph_instructions: dict
    git_instructions: dict
    error_handling: dict


@router.post(
    "/handshake",
    response_model=HandshakeResponse,
)
def agent_handshake(request: HandshakeRequest):
    """
    Return the static SUTRA agent protocol contract.

    IMPORTANT:
    This endpoint explains how SUTRA works.
    It does not grant permissions and does not determine the agent's
    current lifecycle state.

    The current state and legal next action come from:
        GET /v1/agent/context
    """

    if request.protocol != "sutra-agent":
        raise HTTPException(
            status_code=400,
            detail="Unsupported protocol. Expected 'sutra-agent'.",
        )

    if request.protocol_version != "1":
        raise HTTPException(
            status_code=400,
            detail="Unsupported protocol version. Expected '1'.",
        )

    return HandshakeResponse(
        protocol="sutra-agent",
        protocol_version="1",

        workflow=[
            {
                "step": 1,
                "action": "Establish Agent Identity",
                "description": (
                    "A human owner registers or provisions the agent. "
                    "The permanent agent credential is issued out of band."
                ),
            },
            {
                "step": 2,
                "action": "Create AgentSession",
                "endpoint": "POST /v1/agents/session",
                "description": (
                    "Exchange the permanent agent credential for a "
                    "short-lived AgentSession."
                ),
            },
            {
                "step": 3,
                "action": "Read Agent Context",
                "endpoint": "GET /v1/agent/context",
                "description": (
                    "This is the authoritative machine-readable view of "
                    "the agent's identity, session state, repository access, "
                    "capabilities, lifecycle state, blocked actions, and "
                    "recommended next action."
                ),
            },
            {
                "step": 4,
                "action": "Follow Current Legal Action",
                "description": (
                    "Use the method and endpoint returned by "
                    "next_recommended_action or an explicitly permitted "
                    "entry in allowed_actions."
                ),
            },
            {
                "step": 5,
                "action": "Perform Authorized Engineering Work",
                "description": (
                    "SUTRA authorization remains the enforcement boundary. "
                    "An agent must never infer authority from documentation "
                    "alone."
                ),
            },
            {
                "step": 6,
                "action": "Refresh Agent Context",
                "endpoint": "GET /v1/agent/context",
                "description": (
                    "Refresh after meaningful lifecycle changes, "
                    "permission changes, or when determining the next step."
                ),
            },
            {
                "step": 7,
                "action": "Handle Denials",
                "description": (
                    "When an operation is denied, inspect the structured "
                    "denial and follow the legal recovery path. Do not "
                    "repeat an operation that remains unauthorized."
                ),
            },
            {
                "step": 8,
                "action": "Stop at Human Approval Boundary",
                "description": (
                    "Agents may submit engineering work and review findings, "
                    "but cannot self-approve or trigger their own merge."
                ),
            },
        ],

        session_instructions={
            "creation_mechanism": (
                "POST /v1/agents/session with the permanent agent credential."
            ),
            "requirements": (
                "The agent must be active. Revoked/inactive agent credentials "
                "cannot establish a new session."
            ),
            "expiration_behavior": (
                "The AgentSession has absolute expiration and idle timeout. "
                "Protected API access stops when the session becomes invalid."
            ),
            "revocation_behavior": (
                "A revoked AgentSession must no longer authenticate protected "
                "agent endpoints."
            ),
            "renewal_behavior": (
                "Create a new session using the permanent credential after "
                "the previous session expires, provided the agent remains active."
            ),
        },

        capability_instructions={
            "source_of_truth": (
                "Capabilities and currently legal actions are surfaced by "
                "GET /v1/agent/context."
            ),
            "poll_behavior": (
                "POST /v1/agent-protocol/poll is a lightweight protocol-state "
                "refresh instruction. It does not grant capabilities and is "
                "not a second lifecycle state machine."
            ),
            "format": (
                "The context response contains repository capabilities, "
                "allowed_actions, blocked_actions, and next_recommended_action."
            ),
        },

        repository_instructions={
            "source_of_truth": (
                "Use GET /v1/agent/context to discover repositories and "
                "capabilities currently available to this AgentSession."
            ),
            "authorization": (
                "Repository access is granted by a human-authorized control "
                "plane operation. Agents cannot grant themselves repository access."
            ),
            "operation_rule": (
                "Do not call a human-only repository management endpoint using "
                "an AgentSession token."
            ),
        },

        knowledge_graph_instructions={
            "availability": (
                "Knowledge Graph access is available through its dedicated "
                "agent-authorized endpoints when the required capability exists."
            ),
            "requirements": (
                "Active AgentSession plus the relevant repository/read "
                "authorization required by the Knowledge Graph endpoint."
            ),
            "instruction": (
                "Use Knowledge Graph information when exposed by the current "
                "agent context before unnecessary broad repository exploration."
            ),
        },

        git_instructions={
            "provider_rule": (
                "Git transport depends on the configured repository provider. "
                "Do not assume that local SUTRA Git transport and GitHub transport "
                "use identical credentials."
            ),
            "authorization_rule": (
                "Git operations remain subject to the AgentSession and "
                "repository capability boundaries."
            ),
            "local_provider": {
                "clone_url": "/git/{owner}/{repo}.git",
                "authentication_mechanism": (
                    "SUTRA Git Smart HTTP with the credentials documented for "
                    "the configured local repository provider."
                ),
            },
            "github_provider": {
                "authentication_mechanism": (
                    "SUTRA-authorized downstream GitHub credentials issued by "
                    "the provider credential broker."
                ),
                "scope": (
                    "Downstream credentials are limited to the authorized "
                    "repository and requested provider capability."
                ),
            },
        },

        error_handling={
            "principle": (
                "Use structured SUTRA denial information when available. "
                "Never infer that a denied operation becomes authorized merely "
                "because it can be retried."
            ),
            "401": (
                "Authentication/session failure. Check session validity and "
                "establish a new session only when the permanent agent credential "
                "remains valid."
            ),
            "403": (
                "Authenticated but forbidden. The agent lacks required authority, "
                "capability, or lifecycle permission."
            ),
            "404": (
                "Resource unavailable or intentionally hidden because the caller "
                "is not authorized to know whether it exists."
            ),
            "409": (
                "State or concurrency conflict, such as a stale head or invalid "
                "state transition. Refresh context/state before retrying."
            ),
            "422": (
                "Request validation failure or unmet business/lifecycle "
                "requirements."
            ),
        },
    )


# ---------------------------------------------------------------------------
# PROTOCOL POLL
# ---------------------------------------------------------------------------

class AgentInstructionResponse(BaseModel):
    protocol: str
    protocol_version: str
    instruction_id: str
    instruction_type: str
    sequence: int
    required: bool
    action: str
    reason: str
    parameters: dict
    expected_result: str
    next_action: str | None


@router.post(
    "/poll",
    response_model=AgentInstructionResponse,
)
def agent_poll(
    session: AgentSession = Depends(get_current_agent_session),
):
    """
    Lightweight protocol refresh.

    This endpoint intentionally does NOT calculate or grant capability.
    The authoritative dynamic workflow state is exposed by:
        GET /v1/agent/context

    Keeping poll lightweight prevents it from becoming a competing
    lifecycle state machine.
    """

    return AgentInstructionResponse(
        protocol="sutra-agent",
        protocol_version="1",
        instruction_id=f"context-refresh-{session.id}",
        instruction_type="state_refresh",
        sequence=1,
        required=False,
        action="get_context",
        reason=(
            "Refresh authoritative SUTRA state before selecting the next "
            "engineering operation."
        ),
        parameters={
            "endpoint": "/v1/agent/context",
            "method": "GET",
        },
        expected_result=(
            "Current identity, session timing, repository access, capabilities, "
            "lifecycle state, allowed actions, blocked actions, and the "
            "recommended next action."
        ),
        next_action="read_next_recommended_action",
    )