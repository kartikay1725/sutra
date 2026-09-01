from typing import Optional, Dict, Any
import httpx
import logging

from app.providers.checks import (
    CheckProvider,
    CheckRunReport,
    CheckStatus,
    CheckConclusion,
)
from app.providers.github.auth import GitHubAppAuthService

logger = logging.getLogger("sutra.providers.github.checks")


class GitHubCheckProvider(CheckProvider):
    """
    Substrate implementation of CheckProvider targeting GitHub Check Runs API.
    Publishes and updates status checks reflecting SUTRA policy decisions.
    """

    def __init__(
        self,
        auth_service: GitHubAppAuthService,
        base_url: str = "https://api.github.com",
        client: Optional[httpx.Client] = None,
    ):
        self.auth_service = auth_service
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(base_url=self.base_url, timeout=15.0)

    def _get_headers(self, owner: str, name: str) -> Dict[str, str]:
        inst_id = self.auth_service.get_installation_id(owner, name)
        token_data = self.auth_service.create_installation_token(
            installation_id=inst_id,
            repositories=[name],
            permissions={"checks": "write", "metadata": "read"},
        )
        return {
            "Authorization": f"Bearer {token_data['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def report_check_run(
        self,
        owner: str,
        name: str,
        report: CheckRunReport,
    ) -> str:
        headers = self._get_headers(owner, name)
        body: Dict[str, Any] = {
            "name": report.check_name,
            "head_sha": report.head_sha,
            "status": report.status.value,
            "external_id": report.external_id,
            "details_url": report.details_url,
            "output": {
                "title": report.title,
                "summary": report.summary,
            },
        }
        if report.conclusion:
            body["conclusion"] = report.conclusion.value

        res = self._client.post(f"/repos/{owner}/{name}/check-runs", headers=headers, json=body)
        res.raise_for_status()
        data = res.json()
        return str(data.get("id"))
