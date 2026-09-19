from urllib import response
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
    ProviderIssue,
    ProviderIssueComment,
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

    def _get_installation_headers(self, owner: str, name: str, installation_id: Optional[int] = None) -> Dict[str, str]:
        inst_id = installation_id or (
            self.auth_service.get_installation_id_cached(owner, name)
            if hasattr(self.auth_service, "get_installation_id_cached")
            else self.auth_service.get_installation_id(owner, name)
        )
        if hasattr(self.auth_service, "create_installation_token_cached"):
            token_data = self.auth_service.create_installation_token_cached(
                installation_id=inst_id,
                repositories=[name],
                permissions={"contents": "write", "pull_requests": "write", "checks": "write", "metadata": "read", "workflows": "write"},
            )
        else:
            token_data = self.auth_service.create_installation_token(
                installation_id=inst_id,
                repositories=[name],
                permissions={"contents": "write", "pull_requests": "write", "checks": "write", "metadata": "read", "workflows": "write"},
            )
        return {
            "Authorization": f"Bearer {token_data['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get_issue_headers(
        self,
        owner: str,
        name: str,
        installation_id: Optional[int] = None,
    ) -> Dict[str, str]:
        inst_id = installation_id or (
            self.auth_service.get_installation_id_cached(owner, name)
            if hasattr(self.auth_service, "get_installation_id_cached")
            else self.auth_service.get_installation_id(owner, name)
        )
        if hasattr(self.auth_service, "create_installation_token_cached"):
            token_data = self.auth_service.create_installation_token_cached(
                installation_id=inst_id,
                repositories=[name],
                permissions={
                    "issues": "write",
                    "metadata": "read",
                },
            )
        else:
            token_data = self.auth_service.create_installation_token(
                installation_id=inst_id,
                repositories=[name],
                permissions={
                    "issues": "write",
                    "metadata": "read",
                },
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

    def get_raw_repository(self, owner: str, name: str) -> Dict[str, Any]:
        """Fetch raw GitHub repository details including fork, parent, and permissions."""
        headers = self._get_installation_headers(owner, name)
        res = self._client.get(f"/repos/{owner}/{name}", headers=headers)
        res.raise_for_status()
        return res.json()

    def create_fork(
        self,
        owner: str,
        name: str,
        organization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a fork of an upstream repository on GitHub."""
        headers = self._get_installation_headers(owner, name)
        url = f"/repos/{owner}/{name}/forks"
        payload = {}
        if organization:
            payload["organization"] = organization
        res = self._client.post(url, headers=headers, json=payload if payload else None)
        res.raise_for_status()
        return res.json()

    def update_repository(
        self,
        owner: str,
        name: str,
        *,
        new_name: Optional[str] = None,
        description: Optional[str] = None,
        default_branch: Optional[str] = None,
        is_private: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update repository settings on GitHub."""
        headers = self._get_installation_headers(owner, name)
        payload: Dict[str, Any] = {}
        if new_name is not None and new_name.strip() and new_name.strip() != name:
            payload["name"] = new_name.strip()
        if description is not None:
            payload["description"] = description
        if default_branch is not None and default_branch.strip():
            payload["default_branch"] = default_branch.strip()
        if is_private is not None:
            payload["private"] = is_private

        if not payload:
            return {}

        res = self._client.patch(f"/repos/{owner}/{name}", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    def delete_repository(
        self,
        owner: str,
        name: str,
    ) -> bool:
        """Delete repository on GitHub if authorized."""
        headers = self._get_installation_headers(owner, name)
        res = self._client.delete(f"/repos/{owner}/{name}", headers=headers)
        if res.status_code in (204, 200, 404):
            return True
        res.raise_for_status()
        return True

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
    def list_commits(
        self,
        owner: str,
        name: str,
        ref: str,
        limit: int = 30,
    ) -> List[ProviderCommit]:
        headers = self._get_installation_headers(owner, name)

        safe_limit = max(1, min(int(limit), 100))

        res = self._client.get(
            f"/repos/{owner}/{name}/commits",
            headers=headers,
            params={
                "sha": ref,
                "per_page": safe_limit,
            },
        )
        res.raise_for_status()

        data = res.json()

        commits: List[ProviderCommit] = []

        for item in data:
            commit_data = item.get("commit", {})

            author = commit_data.get("author") or {}
            author_name = author.get("name", "Unknown")
            author_email = author.get("email", "")
            committed_date_str = author.get("date")

            try:
                committed_at = (
                    datetime.fromisoformat(
                        committed_date_str.replace("Z", "+00:00")
                    )
                    if committed_date_str
                    else datetime.now(timezone.utc)
                )
            except Exception:
                committed_at = datetime.now(timezone.utc)

            parents = [
                parent.get("sha")
                for parent in item.get("parents", [])
                if parent.get("sha")
            ]

            tree_sha = (
                commit_data.get("tree", {}).get("sha", "")
            )

            commits.append(
                ProviderCommit(
                    sha=item["sha"],
                    message=commit_data.get("message", ""),
                    author_name=author_name,
                    author_email=author_email,
                    committed_at=committed_at,
                    parent_shas=parents,
                    tree_sha=tree_sha,
                )
            )

        return commits

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
    def get_commit_detail(
        self,
        owner: str,
        name: str,
        sha: str,
    ) -> dict[str, Any]:
        headers = self._get_installation_headers(owner, name)

        res = self._client.get(
            f"/repos/{owner}/{name}/commits/{sha}",
            headers=headers,
        )

        if res.status_code == 404:
            raise ValueError("Commit not found")

        res.raise_for_status()
        return res.json()
    def get_file_blame(
        self,
        owner: str,
        name: str,
        path: str,
        ref: str,
    ) -> List[Dict[str, Any]]:
        """
        Return GitHub blame ranges for a file at a specific branch/ref.

        Each range identifies:
        - starting_line
        - ending_line
        - responsible commit
        - commit author
        - authored date
        - commit subject
        """

        # GitHub's REST API does not provide a direct blame endpoint.
        # Use the GraphQL API with the same GitHub App installation token.
        headers = self._get_installation_headers(owner, name)

        query = """
        query FileBlame(
            $owner: String!,
            $name: String!,
            $ref: String!,
            $path: String!
        ) {
            repository(owner: $owner, name: $name) {
                ref(qualifiedName: $ref) {
                    target {
                        ... on Commit {
                            oid
                            blame(path: $path) {
                                ranges {
                                    startingLine
                                    endingLine
                                    age
                                    commit {
                                        oid
                                        abbreviatedOid
                                        messageHeadline
                                        authoredDate
                                        author {
                                            name
                                            email
                                            user {
                                                login
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = self._client.post(
            "/graphql",
            headers=headers,
            json={
                "query": query,
                "variables": {
                    "owner": owner,
                    "name": name,
                    "ref": (
                        ref
                        if ref.startswith("refs/")
                        else f"refs/heads/{ref}"
                    ),
                    "path": path.lstrip("/"),
                },
            },
        )

        response.raise_for_status()

        payload = response.json()

        # GraphQL can return HTTP 200 with an errors array.
        errors = payload.get("errors") or []
        if errors:
            message = errors[0].get(
                "message",
                "GitHub GraphQL blame request failed",
            )
            raise ValueError(message)

        repository = payload.get("data", {}).get("repository")
        if not repository:
            raise ValueError("GitHub repository not found")

        ref_data = repository.get("ref")
        if not ref_data:
            raise ValueError(
                f"GitHub branch/ref '{ref}' not found"
            )

        target = ref_data.get("target")
        if not target:
            raise ValueError(
                f"GitHub ref '{ref}' has no commit target"
            )

        blame = target.get("blame")
        if not blame:
            return []

        ranges: List[Dict[str, Any]] = []

        for item in blame.get("ranges", []):
            commit = item.get("commit") or {}
            author = commit.get("author") or {}
            user = author.get("user") or {}

            ranges.append(
                {
                    "start_line": item.get("startingLine"),
                    "end_line": item.get("endingLine"),
                    "age": item.get("age"),
                    "commit": commit.get("oid"),
                    "short_commit": commit.get(
                        "abbreviatedOid"
                    ),
                    "subject": commit.get(
                        "messageHeadline",
                        "",
                    ),
                    "author_name": author.get(
                        "name",
                        "Unknown",
                    ),
                    "author_email": author.get(
                        "email",
                        "",
                    ),
                    "github_login": user.get("login"),
                    "authored_at": commit.get(
                        "authoredDate"
                    ),
                }
            )

        return ranges
        # ============================================================
    # GITHUB ISSUES
    # ============================================================

    def list_issues(
        self,
        owner: str,
        name: str,
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
        installation_id: Optional[int] = None,
    ) -> List[ProviderIssue]:
        headers = self._get_issue_headers(owner, name, installation_id=installation_id)

        safe_state = state if state in {"open", "closed", "all"} else "all"
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))

        # GitHub pagination is page-based.
        page = (safe_offset // safe_limit) + 1

        response = self._client.get(
            f"/repos/{owner}/{name}/issues",
            headers=headers,
            params={
                "state": safe_state,
                "per_page": safe_limit,
                "page": page,
            },
        )

        response.raise_for_status()

        data = response.json()

        # GitHub's Issues endpoint can also return pull requests.
        # SUTRA's Issues view should contain actual issues only.
        issues: List[ProviderIssue] = []

        for item in data:
            if "pull_request" in item:
                continue

            issues.append(
                self._map_github_issue(item)
            )

        return issues


    def get_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> Optional[ProviderIssue]:
        headers = self._get_issue_headers(owner, name)

        response = self._client.get(
            f"/repos/{owner}/{name}/issues/{issue_number}",
            headers=headers,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()

        # Defensive check: issue endpoint should not normally return a PR,
        # but GitHub represents PRs through the issues API.
        if "pull_request" in data:
            return None

        return self._map_github_issue(data)


    def create_issue(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
    ) -> ProviderIssue:
        headers = self._get_issue_headers(owner, name)

        response = self._client.post(
            f"/repos/{owner}/{name}/issues",
            headers=headers,
            json={
                "title": title,
                "body": body,
            },
        )

        response.raise_for_status()

        return self._map_github_issue(response.json())


    def list_issue_comments(
        self,
        owner: str,
        name: str,
        issue_number: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProviderIssueComment]:
        headers = self._get_issue_headers(owner, name)

        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))

        page = (safe_offset // safe_limit) + 1

        response = self._client.get(
            f"/repos/{owner}/{name}/issues/{issue_number}/comments",
            headers=headers,
            params={
                "per_page": safe_limit,
                "page": page,
            },
        )

        response.raise_for_status()

        data = response.json()

        return [
            self._map_github_issue_comment(
                item,
                issue_number=issue_number,
            )
            for item in data
        ]


    def create_issue_comment(
        self,
        owner: str,
        name: str,
        issue_number: int,
        body: str,
    ) -> ProviderIssueComment:
        headers = self._get_issue_headers(owner, name)

        response = self._client.post(
            f"/repos/{owner}/{name}/issues/{issue_number}/comments",
            headers=headers,
            json={
                "body": body,
            },
        )

        response.raise_for_status()

        return self._map_github_issue_comment(
            response.json(),
            issue_number=issue_number,
        )


    def close_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> ProviderIssue:
        return self._update_issue_state(
            owner=owner,
            name=name,
            issue_number=issue_number,
            state="closed",
        )


    def reopen_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> ProviderIssue:
        return self._update_issue_state(
            owner=owner,
            name=name,
            issue_number=issue_number,
            state="open",
        )


    def _update_issue_state(
        self,
        owner: str,
        name: str,
        issue_number: int,
        state: str,
    ) -> ProviderIssue:
        headers = self._get_issue_headers(owner, name)

        response = self._client.request(
            method="PATCH",
            url=f"/repos/{owner}/{name}/issues/{issue_number}",
            headers=headers,
            json={
                "state": state,
            },
        )

        if response.status_code >= 400:
            raise RuntimeError(
                "GitHub issue state update failed: "
                f"HTTP {response.status_code}; "
                f"headers={dict(response.headers)}; "
                f"body={response.text!r}"
            )
        
        response.raise_for_status()

        return self._map_github_issue(response.json())


    @staticmethod
    def _map_github_issue(
        item: Dict[str, Any],
    ) -> ProviderIssue:
        author = item.get("user") or {}

        created_at_raw = item.get("created_at")
        updated_at_raw = item.get("updated_at")
        closed_at_raw = item.get("closed_at")

        def parse_dt(value: Optional[str]) -> datetime:
            if not value:
                return datetime.now(timezone.utc)

            try:
                return datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
            except Exception:
                return datetime.now(timezone.utc)

        return ProviderIssue(
            id=str(item["id"]),
            number=int(item["number"]),
            title=item.get("title", ""),
            body=item.get("body"),
            state=item.get("state", "open"),
            author_login=author.get("login"),
            author_name=author.get("name") or author.get("login"),
            created_at=parse_dt(created_at_raw),
            updated_at=parse_dt(updated_at_raw),
            closed_at=(
                parse_dt(closed_at_raw)
                if closed_at_raw
                else None
            ),
            html_url=item.get("html_url", ""),
            labels=[
                label.get("name", "")
                for label in item.get("labels", [])
                if label.get("name")
            ],
        )


    @staticmethod
    def _map_github_issue_comment(
        item: Dict[str, Any],
        issue_number: int,
    ) -> ProviderIssueComment:
        author = item.get("user") or {}

        created_at_raw = item.get("created_at")
        updated_at_raw = item.get("updated_at")

        def parse_dt(value: Optional[str]) -> datetime:
            if not value:
                return datetime.now(timezone.utc)

            try:
                return datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
            except Exception:
                return datetime.now(timezone.utc)

        return ProviderIssueComment(
            id=str(item["id"]),
            issue_number=issue_number,
            body=item.get("body", ""),
            author_login=author.get("login"),
            author_name=author.get("name") or author.get("login"),
            created_at=parse_dt(created_at_raw),
            updated_at=parse_dt(updated_at_raw),
            html_url=item.get("html_url", ""),
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
                "patch": f.get("patch"),
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

    def create_or_update_file(
        self,
        owner: str,
        name: str,
        path: str,
        message: str,
        content: bytes,
        branch: str,
    ) -> Dict[str, Any]:
        headers = self._get_installation_headers(owner, name)
        clean_path = path.lstrip("/")
        payload = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        }
        res = self._client.put(f"/repos/{owner}/{name}/contents/{clean_path}", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

    def create_governed_commit(
        self,
        owner: str,
        name: str,
        branch: str,
        commit_message: str,
        file_patches: List[Dict[str, Any]],
        author_name: str,
        author_email: str,
        base_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a commit on a SUTRA-governed branch via the GitHub Git Data API.

        Uses the GitHub App installation token (contents: write). The agent never
        needs to call git push — SUTRA executes the commit atomically.

        Args:
            owner: Repository owner/org.
            name: Repository name.
            branch: Feature branch to commit onto (created from base_branch if absent).
            commit_message: Git commit message.
            file_patches: List of dicts with keys:
                - path (str): file path relative to repo root.
                - content (str): UTF-8 text content of the file.
                - mode (str, optional): git blob mode, default "100644".
                - operation (str, optional): "upsert" (default) or "delete".
            author_name: Committer name for the Git commit object.
            author_email: Committer email for the Git commit object.
            base_branch: Branch to branch off if `branch` doesn't exist yet.

        Returns:
            Dict with keys: commit_sha, branch, tree_sha, parent_sha, html_url.

        Raises:
            ValueError: on GitHub API errors or missing data.
        """
        headers = self._get_installation_headers(owner, name)

        # ── 1. Resolve HEAD of target branch (create it if missing) ──────────
        ref_res = self._client.get(
            f"/repos/{owner}/{name}/git/ref/heads/{branch}",
            headers=headers,
        )
        if ref_res.status_code == 404:
            # Branch doesn't exist — create it from base_branch HEAD
            base = base_branch or "main"
            base_ref_res = self._client.get(
                f"/repos/{owner}/{name}/git/ref/heads/{base}",
                headers=headers,
            )
            base_ref_res.raise_for_status()
            base_sha = base_ref_res.json()["object"]["sha"]
            create_ref_res = self._client.post(
                f"/repos/{owner}/{name}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{branch}", "sha": base_sha},
            )
            create_ref_res.raise_for_status()
            parent_sha = base_sha
        else:
            ref_res.raise_for_status()
            parent_sha = ref_res.json()["object"]["sha"]

        # ── 2. Resolve current tree SHA from parent commit ───────────────────
        parent_commit_res = self._client.get(
            f"/repos/{owner}/{name}/git/commits/{parent_sha}",
            headers=headers,
        )
        parent_commit_res.raise_for_status()
        parent_tree_sha = parent_commit_res.json()["tree"]["sha"]

        # ── 3. Build tree entries from file_patches ──────────────────────────
        tree_entries: List[Dict[str, Any]] = []
        for patch in file_patches:
            op = patch.get("operation", "upsert")
            file_path = patch["path"].lstrip("/")
            if op == "delete":
                tree_entries.append({
                    "path": file_path,
                    "mode": patch.get("mode", "100644"),
                    "type": "blob",
                    "sha": None,  # null SHA = deletion
                })
            else:
                # Create blob
                content_str = patch.get("content", "")
                blob_res = self._client.post(
                    f"/repos/{owner}/{name}/git/blobs",
                    headers=headers,
                    json={
                        "content": content_str,
                        "encoding": "utf-8",
                    },
                )
                blob_res.raise_for_status()
                blob_sha = blob_res.json()["sha"]
                tree_entries.append({
                    "path": file_path,
                    "mode": patch.get("mode", "100644"),
                    "type": "blob",
                    "sha": blob_sha,
                })

        # ── 4. Create new tree ───────────────────────────────────────────────
        tree_res = self._client.post(
            f"/repos/{owner}/{name}/git/trees",
            headers=headers,
            json={"base_tree": parent_tree_sha, "tree": tree_entries},
        )
        tree_res.raise_for_status()
        new_tree_sha = tree_res.json()["sha"]

        # ── 5. Create commit object ──────────────────────────────────────────
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_res = self._client.post(
            f"/repos/{owner}/{name}/git/commits",
            headers=headers,
            json={
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [parent_sha],
                "author": {"name": author_name, "email": author_email, "date": now_iso},
                "committer": {"name": author_name, "email": author_email, "date": now_iso},
            },
        )
        commit_res.raise_for_status()
        commit_data = commit_res.json()
        new_commit_sha = commit_data["sha"]

        # ── 6. Advance branch ref (fast-forward only) ────────────────────────
        update_res = self._client.patch(
            f"/repos/{owner}/{name}/git/refs/heads/{branch}",
            headers=headers,
            json={"sha": new_commit_sha, "force": False},
        )
        if update_res.status_code == 409:
            raise ValueError(
                f"Branch '{branch}' changed during governed commit creation. Retry."
            )
        update_res.raise_for_status()

        html_url = (
            f"https://github.com/{owner}/{name}/commit/{new_commit_sha}"
        )
        return {
            "commit_sha": new_commit_sha,
            "branch": branch,
            "tree_sha": new_tree_sha,
            "parent_sha": parent_sha,
            "html_url": html_url,
        }

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

    def list_pull_requests(
        self,
        owner: str,
        name: str,
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
        installation_id: Optional[int] = None,
    ) -> List[ProviderPullRequest]:
        headers = self._get_installation_headers(owner, name, installation_id=installation_id)
        safe_state = state if state in {"open", "closed", "all"} else "all"
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        page = (safe_offset // safe_limit) + 1

        res = self._client.get(
            f"/repos/{owner}/{name}/pulls",
            headers=headers,
            params={
                "state": safe_state,
                "per_page": safe_limit,
                "page": page,
            },
        )
        res.raise_for_status()
        data = res.json()
        return [
            ProviderPullRequest(
                number=item["number"],
                title=item["title"],
                body=item.get("body"),
                head_ref=item["head"]["ref"] if item.get("head") else "",
                head_sha=item["head"]["sha"] if item.get("head") else "",
                base_ref=item["base"]["ref"] if item.get("base") else "",
                base_sha=item["base"]["sha"] if item.get("base") else "",
                is_merged=item.get("merged_at") is not None,
                is_closed=item.get("state") == "closed",
                mergeable=item.get("mergeable"),
                html_url=item.get("html_url", ""),
            )
            for item in data
        ]

    def create_branch(
        self,
        owner: str,
        name: str,
        branch: str,
        commit_sha: str,
    ) -> ProviderBranch:
        headers = self._get_installation_headers(owner, name)
        ref = f"refs/heads/{branch}"
        payload = {
            "ref": ref,
            "sha": commit_sha,
        }
        res = self._client.post(f"/repos/{owner}/{name}/git/refs", headers=headers, json=payload)
        res.raise_for_status()
        return ProviderBranch(
            name=branch,
            commit_sha=commit_sha,
            is_protected=False,
        )

    def delete_branch(
        self,
        owner: str,
        name: str,
        branch: str,
    ) -> bool:
        headers = self._get_installation_headers(owner, name)
        res = self._client.delete(f"/repos/{owner}/{name}/git/refs/heads/{branch}", headers=headers)
        if res.status_code in (200, 204, 404):
            return True
        res.raise_for_status()
        return True

    def close_pull_request(
        self,
        owner: str,
        name: str,
        pr_number: int,
    ) -> Optional[ProviderPullRequest]:
        headers = self._get_installation_headers(owner, name)
        res = self._client.patch(
            f"/repos/{owner}/{name}/pulls/{pr_number}",
            headers=headers,
            json={"state": "closed"},
        )
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

    def revert_commit(
        self,
        owner: str,
        name: str,
        commit_sha: str,
        branch: str,
        author_name: str,
        author_email: str,
    ) -> Dict[str, Any]:
        """
        Create a new commit that restores the tree from the selected
        commit's first parent, then advance the target branch to it.

        This mirrors SUTRA's current local rollback semantics.
        """

        headers = self._get_installation_headers(owner, name)

        # ---------------------------------------------------------
        # 1. Get the selected commit
        # ---------------------------------------------------------
        commit_res = self._client.get(
            f"/repos/{owner}/{name}/commits/{commit_sha}",
            headers=headers,
        )

        if commit_res.status_code == 404:
            raise ValueError("Commit not found")

        commit_res.raise_for_status()

        commit_data = commit_res.json()

        parents = commit_data.get("parents", [])

        if not parents:
            raise ValueError(
                "Cannot revert initial commit because it has no parent"
            )

        parent_sha = parents[0]["sha"]

        parent_commit_res = self._client.get(
            f"/repos/{owner}/{name}/commits/{parent_sha}",
            headers=headers,
        )
        parent_commit_res.raise_for_status()

        parent_commit_data = parent_commit_res.json()

        parent_tree_sha = (
            parent_commit_data
            .get("commit", {})
            .get("tree", {})
            .get("sha")
        )

        if not parent_tree_sha:
            raise ValueError(
                "Unable to resolve parent commit tree"
            )

        # ---------------------------------------------------------
        # 2. Read current branch HEAD
        # ---------------------------------------------------------
        branch_res = self._client.get(
            f"/repos/{owner}/{name}/git/ref/heads/{branch}",
            headers=headers,
        )

        if branch_res.status_code == 404:
            raise ValueError(
                f"Branch '{branch}' not found"
            )

        branch_res.raise_for_status()

        branch_data = branch_res.json()

        current_head = (
            branch_data
            .get("object", {})
            .get("sha")
        )

        if not current_head:
            raise ValueError(
                f"Unable to resolve HEAD for branch '{branch}'"
            )

        # ---------------------------------------------------------
        # 3. Create a new tree based on the reverted commit's tree
        #
        # No file entries are needed because we want the complete
        # parent tree as the snapshot.
        # ---------------------------------------------------------
        tree_res = self._client.post(
            f"/repos/{owner}/{name}/git/trees",
            headers=headers,
            json={
                "base_tree": parent_tree_sha,
                "tree": [],
            },
        )

        tree_res.raise_for_status()

        new_tree_sha = (
            tree_res.json()
            .get("sha")
        )

        if not new_tree_sha:
            raise ValueError(
                "GitHub did not return a tree SHA"
            )

        # ---------------------------------------------------------
        # 4. Create rollback commit
        # ---------------------------------------------------------
        message = (
            f'Revert "{commit_sha[:7]}" via SUTRA'
        )

        commit_res = self._client.post(
            f"/repos/{owner}/{name}/git/commits",
            headers=headers,
            json={
                "message": message,
                "tree": new_tree_sha,
                "parents": [current_head],
                "author": {
                    "name": author_name,
                    "email": author_email,
                },
                "committer": {
                    "name": author_name,
                    "email": author_email,
                },
            },
        )

        commit_res.raise_for_status()

        new_commit_sha = (
            commit_res.json()
            .get("sha")
        )

        if not new_commit_sha:
            raise ValueError(
                "GitHub did not return the rollback commit SHA"
            )

        # ---------------------------------------------------------
        # 5. Advance branch WITHOUT force
        #
        # Because new_commit_sha has current_head as its parent,
        # this should be a fast-forward update.
        # ---------------------------------------------------------
        update_res = self._client.patch(
            f"/repos/{owner}/{name}/git/refs/heads/{branch}",
            headers=headers,
            json={
                "sha": new_commit_sha,
                "force": False,
            },
        )

        if update_res.status_code == 409:
            raise ValueError(
                "Rollback lost a branch race: branch changed "
                "while the rollback was being created"
            )

        update_res.raise_for_status()

        return {
            "reverted": commit_sha,
            "parent_sha": parent_sha,
            "branch": branch,
            "new_commit": new_commit_sha,
            "message": (
                f"Reverted {commit_sha[:7]} successfully"
            ),
        }
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
            # If the repository disallows this specific merge_method (e.g. merge commit not allowed, only squash or rebase),
            # attempt fallback to alternate methods if not explicitly specified by user
            alt_methods = [m for m in ["squash", "merge", "rebase"] if m != method]
            for alt in alt_methods:
                payload["merge_method"] = alt
                alt_res = self._client.put(f"/repos/{owner}/{name}/pulls/{pr_number}/merge", headers=headers, json=payload)
                if alt_res.status_code == 200:
                    alt_data = alt_res.json()
                    return ProviderMergeResult(
                        success=True,
                        merge_commit_sha=alt_data.get("sha"),
                        message=alt_data.get("message", f"Merged successfully using {alt}"),
                    )
            return ProviderMergeResult(
                success=False,
                merge_commit_sha=None,
                message=f"Pull request not mergeable or merge method blocked (HTTP 405): {res.text}",
            )
        else:
            return ProviderMergeResult(
                success=False,
                merge_commit_sha=None,
                message=f"GitHub merge failed with HTTP {res.status_code}: {res.text}",
            )

    def list_check_runs(
        self,
        owner: str,
        name: str,
        ref: str,
    ) -> List[Dict[str, Any]]:
        """List check runs for a commit ref/SHA on GitHub."""
        headers = self._get_installation_headers(owner, name)
        url = f"/repos/{owner}/{name}/commits/{ref}/check-runs"
        res = self._client.get(url, headers=headers)
        if res.status_code == 404:
            return []
        res.raise_for_status()
        data = res.json()
        return data.get("check_runs", [])

    def create_check_run(
        self,
        owner: str,
        name: str,
        check_name: str,
        head_sha: str,
        status: str = "completed",
        conclusion: Optional[str] = "success",
        title: Optional[str] = None,
        summary: Optional[str] = None,
        details_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a check run on GitHub."""
        headers = self._get_installation_headers(owner, name)
        url = f"/repos/{owner}/{name}/check-runs"
        body: Dict[str, Any] = {
            "name": check_name,
            "head_sha": head_sha,
            "status": status,
        }
        if conclusion and status == "completed":
            body["conclusion"] = conclusion
        if title or summary:
            body["output"] = {
                "title": title or check_name,
                "summary": summary or f"Check run {check_name}: {conclusion or status}",
            }
        if details_url:
            body["details_url"] = details_url
        res = self._client.post(url, headers=headers, json=body)
        res.raise_for_status()
        return res.json()

    def update_check_run(
        self,
        owner: str,
        name: str,
        check_run_id: int,
        status: str = "completed",
        conclusion: Optional[str] = "success",
        title: Optional[str] = None,
        summary: Optional[str] = None,
        details_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing check run on GitHub."""
        headers = self._get_installation_headers(owner, name)
        url = f"/repos/{owner}/{name}/check-runs/{check_run_id}"
        body: Dict[str, Any] = {
            "status": status,
        }
        if conclusion and status == "completed":
            body["conclusion"] = conclusion
        if title or summary:
            body["output"] = {
                "title": title or f"Check {check_run_id}",
                "summary": summary or f"Check run {check_run_id}: {conclusion or status}",
            }
        if details_url:
            body["details_url"] = details_url
        res = self._client.patch(url, headers=headers, json=body)
        res.raise_for_status()
        return res.json()
