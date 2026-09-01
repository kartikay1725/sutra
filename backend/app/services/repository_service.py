import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.repository import Repository


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
                import shutil

                def handle_remove_readonly(
                    func,
                    path,
                    exc,
                ):
                    import stat

                    try:
                        os.chmod(
                            path,
                            stat.S_IWRITE,
                        )
                    except OSError:
                        pass

                    func(path)

                shutil.rmtree(
                    repository_path,
                    onerror=handle_remove_readonly,
                )

            raise