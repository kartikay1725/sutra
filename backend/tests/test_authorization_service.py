import json

from app.models.repository import Repository
from app.services.authorization_service import AuthorizationService


class Obj:
    pass


def make_repository():
    repository = Obj()
    repository.id = "repo-1"
    repository.owner_id = "owner-1"
    return repository


def make_actor(
    capabilities,
    *,
    owner_id="owner-1",
    actor_type="agent",
):
    actor = Obj()
    actor.id = "agent-1"
    actor.type = actor_type
    actor.owner_id = owner_id
    actor.capabilities = json.dumps(capabilities)
    return actor


def test_repository_read_is_allowed():
    decision = AuthorizationService.check(
        make_actor([AuthorizationService.READ]),
        make_repository(),
        AuthorizationService.READ,
    )
    assert decision.allowed is True


def test_repository_write_is_allowed():
    decision = AuthorizationService.check(
        make_actor([AuthorizationService.WRITE]),
        make_repository(),
        AuthorizationService.WRITE,
    )
    assert decision.allowed is True


def test_missing_capability_is_denied():
    decision = AuthorizationService.check(
        make_actor([AuthorizationService.READ]),
        make_repository(),
        AuthorizationService.WRITE,
    )
    assert decision.allowed is False
    assert decision.capability == "repository.write"
    assert "repository.write" in decision.reason


def test_cross_owner_access_is_denied():
    decision = AuthorizationService.check(
        make_actor(
            [AuthorizationService.READ, AuthorizationService.WRITE],
            owner_id="owner-2",
        ),
        make_repository(),
        AuthorizationService.READ,
    )
    assert decision.allowed is False
    assert "does not own" in decision.reason


def test_non_agent_actor_is_denied():
    decision = AuthorizationService.check(
        make_actor(
            [AuthorizationService.READ],
            actor_type="unsupported",
        ),
        make_repository(),
        AuthorizationService.READ,
    )
    assert decision.allowed is False
    assert "Unsupported actor type" in decision.reason


def test_invalid_capabilities_json_denies_access():
    actor = make_actor([AuthorizationService.READ])
    actor.capabilities = "{invalid-json"
    decision = AuthorizationService.check(
        actor,
        make_repository(),
        AuthorizationService.READ,
    )
    assert decision.allowed is False


def test_non_list_capabilities_denies_access():
    actor = make_actor([AuthorizationService.READ])
    actor.capabilities = json.dumps({"repository.read": True})
    decision = AuthorizationService.check(
        actor,
        make_repository(),
        AuthorizationService.READ,
    )
    assert decision.allowed is False


def test_require_succeeds_when_authorized():
    AuthorizationService.require(
        make_actor([AuthorizationService.WRITE]),
        make_repository(),
        AuthorizationService.WRITE,
    )


def test_require_raises_when_denied():
    try:
        AuthorizationService.require(
            make_actor([AuthorizationService.READ]),
            make_repository(),
            AuthorizationService.WRITE,
        )
    except PermissionError as exc:
        assert "repository.write" in str(exc)
    else:
        raise AssertionError("Expected PermissionError")
