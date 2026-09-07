from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user_optional,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.services.repository_browser_service import (
    RepositoryBrowserError,
    RepositoryBrowserService,
)
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider
from app.services.code_provenance_service import CodeProvenanceService


router = APIRouter(
    prefix="/v1/repositories",
    tags=["repository-browser"],
)


def _resolve_repository(
    owner: str,
    repo: str,
    current_user: User | None,
    db: Session,
) -> Repository:

    repository = db.scalar(
        select(Repository)
        .join(
            User,
            User.id == Repository.owner_id,
        )
        .where(
            User.username == owner,
            Repository.slug == repo.lower(),
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    if (
        repository.visibility == "private"
        and (
            current_user is None
            or current_user.id
            != repository.owner_id
        )
    ):
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repository


def _browser(
    repository: Repository,
) -> RepositoryBrowserService:

    storage_root = Path(
        settings.repository_storage_path
    ).resolve()

    repository_path = (
        storage_root
        / repository.storage_key
    ).resolve()

    if not repository_path.is_relative_to(
        storage_root
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Repository storage "
                "integrity failure"
            ),
        )

    try:
        return RepositoryBrowserService(
            repository_path
        )

    except RepositoryBrowserError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
def _github_provider(repository: Repository) -> GitHubRepositoryProvider:
    if repository.provider_type != "github":
        raise HTTPException(
            status_code=400,
            detail="Repository is not a GitHub repository",
        )

    if not repository.provider_owner:
        raise HTTPException(
            status_code=500,
            detail="GitHub repository owner metadata is missing",
        )

    if not settings.github_app_id or not settings.github_private_key_pem:
        raise HTTPException(
            status_code=503,
            detail="GitHub App is not configured",
        )

    auth_service = GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )

    return GitHubRepositoryProvider(
        auth_service=auth_service,
        base_url=settings.github_api_base_url,
    )

def _browser_error(
    exc: RepositoryBrowserError,
) -> HTTPException:

    message = str(exc)

    status_code = (
        413
        if message.startswith(
            "File exceeds"
        )
        else 404
    )

    return HTTPException(
        status_code=status_code,
        detail=message,
    )


# ---------------------------------------------------------
# BRANCHES
# ---------------------------------------------------------

@router.get(
    "/{owner}/{repo}/branches"
)
def list_repository_branches(
    owner: str,
    repo: str,
    current_user: User | None = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    try:
        if repository.provider_type == "github":
            provider = _github_provider(repository)

            branches = provider.list_branches(
                repository.provider_owner,
                repository.name,
            )

            return {
                "repository_id": repository.id,
                "default_branch": repository.default_branch,
                "branches": [
                    {
                        "name": branch.name,
                        "commit": branch.commit_sha,
                        "protected": branch.is_protected,
                    }
                    for branch in branches
                ],
            }

        return {
            "repository_id": repository.id,
            "default_branch": repository.default_branch,
            "branches": _browser(repository).branches(),
        }

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GitHub repository browser failed: {exc}",
        ) from exc


# ---------------------------------------------------------
# DIRECTORY TREE
# ---------------------------------------------------------

@router.get(
    "/{owner}/{repo}/tree"
)
def get_repository_tree(
    owner: str,
    repo: str,
    ref: str | None = Query(
        default=None,
        max_length=256,
    ),
    path: str = Query(
        default="",
        max_length=4096,
    ),
    current_user: User | None = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):

    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    selected_ref = (
        ref
        or repository.default_branch
    )

    try:
        if repository.provider_type == "github":
            provider = _github_provider(repository)

            files = provider.list_files(
                repository.provider_owner,
                repository.name,
                path,
                selected_ref,
            )

            entries = [
                {
                    "name": item["name"],
                    "path": item["path"],
                    "type": (
                        "directory"
                        if item["type"] == "dir"
                        else "file"
                    ),
                    "mode": None,
                    "sha": item.get("sha"),
                    "size": item.get("size"),
                }
                for item in files
            ]

            entries.sort(
                key=lambda item: (
                    item["type"] != "directory",
                    str(item["name"]).lower(),
                )
            )

            return {
                "ref": selected_ref,
                "commit": None,
                "path": path,
                "entries": entries,
                "truncated": False,
            }

        return _browser(repository).tree(
            selected_ref,
            path,
        )

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GitHub repository browser failed: {exc}",
        ) from exc


