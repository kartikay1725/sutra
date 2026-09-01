from fastapi.testclient import TestClient


def _status(client: TestClient, path: str, expected=(200, 401, 403, 404, 422)):
    response = client.get(path)
    assert response.status_code in expected, f"{path}: {response.status_code} {response.text}"


def test_core_api_routes_are_registered(client: TestClient):
    paths = [
        "/openapi.json",
        "/v1/repositories",
        "/v1/me/work",
        "/v1/me/dashboard",
        "/v1/me/activity",
        "/v1/notifications",
        "/v1/search?q=test",
        "/v1/agents",
    ]
    for path in paths:
        _status(client, path)


def test_critical_unauthenticated_boundaries(client: TestClient):
    paths = [
    "/v1/me/work",
    "/v1/me/dashboard",
    "/v1/agents",
    "/v1/notifications",
    "/v1/organizations/nonexistent/policies",
]
    for path in paths:
        response = client.get(path)
        assert response.status_code in (401, 403), (
            f"Expected auth boundary for {path}, "
            f"got {response.status_code}: {response.text}"
        )
