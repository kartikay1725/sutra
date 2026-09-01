import secrets

from fastapi.testclient import TestClient

from app.main import app

from .test_agent_adversarial import (
    _agent_headers,
    _fresh_username,
    _make_agent,
    _make_session,
    _register_login,
)


def _new_agent_session(name: str = "ProtocolTest") -> tuple[str, str, str]:
    """
    Create an isolated human owner + agent + AgentSession.

    Returns:
        (jwt, agent_id, session_token)
    """
    user = _fresh_username()
    jwt = _register_login(user)
    agent_id, agent_token = _make_agent(jwt, name)
    session_token = _make_session(agent_token)
    return jwt, agent_id, session_token


def test_agent_protocol_handshake():
    with TestClient(app) as client:
        response = client.post(
            "/v1/agent-protocol/handshake",
            json={
                "protocol": "sutra-agent",
                "protocol_version": "1",
                "client_name": "test-agent",
                "client_type": "automated",
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["protocol"] == "sutra-agent"
        assert data["protocol_version"] == "1"

        assert "workflow" in data
        assert "session_instructions" in data
        assert "capability_instructions" in data
        assert "repository_instructions" in data
        assert "knowledge_graph_instructions" in data
        assert "git_instructions" in data
        assert "error_handling" in data


def test_agent_protocol_handshake_rejects_unknown_protocol():
    with TestClient(app) as client:
        response = client.post(
            "/v1/agent-protocol/handshake",
            json={
                "protocol": "unknown-agent",
                "protocol_version": "1",
                "client_name": "test",
                "client_type": "bot",
            },
        )

        assert response.status_code == 400


def test_agent_protocol_handshake_rejects_unknown_version():
    with TestClient(app) as client:
        response = client.post(
            "/v1/agent-protocol/handshake",
            json={
                "protocol": "sutra-agent",
                "protocol_version": "2",
                "client_name": "test",
                "client_type": "bot",
            },
        )

        assert response.status_code == 400


def test_agent_protocol_poll_unauthenticated():
    with TestClient(app) as client:
        response = client.post("/v1/agent-protocol/poll")

        assert response.status_code == 401


def test_agent_protocol_poll_authenticated():
    """
    Poll is now a lightweight protocol refresh operation.

    It must not act as a second lifecycle/state machine.
    """
    _, _, session_token = _new_agent_session("PollTest")

    with TestClient(app) as client:
        response = client.post(
            "/v1/agent-protocol/poll",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["protocol"] == "sutra-agent"
        assert data["protocol_version"] == "1"

        assert data["action"] == "get_context"
        assert data["parameters"]["endpoint"] == "/v1/agent/context"
        assert data["parameters"]["method"] == "GET"

        assert data["instruction_type"] == "state_refresh"

        assert "Current identity" in data["expected_result"]


def test_context_does_not_advertise_human_repository_listing():
    """
    /v1/repositories is a human-owner endpoint.

    An agent's context must never advertise it as a legal agent action.
    """
    _, _, session_token = _new_agent_session("ContextRepoTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        endpoints = {
            action["endpoint"]
            for action in data["allowed_actions"]
        }

        assert "/v1/repositories" not in endpoints

        # The agent should discover its repository state from context.
        assert "repository_access" in data


def test_context_uses_agent_change_endpoint():
    """
    Agent Change creation must advertise /v1/changes/agent,
    not the human /v1/changes endpoint.
    """
    _, _, session_token = _new_agent_session("ContextChangeTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        actions = data["allowed_actions"]

        create_change = next(
            (
                action
                for action in actions
                if action["name"] == "create_change"
            ),
            None,
        )

        # A brand-new agent may not have change.create yet.
        # In that case the capability is correctly unavailable.
        if create_change is None:
            assert any(
                blocked.get("reason") == "REPOSITORY_ACCESS_REQUIRED"
                for blocked in data["blocked_actions"]
                if isinstance(blocked, dict)
            )
            return

        assert create_change["method"] == "POST"
        assert create_change["endpoint"] == "/v1/changes/agent"


def test_context_uses_agent_pull_request_endpoint():
    """
    Agent PR creation must advertise /v1/pull-requests/agent,
    not the human /v1/pull-requests endpoint.
    """
    _, _, session_token = _new_agent_session("ContextPRTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        actions = data["allowed_actions"]

        create_pr = next(
            (
                action
                for action in actions
                if action["name"] == "create_pull_request"
            ),
            None,
        )

        # A brand-new agent may not have repository.write yet.
        if create_pr is None:
            assert any(
                blocked.get("reason") == "REPOSITORY_ACCESS_REQUIRED"
                for blocked in data["blocked_actions"]
                if isinstance(blocked, dict)
            )
            return

        assert create_pr["method"] == "POST"
        assert create_pr["endpoint"] == "/v1/pull-requests/agent"


def test_context_advertises_agent_commit_and_finalize_endpoints():
    """
    When change capabilities are present, context must expose the
    actual agent-only Change endpoints.
    """
    _, _, session_token = _new_agent_session("ContextCommitTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        action_map = {
            action["name"]: action
            for action in data["allowed_actions"]
        }

        # These may not yet be legal for a fresh agent. The important
        # invariant is that, when advertised, the endpoint is correct.
        if "attach_commit" in action_map:
            assert action_map["attach_commit"]["method"] == "POST"
            assert (
                action_map["attach_commit"]["endpoint"]
                == "/v1/changes/{id}/agent-commit"
            )

        if "finalize_change" in action_map:
            assert action_map["finalize_change"]["method"] == "POST"
            assert (
                action_map["finalize_change"]["endpoint"]
                == "/v1/changes/{id}/agent-finalize"
            )


def test_context_always_blocks_agent_merge_and_approval():
    """
    Human approval and merge remain outside the agent's authority.
    """
    _, _, session_token = _new_agent_session("ContextSecurityTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        blocked = data["blocked_actions"]

        blocked_by_name = {
            item["action"]: item
            for item in blocked
            if isinstance(item, dict) and "action" in item
        }

        assert "merge_pull_request" in blocked_by_name
        assert "approve_pull_request" in blocked_by_name

        assert blocked_by_name["merge_pull_request"]["reason"] == (
            "HUMAN_APPROVAL_REQUIRED"
        )

        assert blocked_by_name["approve_pull_request"]["reason"] == (
            "AGENT_ACTION_FORBIDDEN"
        )


def test_context_exposes_authoritative_session_state():
    """
    Context must expose enough session information for a fresh agent
    to understand its current authentication lifetime.
    """
    _, agent_id, session_token = _new_agent_session("ContextStateTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["identity"]["agent_id"] == agent_id
        assert data["identity"]["status"] == "active"

        session = data["session"]

        assert session["session_id"]
        assert session["expires_at"]
        assert session["idle_timeout_seconds"] > 0
        assert session["absolute_ttl_minutes"] > 0


def test_context_no_repository_access_recommends_waiting_for_grant():
    """
    A fresh agent with no repository grant must be told to wait for
    human repository authorization rather than attempt repository work.
    """
    _, _, session_token = _new_agent_session("NoRepoContextTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["repository_access"] == []

        next_action = data["next_recommended_action"]

        assert next_action is not None
        assert next_action["name"] == "wait_for_repository_access"
        assert next_action["method"] == "GET"
        assert next_action["endpoint"] == "/v1/agent/context"


def test_context_has_single_discover_protocol_action():
    """
    The protocol handshake is discoverable, but must not be confused with
    a separate authorization mechanism.
    """
    _, _, session_token = _new_agent_session("ProtocolDiscoveryTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        actions = [
            action
            for action in response.json()["allowed_actions"]
            if action["name"] == "discover_protocol"
        ]

        assert len(actions) == 1

        assert actions[0]["method"] == "POST"
        assert actions[0]["endpoint"] == "/v1/agent-protocol/handshake"


def test_context_does_not_expose_human_only_change_or_pr_routes():
    """
    Context must never expose the human endpoints as agent operations.
    """
    _, _, session_token = _new_agent_session("ContextEndpointIsolationTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        actions = response.json()["allowed_actions"]

        endpoints = {action["endpoint"] for action in actions}

        assert "/v1/changes" not in endpoints
        assert "/v1/pull-requests" not in endpoints


def test_context_response_is_machine_readable():
    """
    Basic schema-level check for the agent contract.
    """
    _, _, session_token = _new_agent_session("MachineReadableTest")

    with TestClient(app) as client:
        response = client.get(
            "/v1/agent/context",
            headers=_agent_headers(session_token),
        )

        assert response.status_code == 200

        data = response.json()

        required_top_level = {
            "protocol_version",
            "identity",
            "session",
            "repository_access",
            "current_lifecycle",
            "allowed_actions",
            "blocked_actions",
            "next_recommended_action",
        }

        assert required_top_level.issubset(data.keys())

        assert isinstance(data["allowed_actions"], list)
        assert isinstance(data["blocked_actions"], list)
        assert isinstance(data["repository_access"], list)