# ---------------------------------------------------------
# FILE (GET & PUT)
# ---------------------------------------------------------

@router.get(
    "/{owner}/{repo}/file"
)
def get_repository_file(
    owner: str,
    repo: str,
    path: str = Query(
        ...,
        min_length=1,
        max_length=4096,
    ),
    ref: str | None = Query(
        default=None,
        max_length=256,
    ),
    current_user: User | None = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):

    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    selected_ref = (
        ref
        or repository.default_branch
    )

    try:
        if repository.provider_type == "github":
            provider = _github_provider(repository)

            raw = provider.read_file(
                repository.provider_owner,
                repository.name,
                path,
                selected_ref,
            )

            try:
                content = raw.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                content = raw.decode(
                    "utf-8",
                    errors="replace",
                )
                encoding = "utf-8-replaced"

            return {
                "ref": selected_ref,
                "commit": None,
                "path": path,
                "size": len(raw),
                "encoding": encoding,
                "content": content,
            }

        return _browser(repository).file(
            selected_ref,
            path,
        )

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GitHub repository browser failed: {exc}",
        ) from exc


# pyrefly: ignore [missing-import]
from pydantic import BaseModel as _BaseModel

class SaveFileRequest(_BaseModel):
    path: str
    content: str
    branch: str = "main"
    commit_title: str
    commit_description: str | None = None

