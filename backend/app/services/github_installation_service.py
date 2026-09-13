"""
GitHub Installation Service
============================
Manages the association between SUTRA users and GitHub App installations.

Design principles:
- No installation access tokens are ever persisted in the database.
- Tokens are fetched on-demand and used ephemerally.
- Repository sync is fully idempotent: identified by (provider_type, external_id).
- One GitHub installation → one SUTRA user (enforced by unique constraint).
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.user import User
from app.providers.github.auth import GitHubAppAuthService

logger = logging.getLogger("sutra.services.github_installation")


class GitHubInstallationService:
    """Service for GitHub App installation lifecycle and repository synchronization."""

    def __init__(self, auth_service: GitHubAppAuthService):
        self.auth_service = auth_service

    # ------------------------------------------------------------------
    # Installation CRUD
    # ------------------------------------------------------------------

    def get_installation_for_user(
        self, db: Session, user_id: str
    ) -> Optional[GitHubInstallation]:
        """Return the active GitHub installation record for a SUTRA user, or None."""
        return db.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.user_id == user_id
            )
        )

    def upsert_installation(
        self,
        db: Session,
        user_id: str,
        github_installation_id: int,
        github_account_id: int,
        github_account_login: str,
        target_type: str,
    ) -> GitHubInstallation:
        """
        Create or update the GitHubInstallation record for a user.
        If the same installation_id is already owned by a different user, raises ValueError.
        """
        # Check if this installation_id is already claimed by another user
        existing_by_install_id = db.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.github_installation_id == github_installation_id
            )
        )
        if existing_by_install_id and existing_by_install_id.user_id != user_id:
            raise ValueError(
                f"GitHub installation {github_installation_id} is already "
                f"associated with a different SUTRA user."
            )

        # Find existing record for this user
        installation = self.get_installation_for_user(db, user_id)

        if installation is None:
            installation = GitHubInstallation(
                id=str(uuid4()),
                user_id=user_id,
                github_installation_id=github_installation_id,
                github_account_id=github_account_id,
                github_account_login=github_account_login,
                target_type=target_type,
            )
            db.add(installation)
        else:
            # Update all fields — user may have reinstalled or switched org
            installation.github_installation_id = github_installation_id
            installation.github_account_id = github_account_id
            installation.github_account_login = github_account_login
            installation.target_type = target_type
            installation.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(installation)
        return installation

    def delete_installation(self, db: Session, user_id: str) -> bool:
        """
        Remove a user's GitHub installation record.
        Does NOT delete synced repositories — they become orphaned (provider_type=github)
        and should be handled gracefully by the listing endpoints.
        """
        installation = self.get_installation_for_user(db, user_id)
        if installation is None:
            return False
        db.delete(installation)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # GitHub API verification
    # ------------------------------------------------------------------

    def verify_installation_from_github(
        self, installation_id: int
    ) -> dict:
        """
        Verify an installation by calling the GitHub API.
        Returns the raw installation data from GitHub.
        Raises httpx.HTTPStatusError if the installation is invalid/inaccessible.

        IMPORTANT: Uses the App JWT (never an installation token) — the private key
        stays on the server and is never exposed.
        """
        jwt_token = self.auth_service.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        client = self.auth_service._client
        response = client.get(f"/app/installations/{installation_id}", headers=headers)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Repository listing from GitHub
    # ------------------------------------------------------------------

    def list_repos_for_installation(self, installation_id: int) -> list[dict]:
        """
        Fetch all repositories accessible through a GitHub App installation.
        Uses a short-lived installation token (fetched, used, and discarded here).
        The token is NOT stored anywhere.
        """
        # Get an installation token scoped for listing repos (metadata:read)
        if hasattr(self.auth_service, "create_installation_token_cached"):
            token_data = self.auth_service.create_installation_token_cached(
                installation_id=installation_id,
                repositories=[],  # all repos in the installation
                permissions={"metadata": "read"},
            )
        else:
            token_data = self.auth_service.create_installation_token(
                installation_id=installation_id,
                repositories=[],
                permissions={"metadata": "read"},
            )
        raw_token = token_data["token"]

        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        all_repos = []
        page = 1
        client = self.auth_service._client

        while True:
            resp = client.get(
                f"/installation/repositories?per_page=100&page={page}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            repos = data.get("repositories", [])
            all_repos.extend(repos)
            # Stop if we got fewer than 100 (last page)
            if len(repos) < 100:
                break
            page += 1

        return all_repos

    # ------------------------------------------------------------------
    # Repository sync (idempotent)
    # ------------------------------------------------------------------

    def sync_repos_for_user(
        self,
        db: Session,
        user: User,
        installation: GitHubInstallation,
    ) -> list[Repository]:
        """
        Fetch all repositories from GitHub for this installation and upsert them
        into the SUTRA repositories table.

        Idempotency: identified by (provider_type='github', external_id=str(github_repo_id)).
        If a repo already exists, its metadata is updated. No duplicates are created.

        IMPORTANT: No Git content is fetched or stored. SUTRA only stores metadata.
        Repository engineering objects (issues/PRs) are backfilled asynchronously.
        """
        github_repos = self.list_repos_for_installation(
            installation.github_installation_id
        )

        synced = []
        now = datetime.now(timezone.utc)

        for gh_repo in github_repos:
            external_id = str(gh_repo["id"])
            repo_name = gh_repo["name"]
            owner_login = gh_repo["owner"]["login"]

            # Look up by stable external identity
            existing = db.scalar(
                select(Repository).where(
                    Repository.provider_type == "github",
                    Repository.external_id == external_id,
                    Repository.deleted_at.is_(None),
                )
            )

            if existing is not None:
                # Update mutable metadata
                existing.name = repo_name
                existing.slug = repo_name.lower()
                existing.description = gh_repo.get("description")
                existing.visibility = "private" if gh_repo.get("private") else "public"
                existing.default_branch = gh_repo.get("default_branch", "main")
                existing.github_installation_id = installation.github_installation_id
                existing.provider_owner = owner_login
                existing.updated_at = now
                synced.append(existing)
            else:
                # Create new repository record
                new_repo = Repository(
                    id=str(uuid4()),
                    owner_id=user.id,
                    name=repo_name,
                    slug=repo_name.lower(),
                    description=gh_repo.get("description"),
                    visibility="private" if gh_repo.get("private") else "public",
                    default_branch=gh_repo.get("default_branch", "main"),
                    # storage_key is used for local git objects; for GitHub repos it's a placeholder
                    storage_key=f"github/{installation.github_installation_id}/{external_id}",
                    provider_type="github",
                    external_id=external_id,
                    github_installation_id=installation.github_installation_id,
                    provider_owner=owner_login,
                    settings={},
                )
                db.add(new_repo)
                synced.append(new_repo)

        db.commit()
        for repo in synced:
            db.refresh(repo)

        logger.info(
            f"Synced {len(synced)} GitHub repositories for user {user.id} "
            f"(installation {installation.github_installation_id})"
        )
        return synced

    def sync_repository_engineering_objects(
        self,
        db: Session,
        repository: Repository,
        issue_limit: int = 30,
        pr_limit: int = 30,
        installation_id: Optional[int] = None,
        force: bool = False,
        staleness_hours: float = 1.0,
    ) -> dict[str, Any]:
        """
        Idempotently backfill existing open issues and pull requests from GitHub
        into SUTRA without fabricating agent or session provenance.
        Respects 1-hour default staleness guard unless force=True.
        Updates github_objects_synced_at upon completion.
        """
        if repository.provider_type != "github" or not repository.provider_owner:
            return {"issues": 0, "pull_requests": 0, "skipped": True}

        inst_id = installation_id or repository.github_installation_id
        now = datetime.now(timezone.utc)

        # Staleness guard (Q3): 1 hour default
        if not force and repository.github_objects_synced_at is not None:
            synced_at = repository.github_objects_synced_at
            if synced_at.tzinfo is None:
                synced_at = synced_at.replace(tzinfo=timezone.utc)
            age = now - synced_at
            if age < timedelta(hours=staleness_hours):
                logger.debug(
                    f"Skipping backfill for {repository.name}: synced {age.total_seconds():.0f}s ago (< {staleness_hours}h)"
                )
                return {"issues": 0, "pull_requests": 0, "skipped": True}

        from app.models.issue import Issue
        from app.providers.github.repository import GitHubRepositoryProvider
        from app.services import knowledge_graph_service
        from app.services.pull_request_service import PullRequestService

        provider = GitHubRepositoryProvider(
            auth_service=self.auth_service,
            base_url=getattr(self.auth_service, "base_url", "https://api.github.com"),
        )
        owner = repository.provider_owner
        repo_name = repository.name

        issues_synced = 0
        prs_synced = 0

        # 1. Backfill Issues
        try:
            gh_issues = provider.list_issues(
                owner=owner,
                name=repo_name,
                state="open",
                limit=issue_limit,
                installation_id=inst_id,
            )
            for gh_issue in gh_issues:
                # Deduplicate by repository_id + github_issue_id / github_issue_number
                existing_issue = None
                if gh_issue.id:
                    existing_issue = db.scalar(
                        select(Issue).where(
                            Issue.repository_id == repository.id,
                            Issue.github_issue_id == str(gh_issue.id),
                        )
                    )
                if not existing_issue and gh_issue.number:
                    existing_issue = db.scalar(
                        select(Issue).where(
                            Issue.repository_id == repository.id,
                            Issue.github_issue_number == gh_issue.number,
                        )
                    )

                if existing_issue:
                    existing_issue.title = gh_issue.title or existing_issue.title
                    existing_issue.body = gh_issue.body or existing_issue.body
                    existing_issue.status = gh_issue.state or existing_issue.status
                    existing_issue.github_html_url = gh_issue.html_url or existing_issue.github_html_url
                    existing_issue.github_author_login = gh_issue.author_login or existing_issue.github_author_login
                    existing_issue.updated_at = gh_issue.updated_at or now
                else:
                    new_issue = Issue(
                        id=str(uuid4()),
                        repository_id=repository.id,
                        github_issue_id=str(gh_issue.id) if gh_issue.id else None,
                        github_issue_number=gh_issue.number,
                        github_html_url=gh_issue.html_url,
                        source_type="human",
                        agent_id=None,
                        agent_session_id=None,
                        task_id=None,
                        actor_id=None,
                        title=gh_issue.title or f"GitHub Issue #{gh_issue.number}",
                        body=gh_issue.body or "",
                        status=gh_issue.state or "open",
                        github_author_login=gh_issue.author_login,
                        created_at=gh_issue.created_at or now,
                        updated_at=gh_issue.updated_at or now,
                        closed_at=gh_issue.closed_at,
                    )
                    db.add(new_issue)
                issues_synced += 1

            db.commit()
        except Exception as e:
            logger.warning(f"Error backfilling issues for {owner}/{repo_name}: {e}")
            db.rollback()

        # 2. Backfill Pull Requests
        try:
            gh_prs = provider.list_pull_requests(
                owner=owner,
                name=repo_name,
                state="open",
                limit=pr_limit,
                installation_id=inst_id,
            )
            pr_svc = PullRequestService(db)
            for gh_pr in gh_prs:
                pr_svc.upsert_github_pull_request(
                    repository=repository,
                    pr_number=gh_pr.number,
                    title=gh_pr.title or f"GitHub PR #{gh_pr.number}",
                    target_branch=gh_pr.base_ref or (repository.default_branch or "main"),
                    head_branch=gh_pr.head_ref or None,
                    head_sha=gh_pr.head_sha or None,
                    base_sha=gh_pr.base_sha or None,
                    description=gh_pr.body or None,
                    html_url=gh_pr.html_url or None,
                    author_login=None,
                    is_merged=gh_pr.is_merged,
                    is_closed=gh_pr.is_closed,
                    action="opened",
                )
                prs_synced += 1

            db.commit()
        except Exception as e:
            logger.warning(f"Error backfilling PRs for {owner}/{repo_name}: {e}")
            db.rollback()

        # 3. Index Knowledge Graph
        try:
            knowledge_graph_service.index_engineering_lifecycle(db, repository)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to index Knowledge Graph after engineering backfill: {e}")
            db.rollback()

        # 4. Update github_objects_synced_at timestamp
        try:
            repository.github_objects_synced_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to update github_objects_synced_at for {repository.name}: {e}")
            db.rollback()

        return {"issues": issues_synced, "pull_requests": prs_synced, "skipped": False}

