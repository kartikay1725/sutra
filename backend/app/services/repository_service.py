import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.repository import Repository

logger = logging.getLogger("sutra.services.repository")


class RepositoryService:

    # ------------------------------------------------------------------
    # Git receive hook
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_receive_hook(
        repository_path: Path,
    ) -> None:
        """Install/update the SUTRA agent pre-receive policy hook."""

        hooks_dir = repository_path / "hooks"
        hooks_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        backend_root = Path(
            __file__
        ).resolve().parents[2]

        project_root = backend_root

        python_executable = Path(
            sys.executable
        ).resolve()

        # Git for Windows launches hooks through a shell. Forward-slash
        # paths are reliable across the Windows Git shell boundary.
        backend_root_str = backend_root.as_posix()
        project_root_str = project_root.as_posix()

        hook = "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                "",
                "# Make the backend importable.",
                (
                    "export PYTHONPATH="
                    f"{shlex.quote(backend_root_str)}"
                ),
                "",
                "# Make the application environment discoverable.",
                (
                    "export SUTRA_PROJECT_ROOT="
                    f"{shlex.quote(project_root_str)}"
                ),
                "",
                (
                    "exec "
                    f"{shlex.quote(str(python_executable))} "
                    "-m app.git_pre_receive"
                ),
                "",
            ]
        )

        hook_path = hooks_dir / "pre-receive"

        hook_path.write_text(
            hook,
            encoding="utf-8",
        )

        try:
            hook_path.chmod(0o755)
        except OSError:
            # chmod is not meaningful on all development filesystems.
            pass

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_git(
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        process_env = os.environ.copy()

        if env:
            process_env.update(env)

        try:
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                env=process_env,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            import sys
            print(f"GIT COMMAND FAILED: {' '.join(args)}", file=sys.stderr)
            print(f"STDOUT: {e.stdout}", file=sys.stderr)
            print(f"STDERR: {e.stderr}", file=sys.stderr)
            raise

    # ------------------------------------------------------------------
    # Initial repository contents
    # ------------------------------------------------------------------

    @staticmethod
    def _initialize_repository_contents(
        repository_path: Path,
        repository_name: str,
    ) -> None:
        """
        Create the first real commit for a newly-created bare repository.

        The bootstrap push is a trusted SUTRA system operation. The receive
        hook is deliberately NOT installed yet, so repository creation does
        not depend on hook environment propagation or application settings.

        Normal pushes after repository creation continue through the installed
        pre-receive policy hook.
        """

        with tempfile.TemporaryDirectory(
            prefix="sutra-initial-repo-"
        ) as temp_dir:
            temp_path = Path(temp_dir)

            RepositoryService._run_git(
                "init",
                "--initial-branch=main",
                temp_path.as_posix(),
            )

            readme = (
                f"# {repository_name}\n\n"
                f"Welcome to {repository_name}.\n\n"
                "This repository was created with SUTRA.\n"
            )

            (
                temp_path / "README.md"
            ).write_text(
                readme,
                encoding="utf-8",
            )

            RepositoryService._run_git(
                "add",
                "README.md",
                cwd=temp_path,
            )

            commit_env = {
                "GIT_AUTHOR_NAME": "SUTRA",
                "GIT_AUTHOR_EMAIL": "no-reply@sutra.local",
                "GIT_COMMITTER_NAME": "SUTRA",
                "GIT_COMMITTER_EMAIL": "no-reply@sutra.local",
            }

            RepositoryService._run_git(
                "commit",
                "-m",
                "Initial commit",
                cwd=temp_path,
                env=commit_env,
            )

            RepositoryService._run_git(
                "remote",
                "add",
                "sutra",
                repository_path.as_posix(),
                cwd=temp_path,
            )

            # The bare repository intentionally has no receive hook yet.
            # Therefore this trusted bootstrap push cannot invoke the agent
            # authorization policy.
            RepositoryService._run_git(
                "push",
                "sutra",
                "HEAD:refs/heads/main",
                cwd=temp_path,
            )

            # Verify that main now points at the pushed commit.
            RepositoryService._run_git(
                "rev-parse",
                "--verify",
                "refs/heads/main",
                cwd=repository_path,
            )

    # ------------------------------------------------------------------
    # Service
    # ------------------------------------------------------------------

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        owner_id: str,
        name: str,
        description: str | None,
        visibility: str,
    ) -> Repository:

        slug = name.lower()

        existing = self.db.scalar(
            select(Repository).where(
                Repository.owner_id == owner_id,
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )

        if existing:
            raise ValueError(
                "Repository already exists"
            )

        repository_id = str(
            uuid4()
        )

        storage_root = Path(
            settings.repository_storage_path
        ).resolve()

        storage_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        repository_path = (
            storage_root / repository_id
        ).resolve()

        if not repository_path.is_relative_to(
            storage_root
        ):
            raise ValueError(
                "Repository path traversal denied"
            )

        repository_path.mkdir(
            parents=True,
            exist_ok=False,
        )

        try:
            # Create the permanent bare repository.
            self._run_git(
                "init",
                "--bare",
                "--initial-branch=main",
                repository_path.as_posix(),
            )

            # ----------------------------------------------------------
            # IMPORTANT:
            #
            # Bootstrap the initial commit BEFORE installing the
            # receive hook. This is a trusted repository-creation
            # operation and must not depend on agent hook execution,
            # hook environment propagation, or application settings.
            # ----------------------------------------------------------
            self._initialize_repository_contents(
                repository_path=repository_path,
                repository_name=name,
            )

            # Only after the repository has a valid initial main branch
            # do we install the permanent receive policy hook.
            self.ensure_receive_hook(
                repository_path
            )

            # Persist the application record only after Git initialization
            # and receive-hook installation have both succeeded.
            repository = Repository(
                id=repository_id,
                owner_id=owner_id,
                name=name,
                slug=slug,
                description=description,
                visibility=visibility,
                default_branch="main",
                storage_key=repository_id,
            )

            self.db.add(repository)
            self.db.commit()
            self.db.refresh(repository)

            return repository

        except Exception:
            self.db.rollback()

            if repository_path.exists():
                shutil.rmtree(
                    repository_path,
                    onerror=self._remove_readonly,
                )

            raise

    @staticmethod
    def _remove_readonly(func, path, exc):
        import stat
        try:
            os.chmod(path, stat.S_IWRITE)
        except OSError:
            pass
        func(path)

    def clone_repository(
        self,
        owner_id: str,
        url: str,
        name: str | None = None,
        description: str | None = None,
        visibility: str = "private",
        connection_type: str | None = None,
        upstream_url: str | None = None,
        upstream_repository_id: str | None = None,
    ) -> Repository:
        """
        Clone any Git URL or repository into SUTRA storage, configure pre-receive hook,
        detect GitHub provider / fork metadata, and persist repository record.
        """
        clean_url = url.strip()
        if not clean_url:
            raise ValueError("Repository URL is required")

        # Normalize shorthand 'owner/repo' format to GitHub URL
        gh_owner = None
        gh_repo = None
        is_github = False

        shorthand_match = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", clean_url)
        github_https_match = re.match(r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", clean_url, re.IGNORECASE)
        github_ssh_match = re.match(r"^git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", clean_url, re.IGNORECASE)

        if shorthand_match:
            gh_owner, gh_repo = shorthand_match.group(1), shorthand_match.group(2)
            clean_url = f"https://github.com/{gh_owner}/{gh_repo}.git"
            is_github = True
        elif github_https_match:
            gh_owner, gh_repo = github_https_match.group(1), github_https_match.group(2)
            is_github = True
        elif github_ssh_match:
            gh_owner, gh_repo = github_ssh_match.group(1), github_ssh_match.group(2)
            is_github = True

        # Derive name if not provided
        if not name:
            if gh_repo:
                name = gh_repo
            else:
                leaf = clean_url.rstrip("/").split("/")[-1]
                if leaf.endswith(".git"):
                    leaf = leaf[:-4]
                name = leaf

        if not name or not re.match(r"^[A-Za-z0-9._-]+$", name):
            raise ValueError(f"Invalid repository name: '{name}'. Must contain only alphanumeric, dash, dot, or underscore.")

        slug = name.lower()

        # Check existing repo for this owner
        existing = self.db.scalar(
            select(Repository).where(
                Repository.owner_id == owner_id,
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )
        if existing:
            raise ValueError(f"Repository with slug '{slug}' already exists for this owner")

        repository_id = str(uuid4())
        storage_root = Path(settings.repository_storage_path).resolve()
        storage_root.mkdir(parents=True, exist_ok=True)

        repository_path = (storage_root / repository_id).resolve()
        if not repository_path.is_relative_to(storage_root):
            raise ValueError("Repository path traversal denied")

        try:
            logger.info(f"Cloning bare repository from {clean_url} to {repository_path}")
            self._run_git("clone", "--bare", clean_url, repository_path.as_posix())

            # Discover default branch from cloned repo
            default_branch = "main"
            try:
                res = self._run_git("symbolic-ref", "--short", "HEAD", cwd=repository_path)
                if res.stdout.strip():
                    default_branch = res.stdout.strip()
            except Exception:
                try:
                    res = self._run_git("rev-parse", "--verify", "refs/heads/master", cwd=repository_path)
                    default_branch = "master"
                except Exception:
                    default_branch = "main"

            # Install SUTRA pre-receive policy hook
            self.ensure_receive_hook(repository_path)

            detected_connection = connection_type or "owned"
            detected_upstream_url = upstream_url
            detected_upstream_id = upstream_repository_id
            gh_external_id = None
            gh_provider_owner = gh_owner
            settings_dict = {"clone_source_url": clean_url}

            # Inspect GitHub metadata & permissions if applicable
            if is_github and gh_owner and gh_repo:
                if getattr(settings, "github_app_id", None) and getattr(settings, "github_private_key_pem", None):
                    try:
                        from app.providers.github.auth import GitHubAppAuthService
                        from app.providers.github.repository import GitHubRepositoryProvider

                        auth_svc = GitHubAppAuthService(
                            app_id=settings.github_app_id,
                            private_key_pem=settings.github_private_key_pem,
                            base_url=settings.github_api_base_url,
                        )
                        provider = GitHubRepositoryProvider(auth_service=auth_svc, base_url=settings.github_api_base_url)
                        raw = provider.get_raw_repository(gh_owner, gh_repo)
                        if raw:
                            gh_external_id = str(raw.get("id")) if raw.get("id") else None
                            is_fork = bool(raw.get("fork"))
                            parent = raw.get("parent")
                            perms = raw.get("permissions", {})
                            settings_dict["permissions"] = perms
                            settings_dict["github_metadata"] = {
                                "fork": is_fork,
                                "parent": parent.get("full_name") if parent else None,
                                "default_branch": raw.get("default_branch"),
                            }

                            if is_fork and parent:
                                detected_connection = "fork"
                                detected_upstream_url = detected_upstream_url or parent.get("html_url") or f"https://github.com/{parent.get('full_name')}.git"
                                # Check if upstream repo is tracked in SUTRA
                                upstream_match = self.db.scalar(
                                    select(Repository).where(
                                        Repository.provider_type == "github",
                                        (Repository.provider_owner == parent.get("owner", {}).get("login")) &
                                        (Repository.slug == parent.get("name", "").lower()),
                                        Repository.deleted_at.is_(None),
                                    )
                                )
                                if upstream_match:
                                    detected_upstream_id = upstream_match.id
                            elif not perms.get("push", False) and not perms.get("admin", False):
                                detected_connection = "external_readonly"
                                detected_upstream_url = detected_upstream_url or clean_url
                            else:
                                detected_connection = connection_type or ("fork" if is_fork else "owned")
                    except Exception as e:
                        logger.warning(f"GitHub metadata query skipped during clone of {gh_owner}/{gh_repo}: {e}")

            settings_dict["connection_type"] = detected_connection
            if detected_upstream_url:
                settings_dict["upstream_url"] = detected_upstream_url

            repository = Repository(
                id=repository_id,
                owner_id=owner_id,
                name=name,
                slug=slug,
                description=description,
                visibility=visibility,
                default_branch=default_branch,
                storage_key=repository_id,
                provider_type="github" if is_github else "local",
                provider_owner=gh_provider_owner,
                external_id=gh_external_id,
                connection_type=detected_connection,
                upstream_repository_id=detected_upstream_id,
                upstream_url=detected_upstream_url,
                settings=settings_dict,
            )

            self.db.add(repository)
            self.db.commit()
            self.db.refresh(repository)

            # Trigger initial file indexing for codebase intelligence
            try:
                from app.services import knowledge_graph_service
                knowledge_graph_service.index_repository_files(self.db, repository, commit_sha=default_branch)
                self.db.commit()
            except Exception as e:
                logger.warning(f"Initial file indexing error for cloned repository {repository.slug}: {e}")

            return repository

        except Exception:
            self.db.rollback()
            if repository_path.exists():
                shutil.rmtree(repository_path, onerror=self._remove_readonly)
            raise

    def create_or_connect_fork(
        self,
        owner_id: str,
        upstream_repository_id: str,
    ) -> Repository:
        """
        Create or connect a fork of an upstream repository for open-source contributions.
        """
        upstream = self.db.scalar(
            select(Repository).where(
                Repository.id == upstream_repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if not upstream:
            raise ValueError(f"Upstream repository '{upstream_repository_id}' not found")

        # Check if a fork already exists for this owner
        existing_fork = self.db.scalar(
            select(Repository).where(
                Repository.owner_id == owner_id,
                Repository.upstream_repository_id == upstream.id,
                Repository.deleted_at.is_(None),
            )
        )
        if existing_fork:
            return existing_fork

        # Upstream GitHub repository: create fork via GitHub API if configured
        fork_url = None
        if upstream.provider_type == "github" and upstream.provider_owner:
            if getattr(settings, "github_app_id", None) and getattr(settings, "github_private_key_pem", None):
                from app.providers.github.auth import GitHubAppAuthService
                from app.providers.github.repository import GitHubRepositoryProvider

                auth_svc = GitHubAppAuthService(
                    app_id=settings.github_app_id,
                    private_key_pem=settings.github_private_key_pem,
                    base_url=settings.github_api_base_url,
                )
                provider = GitHubRepositoryProvider(auth_service=auth_svc, base_url=settings.github_api_base_url)
                try:
                    fork_data = provider.create_fork(upstream.provider_owner, upstream.name)
                    fork_url = fork_data.get("clone_url") or fork_data.get("html_url")
                except Exception as e:
                    logger.warning(f"GitHub fork creation call failed: {e}")

        if not fork_url:
            upstream_path = Path(settings.repository_storage_path).resolve() / upstream.storage_key
            fork_url = upstream_path.as_posix()

        fork_name = f"{upstream.name}-fork"
        upstream_url_str = upstream.upstream_url or (
            f"https://github.com/{upstream.provider_owner}/{upstream.name}.git"
            if upstream.provider_owner else f"{settings.sutra_base_url}/git/{upstream.name}.git"
        )

        return self.clone_repository(
            owner_id=owner_id,
            url=fork_url,
            name=fork_name,
            description=f"Fork of {upstream.name} for autonomous open-source contributions",
            visibility=upstream.visibility,
            connection_type="fork",
            upstream_url=upstream_url_str,
            upstream_repository_id=upstream.id,
        )