@router.put(
    "/{owner}/{repo}/file"
)
def save_repository_file(
    owner: str,
    repo: str,
    payload: SaveFileRequest,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    import subprocess
    import tempfile
    import os

    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required to commit changes")

    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    if repository.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied to commit to this repository")

    browser = _browser(repository)
    git_dir = str(browser.repository_path)
    branch = payload.branch or repository.default_branch or "main"
    rel_path = payload.path.lstrip("/").replace("\\", "/")

    # 1. Write the new file blob into git object database: `git hash-object -w --stdin`
    try:
        hash_proc = subprocess.run(
            ["git", "--git-dir", git_dir, "hash-object", "-w", "--stdin"],
            input=payload.content.encode("utf-8"),
            capture_output=True,
            check=True
        )
        blob_sha = hash_proc.stdout.decode("utf-8").strip()

        # 2. Get the current commit SHA of the branch (or empty if brand new)
        rev_proc = subprocess.run(
            ["git", "--git-dir", git_dir, "rev-parse", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
            text=True
        )
        parent_sha = rev_proc.stdout.strip() if rev_proc.returncode == 0 else None

        # 3. Build the new git index using a temporary index file
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            temp_index_path = tf.name

        try:
            env = os.environ.copy()
            env["GIT_INDEX_FILE"] = temp_index_path
            env["GIT_DIR"] = git_dir

            # Read parent commit's tree into temp index if parent exists
            if parent_sha:
                subprocess.run(
                    ["git", "--git-dir", git_dir, "read-tree", parent_sha],
                    env=env,
                    check=True,
                    capture_output=True
                )

            # Update index with the new blob
            subprocess.run(
                ["git", "--git-dir", git_dir, "update-index", "--add", "--cacheinfo", "100644", blob_sha, rel_path],
                env=env,
                check=True,
                capture_output=True
            )

            # Write tree
            write_tree_proc = subprocess.run(
                ["git", "--git-dir", git_dir, "write-tree"],
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            new_tree_sha = write_tree_proc.stdout.strip()

            # 4. Create commit object
            commit_msg = payload.commit_title.strip()
            if payload.commit_description and payload.commit_description.strip():
                commit_msg += f"\n\n{payload.commit_description.strip()}"

            author_str = f"{current_user.username} <{current_user.email}>"
            env["GIT_AUTHOR_NAME"] = current_user.username
            env["GIT_AUTHOR_EMAIL"] = current_user.email
            env["GIT_COMMITTER_NAME"] = current_user.username
            env["GIT_COMMITTER_EMAIL"] = current_user.email

            commit_cmd = ["git", "--git-dir", git_dir, "commit-tree", new_tree_sha, "-m", commit_msg]
            if parent_sha:
                commit_cmd.extend(["-p", parent_sha])

            commit_proc = subprocess.run(
                commit_cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            new_commit_sha = commit_proc.stdout.strip()

            # 5. Update branch ref
            subprocess.run(
                ["git", "--git-dir", git_dir, "update-ref", f"refs/heads/{branch}", new_commit_sha],
                check=True,
                capture_output=True
            )

            return {
                "status": "success",
                "commit_sha": new_commit_sha,
                "branch": branch,
                "path": rel_path,
                "message": commit_msg,
            }
        finally:
            if os.path.exists(temp_index_path):
                os.remove(temp_index_path)

    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Git operation failed: {exc.stderr.decode('utf-8') if hasattr(exc.stderr, 'decode') else str(exc)}"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to commit file: {str(exc)}")

# ---------------------------------------------------------
# BLAME + SUTRA CODE PROVENANCE
# ---------------------------------------------------------

@router.get(
    "/{owner}/{repo}/blame"
)
def get_repository_blame(
    owner: str,
    repo: str,
    path: str = Query(
        ...,
        min_length=1,
        max_length=4096,
    ),
    ref: str | None = Query(
        default=None,
        max_length=256,
    ),
    current_user: User | None = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    selected_ref = (
        ref
        or repository.default_branch
    )

    try:
        if repository.provider_type != "github":
            raise HTTPException(
                status_code=501,
                detail="Blame is currently supported only for GitHub repositories",
            )

        provider = _github_provider(repository)

        ranges = provider.get_file_blame(
            repository.provider_owner,
            repository.name,
            path,
            selected_ref,
        )

        provenance_service = CodeProvenanceService(db)

        enriched_ranges = provenance_service.resolve_blame_ranges(
            repository_id=repository.id,
            ranges=ranges,
        )

        return {
            "repository_id": repository.id,
            "path": path,
            "ref": selected_ref,
            "ranges": enriched_ranges,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GitHub blame failed: {exc}",
        ) from exc

# ---------------------------------------------------------
# COMMITS
# ---------------------------------------------------------

@router.get(
    "/{owner}/{repo}/commits"
)
def list_repository_commits(
    owner: str,
    repo: str,
    ref: str | None = Query(
        default=None,
        max_length=256,
    ),
    limit: int = Query(
        default=30,
        ge=1,
        le=100,
    ),
    current_user: User | None = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):

    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    selected_ref = (
        ref
        or repository.default_branch
    )

    try:
        if repository.provider_type == "github":
            provider = _github_provider(repository)

            commits = provider.list_commits(
                repository.provider_owner,
                repository.name,
                selected_ref,
                limit,
            )

            return {
                "ref": selected_ref,
                "head": commits[0].sha if commits else None,
                "commits": [
                    {
                        "sha": commit.sha,
                        "short_sha": commit.sha[:7],
                        "author_name": commit.author_name,
                        "author_email": commit.author_email,
                        "committed_at": int(
                            commit.committed_at.timestamp()
                        ),
                        "subject": (
                            commit.message.split("\n", 1)[0]
                            if commit.message
                            else ""
                        ),
                    }
                    for commit in commits
                ],
            }

        return _browser(repository).commits(
            selected_ref,
            limit,
        )

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GitHub repository browser failed: {exc}",
        ) from exc


# ---------------------------------------------------------
# COMMIT DETAIL (diff + metadata)
# ---------------------------------------------------------

@router.get("/{owner}/{repo}/commits/{sha}")
def get_commit_detail(
    owner: str,
    repo: str,
    sha: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    import re as _re
    import subprocess as _sp

    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    if not _re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        raise HTTPException(
            status_code=400,
            detail="Invalid commit SHA",
        )

    # ---------------------------------------------------------
    # GITHUB PROVIDER
    # ---------------------------------------------------------
    if repository.provider_type == "github":
        try:
            provider = _github_provider(repository)

            data = provider.get_commit_detail(
                repository.provider_owner,
                repository.name,
                sha,
            )

            commit_data = data.get("commit", {})
            author = commit_data.get("author") or {}

            full_sha = data.get("sha", sha)

            author_name = author.get(
                "name",
                "Unknown",
            )

            author_email = author.get(
                "email",
                "",
            )

            committed_at = 0

            committed_date = author.get("date")

            if committed_date:
                from datetime import datetime

                try:
                    committed_at = int(
                        datetime.fromisoformat(
                            committed_date.replace(
                                "Z",
                                "+00:00",
                            )
                        ).timestamp()
                    )
                except Exception:
                    committed_at = 0

            message = commit_data.get(
                "message",
                "",
            )

            if "\n" in message:
                subject, body = message.split(
                    "\n",
                    1,
                )
                body = body.strip()
            else:
                subject = message
                body = ""

            parents = data.get(
                "parents",
                [],
            )

            parent_sha = (
                parents[0].get("sha")
                if parents
                else None
            )

            file_stats = []
            diff_parts = []

            for item in data.get("files", []):
                filename = item.get("filename", "")
                status = item.get("status", "modified")

                additions = item.get("additions", 0)
                deletions = item.get("deletions", 0)

                file_stats.append(
                    f"{filename} | {status} | "
                    f"+{additions} -{deletions}"
                )

                patch = item.get("patch")

                if patch:
                    diff_parts.append(
                        f"diff --git a/{filename} b/{filename}\n"
                        f"--- a/{filename}\n"
                        f"+++ b/{filename}\n"
                        f"{patch}"
                    )

            return {
                "sha": full_sha,
                "short_sha": full_sha[:7],
                "author_name": author_name,
                "author_email": author_email,
                "committed_at": committed_at,
                "subject": subject,
                "body": body,
                "is_agent": (
                    "bot" in author_name.lower()
                    or "agent" in author_name.lower()
                    or "bot@" in author_email.lower()
                    or "agent@" in author_email.lower()
                ),
                "parent_sha": parent_sha,
                "file_stats": file_stats,
                "diff": "\n\n".join(diff_parts),
            }

        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"GitHub commit detail failed: {exc}",
            ) from exc

    # ---------------------------------------------------------
    # LOCAL PROVIDER — EXISTING BEHAVIOR
    # ---------------------------------------------------------

    git_dir = str(
        (
            Path(settings.repository_storage_path)
            / repository.storage_key
        ).resolve()
    )

    info = _sp.run(
        [
            "git",
            "--git-dir",
            git_dir,
            "show",
            "--stat",
            "--format=%H%n%an%n%ae%n%at%n%s%n%b%n---STAT---",
            sha,
        ],
        capture_output=True,
        text=True,
    )

    if info.returncode != 0:
        raise HTTPException(
            status_code=404,
            detail="Commit not found",
        )

    lines = info.stdout.split("\n")

    full_sha = lines[0].strip()

    author_name = (
        lines[1].strip()
        if len(lines) > 1
        else ""
    )

    author_email = (
        lines[2].strip()
        if len(lines) > 2
        else ""
    )

    try:
        committed_at = int(
            lines[3].strip()
        )
    except Exception:
        committed_at = 0

    subject = (
        lines[4].strip()
        if len(lines) > 4
        else ""
    )

    body_lines = []
    stat_section = False
    file_stats = []

    for line in lines[5:]:
        if line.strip() == "---STAT---":
            stat_section = True
            continue

        if stat_section:
            if "|" in line or line.strip().startswith("..."):
                file_stats.append(line.strip())
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    diff_proc = _sp.run(
        [
            "git",
            "--git-dir",
            git_dir,
            "show",
            "--unified=4",
            "--format=",
            sha,
        ],
        capture_output=True,
        text=True,
        errors="replace",
    )

    diff_text = diff_proc.stdout

    parent_proc = _sp.run(
        [
            "git",
            "--git-dir",
            git_dir,
            "rev-parse",
            f"{sha}^",
        ],
        capture_output=True,
        text=True,
    )

    parent_sha = (
        parent_proc.stdout.strip()
        if parent_proc.returncode == 0
        else None
    )

    is_agent = (
        "bot" in author_name.lower()
        or "agent" in author_name.lower()
        or "bot@" in author_email.lower()
        or "agent@" in author_email.lower()
    )

    return {
        "sha": full_sha,
        "short_sha": (
            full_sha[:7]
            if full_sha
            else sha[:7]
        ),
        "author_name": author_name,
        "author_email": author_email,
        "committed_at": committed_at,
        "subject": subject,
        "body": body,
        "is_agent": is_agent,
        "parent_sha": parent_sha,
        "file_stats": file_stats,
        "diff": diff_text,
    }

# ---------------------------------------------------------
# REVERT (ROLLBACK) — works with bare repos via plumbing
# ---------------------------------------------------------

@router.post("/{owner}/{repo}/commits/{sha}/revert")
def revert_commit(
    owner: str,
    repo: str,
    sha: str,
    branch: str | None = Query(default=None, max_length=256),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    import os as _os
    import re as _re
    import subprocess as _sp

    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    # ---------------------------------------------------------
    # VALIDATE SHA
    # ---------------------------------------------------------
    if not _re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        raise HTTPException(
            status_code=400,
            detail="Invalid commit SHA",
        )

    # ---------------------------------------------------------
    # AUTHENTICATION
    # ---------------------------------------------------------
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    # ---------------------------------------------------------
    # AUTHORIZATION
    # ---------------------------------------------------------
    if repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Permission denied to rollback this repository",
        )

    # =========================================================
    # GITHUB PROVIDER
    # =========================================================
    if repository.provider_type == "github":
        try:
            provider = _github_provider(repository)

            # Explicit branch wins.
            # Otherwise use the repository's configured default branch.
            selected_branch = (
                branch.strip()
                if branch and branch.strip()
                else repository.default_branch
            )

            if not selected_branch:
                raise ValueError(
                    "No target branch specified and repository has no default branch"
                )

            # Prevent obviously invalid branch input.
            if selected_branch.startswith("-"):
                raise ValueError("Invalid branch name")

            result = provider.revert_commit(
                owner=repository.provider_owner,
                name=repository.name,
                commit_sha=sha,
                branch=selected_branch,
                author_name=current_user.username,
                author_email=current_user.email,
            )

            return result

        except ValueError as exc:
            message = str(exc)

            if "not found" in message.lower():
                status_code = 404
            elif "race" in message.lower():
                status_code = 409
            elif "branch" in message.lower():
                status_code = 422
            else:
                status_code = 422

            raise HTTPException(
                status_code=status_code,
                detail=message,
            ) from exc

        except HTTPException:
            raise

        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"GitHub rollback failed: {exc}",
            ) from exc

    # =========================================================
    # LOCAL PROVIDER
    # =========================================================
    try:
        browser = _browser(repository)
        git_dir = str(browser.repository_path)

        # -----------------------------------------------------
        # Resolve selected commit to full SHA
        # -----------------------------------------------------
        full_sha = browser.resolve_commit(sha)

        # -----------------------------------------------------
        # Get parent of commit being reverted
        # -----------------------------------------------------
        parent = _sp.run(
            [
                "git",
                "--git-dir",
                git_dir,
                "rev-parse",
                f"{full_sha}^",
            ],
            capture_output=True,
            text=True,
        )

        if parent.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail="Cannot revert initial commit (no parent)",
            )

        parent_sha = parent.stdout.strip()

        # -----------------------------------------------------
        # Determine target branch
        # -----------------------------------------------------
        if branch and branch.strip():
            selected_branch = branch.strip()
        else:
            selected_branch = None

            # First prefer repository default branch.
            if repository.default_branch:
                selected_branch = repository.default_branch.strip()

            # Fall back to local symbolic HEAD only when no
            # repository default branch is configured.
            if not selected_branch:
                head = _sp.run(
                    [
                        "git",
                        "--git-dir",
                        git_dir,
                        "symbolic-ref",
                        "HEAD",
                    ],
                    capture_output=True,
                    text=True,
                )

                if head.returncode == 0:
                    selected_branch = (
                        head.stdout.strip()
                        .replace("refs/heads/", "")
                    )

            if not selected_branch:
                selected_branch = "main"

        # -----------------------------------------------------
        # Verify target branch exists
        # -----------------------------------------------------
        branch_exists = _sp.run(
            [
                "git",
                "--git-dir",
                git_dir,
                "rev-parse",
                "--verify",
                f"refs/heads/{selected_branch}",
            ],
            capture_output=True,
            text=True,
        )

        if branch_exists.returncode != 0:
            raise HTTPException(
                status_code=404,
                detail=f"Branch '{selected_branch}' not found",
            )

        # -----------------------------------------------------
        # Get current HEAD of selected branch
        # -----------------------------------------------------
        current_head_result = _sp.run(
            [
                "git",
                "--git-dir",
                git_dir,
                "rev-parse",
                f"refs/heads/{selected_branch}",
            ],
            capture_output=True,
            text=True,
        )

        if current_head_result.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Failed to resolve current HEAD of branch "
                    f"'{selected_branch}'"
                ),
            )

        current_head = current_head_result.stdout.strip()

        if not current_head:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Branch '{selected_branch}' has no valid current HEAD"
                ),
            )

        # -----------------------------------------------------
        # Get parent commit tree
        #
        # This mirrors the existing local rollback behaviour:
        # restore the selected commit's parent tree and create
        # a new commit on top of the CURRENT branch HEAD.
        # -----------------------------------------------------
        parent_tree = _sp.run(
            [
                "git",
                "--git-dir",
                git_dir,
                "rev-parse",
                f"{parent_sha}^{{tree}}",
            ],
            capture_output=True,
            text=True,
        )

        if parent_tree.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Failed to resolve parent tree: "
                    f"{parent_tree.stderr.strip()}"
                ),
            )

        parent_tree_sha = parent_tree.stdout.strip()

        # -----------------------------------------------------
        # Create revert commit
        # -----------------------------------------------------
        author_name = current_user.username
        author_email = current_user.email

        env = _os.environ.copy()
        env.update(
            {
                "GIT_DIR": git_dir,
                "GIT_AUTHOR_NAME": author_name,
                "GIT_AUTHOR_EMAIL": author_email,
                "GIT_COMMITTER_NAME": author_name,
                "GIT_COMMITTER_EMAIL": author_email,
            }
        )

        new_commit = _sp.run(
            [
                "git",
                "--git-dir",
                git_dir,
                "commit-tree",
                parent_tree_sha,
                "-p",
                current_head,
                "-m",
                f'Revert "{full_sha[:7]}" via SUTRA',
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        if new_commit.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Revert commit failed: "
                    f"{new_commit.stderr.strip()}"
                ),
            )

        new_sha = new_commit.stdout.strip()

        if not new_sha:
            raise HTTPException(
                status_code=422,
                detail="Revert commit was created without a commit SHA",
            )

        # -----------------------------------------------------
        # Update selected branch
        # -----------------------------------------------------
        update = _sp.run(
            [
                "git",
                "--git-dir",
                git_dir,
                "update-ref",
                f"refs/heads/{selected_branch}",
                new_sha,
                current_head,
            ],
            capture_output=True,
            text=True,
        )

        if update.returncode != 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Failed to update branch '{selected_branch}': "
                    f"{update.stderr.strip()}"
                ),
            )

        return {
            "reverted": full_sha,
            "parent_commit": parent_sha,
            "branch": selected_branch,
            "new_commit": new_sha,
            "message": (
                f"Reverted {full_sha[:7]} successfully "
                f"on branch '{selected_branch}'"
            ),
        }

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc

