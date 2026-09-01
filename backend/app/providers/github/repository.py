import base64
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import httpx
import logging

from app.providers.base import (
    RepositoryProvider,
    ProviderRepoMetadata,
    ProviderBranch,
    ProviderCommit,
    ProviderDiffStat,
    ProviderPullRequest,
    ProviderMergeResult,
)
from app.providers.github.auth import GitHubAppAuthService

logger = logging.getLogger("sutra.providers.github.repo")


class GitHubRepositoryProvider(RepositoryProvider):
    """
    Substrate implementation of RepositoryProvider targeting GitHub REST API v3.
    Uses GitHub App authentication to execute repository and PR operations.
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

    def _get_app_headers(self) -> Dict[str, str]:
        jwt_token = self.auth_service.generate_app_jwt()
        return {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get_installation_headers(self, owner: str, name: str) -> Dict[str, str]:
        inst_id = self.auth_service.get_installation_id(owner, name)
        token_data = self.auth_service.create_installation_token(
            installation_id=inst_id,
            repositories=[name],
            permissions={"contents": "write", "pull_requests": "write", "metadata": "read"},
        )
        return {
            "Authorization": f"Bearer {token_data['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_repository_metadata(self, owner: str, name: str) -> ProviderRepoMetadata:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}", headers=headers)
        res.raise_for_status()
        data = res.json()

        # Capability detection: rulesets vs classic branch protection
        plan_name = data.get("plan", {}).get("name", "free").lower() if data.get("plan") else "free"
        is_private = data.get("private", True)
        
        # GitHub allows full rulesets on public repos or paid org plans
        supports_rulesets = not is_private or plan_name in {"team", "enterprise", "business"}

        return ProviderRepoMetadata(
            provider_type="github",
            owner=owner,
            name=name,
            default_branch=data.get("default_branch", "main"),
            is_private=is_private,
            clone_url=data.get("clone_url", f"https://github.com/{owner}/{name}.git"),
            external_id=str(data.get("id")),
            capabilities={
                "rulesets": supports_rulesets,
                "classic_branch_protection": True,
                "check_runs": True,
                "pre_receive_hook": False,
            },
        )

    def get_branch(self, owner: str, name: str, branch: str) -> Optional[ProviderBranch]:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}/branches/{branch}", headers=headers)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        data = res.json()
        return ProviderBranch(
            name=data["name"],
            commit_sha=data["commit"]["sha"],
            is_protected=data.get("protected", False),
        )

    def list_branches(self, owner: str, name: str) -> List[ProviderBranch]:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}/branches", headers=headers)
        res.raise_for_status()
        data = res.json()
        return [
            ProviderBranch(
                name=b["name"],
                commit_sha=b["commit"]["sha"],
                is_protected=b.get("protected", False),
            )
            for b in data
        ]

    def get_commit(self, owner: str, name: str, sha: str) -> Optional[ProviderCommit]:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}/commits/{sha}", headers=headers)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        data = res.json()

        author_name = data.get("commit", {}).get("author", {}).get("name", "Unknown")
        author_email = data.get("commit", {}).get("author", {}).get("email", "")
        committed_date_str = data.get("commit", {}).get("author", {}).get("date")
        
        try:
            c_date = datetime.fromisoformat(committed_date_str.replace("Z", "+00:00")) if committed_date_str else datetime.now(timezone.utc)
        except Exception:
            c_date = datetime.now(timezone.utc)

        parents = [p["sha"] for p in data.get("parents", [])]
        tree_sha = data.get("commit", {}).get("tree", {}).get("sha", "")

        return ProviderCommit(
            sha=data["sha"],
            message=data.get("commit", {}).get("message", ""),
            author_name=author_name,
            author_email=author_email,
            committed_at=c_date,
            parent_shas=parents,
            tree_sha=tree_sha,
        )

    def commit_exists(self, owner: str, name: str, sha: str) -> bool:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}/commits/{sha}", headers=headers)
        return res.status_code == 200

    def get_diff_stats(self, owner: str, name: str, base: str, head: str) -> ProviderDiffStat:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}/compare/{base}...{head}", headers=headers)
        res.raise_for_status()
        data = res.json()

        files_data = data.get("files", [])
        additions = 0
        deletions = 0
        changed_files = []

        for f in files_data:
            adds = f.get("additions", 0)
            dels = f.get("deletions", 0)
            additions += adds
            deletions += dels
            changed_files.append({
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": adds,
                "deletions": dels,
            })

        return ProviderDiffStat(
            files_changed=len(files_data),
            additions=additions,
            deletions=deletions,
            changed_files=changed_files,
        )

    def read_file(self, owner: str, name: str, path: str, ref: str) -> bytes:
        headers = self._get_installation_headers(owner, name)
        clean_path = path.lstrip("/")
        res = self._client.get(f"/repos/{owner}/{name}/contents/{clean_path}?ref={ref}", headers=headers)
        res.raise_for_status()
        data = res.json()
        if data.get("encoding") == "base64" and "content" in data:
            return base64.b64decode(data["content"])
        raise ValueError(f"Unexpected content payload encoding for '{path}'")

    def list_files(self, owner: str, name: str, path: str, ref: str) -> List[Dict[str, Any]]:
        headers = self._get_installation_headers(owner, name)
        clean_path = path.lstrip("/")
        url = f"/repos/{owner}/{name}/contents/{clean_path}?ref={ref}" if clean_path else f"/repos/{owner}/{name}/contents?ref={ref}"
        res = self._client.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        items = []
        if isinstance(data, list):
            for item in data:
                items.append({
                    "name": item.get("name"),
                    "type": "dir" if item.get("type") == "dir" else "file",
                    "sha": item.get("sha"),
                    "path": item.get("path"),
                    "size": item.get("size", 0),
                })
        return items

    def create_pull_request(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> ProviderPullRequest:
        headers = self._get_installation_headers(owner, name)
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }
        res = self._client.post(f"/repos/{owner}/{name}/pulls", headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        return ProviderPullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            head_ref=data["head"]["ref"],
            head_sha=data["head"]["sha"],
            base_ref=data["base"]["ref"],
            base_sha=data["base"]["sha"],
            is_merged=data.get("merged", False),
            is_closed=data.get("state") == "closed",
            mergeable=data.get("mergeable"),
            html_url=data.get("html_url", ""),
        )

    def get_pull_request(self, owner: str, name: str, pr_number: int) -> Optional[ProviderPullRequest]:
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}/pulls/{pr_number}", headers=headers)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        data = res.json()
        return ProviderPullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            head_ref=data["head"]["ref"],
            head_sha=data["head"]["sha"],
            base_ref=data["base"]["ref"],
            base_sha=data["base"]["sha"],
            is_merged=data.get("merged", False),
            is_closed=data.get("state") == "closed",
            mergeable=data.get("mergeable"),
            html_url=data.get("html_url", ""),
        )

    def merge_pull_request(
        self,
        owner: str,
        name: str,
        pr_number: int,
        commit_title: str,
        commit_message: str,
        expected_head_sha: str,
        method: str = "squash",
    ) -> ProviderMergeResult:
        headers = self._get_installation_headers(owner, name)
        payload = {
            "commit_title": commit_title,
            "commit_message": commit_message,
            "sha": expected_head_sha,  # Optimistic concurrency check
            "merge_method": method,
        }
        res = self._client.put(f"/repos/{owner}/{name}/pulls/{pr_number}/merge", headers=headers, json=payload)
        
        if res.status_code == 200:
            data = res.json()
            return ProviderMergeResult(
                success=True,
                merge_commit_sha=data.get("sha"),
                message=data.get("message", "Merged successfully"),
            )
        elif res.status_code == 409:
            return ProviderMergeResult(
                success=False,
                merge_commit_sha=None,
                message=f"Merge conflict or SHA mismatch on GitHub (HTTP 409): {res.text}",
            )
        elif res.status_code == 405:
            return ProviderMergeResult(
                success=False,
                merge_commit_sha=None,
                message=f"Pull request not mergeable or branch protection blocked merge (HTTP 405): {res.text}",
            )
        else:
            return ProviderMergeResult(
                success=False,
                merge_commit_sha=None,
                message=f"GitHub merge failed with HTTP {res.status_code}: {res.text}",
            )
