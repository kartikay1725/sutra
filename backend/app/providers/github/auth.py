from _pytest import fixtures
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import jwt
import httpx
import logging

logger = logging.getLogger("sutra.providers.github.auth")


class GitHubAppAuthService:
    """
    Handles GitHub App JWT generation, installation resolution,
    and scoped installation token negotiation.
    """

    def __init__(
        self,
        app_id: str,
        private_key_pem: str,
        base_url: str = "https://api.github.com",
        client: Optional[httpx.Client] = None,
    ):
        self.app_id = str(app_id).strip()
        self.private_key_pem = private_key_pem.strip()
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self.base_url, timeout=15.0)

    def generate_app_jwt(self, ttl_seconds: int = 540) -> str:
        """
        Generate RS256 JWT for GitHub App authentication.
        GitHub maximum JWT lifetime is 10 minutes (600 seconds).
        We use 9 minutes (540s) with 60s clock drift buffer.
        """
        if not self.app_id or not self.private_key_pem:
            raise ValueError("GitHub App ID and private key PEM must be configured")

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + min(ttl_seconds, 540),
            "iss": self.app_id,
        }
        # Never log private_key_pem or the resulting JWT
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    def get_installation_id(self, owner: str, repo: str) -> int:
        """
        Query GitHub for the App installation ID for a given repository.
        """
        jwt_token = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"/repos/{owner}/{repo}/installation"
        res = self._client.get(url, headers=headers)
        if res.status_code == 404:
            raise ValueError(f"GitHub App is not installed on repository '{owner}/{repo}'")
        res.raise_for_status()
        return res.json()["id"]

    def create_installation_token(
        self,
        installation_id: int,
        repositories: List[str],
        permissions: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Negotiate an installation access token scoped to specific repositories and permissions.
        Note: GitHub natively sets expires_at to +1 hour. SUTRA enforces effective TTL <= 10 min.
        """
        jwt_token = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        body: Dict[str, Any] = {
            "permissions": permissions,
        }
        if repositories:
            body["repositories"] = repositories

        url = f"/app/installations/{installation_id}/access_tokens"
        res = self._client.post(
            url,
            headers=headers,
            json=body,
        )

        if res.status_code >= 400:
            raise RuntimeError(
                "GitHub installation token request failed: "
                f"HTTP {res.status_code} - {res.text}"
            )

        data = res.json()
        data = res.json()
        return {
            "token": data["token"],
            "expires_at": data["expires_at"],
            "permissions": data.get("permissions", permissions),
            "repositories": [r["name"] if isinstance(r, dict) else r for r in data.get("repositories", repositories)],
        }

    def revoke_installation_token(self, token: str) -> bool:
        """
        Revoke an installation token immediately on GitHub's API.
        """
        if not token:
            return False
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            res = self._client.delete("/installation/token", headers=headers)
            return res.status_code in {204, 200}
        except Exception as e:
            logger.warning(f"Failed to revoke installation token on GitHub: {e}")
            return False