# ---------------------------------------------------------
# FILE BLAME
# ---------------------------------------------------------

@router.get(
    "/{owner}/{repo}/blame"
)
def get_repository_file_blame(
    owner: str,
    repo: str,
    path: str = Query(
        ...,
        min_length=1,
        max_length=4096,
    ),
    ref: str | None = Query(
        default=None,
        max_length=256,
    ),
    current_user: User | None = Depends(
        get_current_user_optional
    ),
    db: Session = Depends(get_db),
):
    repository = _resolve_repository(
        owner,
        repo,
        current_user,
        db,
    )

    selected_ref = (
        ref
        or repository.default_branch
    )

    if not selected_ref:
        raise HTTPException(
            status_code=422,
            detail="Repository has no default branch",
        )

    clean_path = path.lstrip("/")

    try:
        # -----------------------------------------------------
        # GITHUB PROVIDER
        # -----------------------------------------------------
        if repository.provider_type == "github":
            provider = _github_provider(repository)

            blame_ranges = provider.get_file_blame(
                owner=repository.provider_owner,
                name=repository.name,
                path=clean_path,
                ref=selected_ref,
            )

            return {
                "repository_id": repository.id,
                "path": clean_path,
                "ref": selected_ref,
                "ranges": blame_ranges,
            }

        # -----------------------------------------------------
        # LOCAL PROVIDER
        #
        # Not implemented yet. We will add native git blame
        # after GitHub provenance is working end-to-end.
        # -----------------------------------------------------
        raise HTTPException(
            status_code=501,
            detail=(
                "Line-level blame is currently available "
                "for GitHub repositories only"
            ),
        )

    except HTTPException:
        raise

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            status_code = 404
        else:
            status_code = 422

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Repository blame lookup failed: {exc}",
        ) from exc