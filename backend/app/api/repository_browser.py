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
        return {
            "repository_id": repository.id,
            "default_branch": (
                repository.default_branch
            ),
            "branches": (
                _browser(repository)
                .branches()
            ),
        }

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc


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
        return _browser(
            repository
        ).tree(
            selected_ref,
            path,
        )

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc


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
        return _browser(
            repository
        ).file(
            selected_ref,
            path,
        )

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc


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
        return _browser(
            repository
        ).commits(
            selected_ref,
            limit,
        )

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc


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
    import re as _re, subprocess as _sp
    repository = _resolve_repository(owner, repo, current_user, db)
    if not _re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        raise HTTPException(status_code=400, detail="Invalid commit SHA")

    git_dir = str((Path(settings.repository_storage_path) / repository.storage_key).resolve())

    # Full commit info
    info = _sp.run(
        ["git", "--git-dir", git_dir, "show", "--stat", "--format=%H%n%an%n%ae%n%at%n%s%n%b%n---STAT---", sha],
        capture_output=True, text=True
    )
    if info.returncode != 0:
        raise HTTPException(status_code=404, detail="Commit not found")

    lines = info.stdout.split("\n")
    full_sha = lines[0].strip()
    author_name = lines[1].strip() if len(lines) > 1 else ""
    author_email = lines[2].strip() if len(lines) > 2 else ""
    try:
        committed_at = int(lines[3].strip())
    except Exception:
        committed_at = 0
    subject = lines[4].strip() if len(lines) > 4 else ""
    body_lines = []
    stat_section = False
    file_stats = []
    for l in lines[5:]:
        if l.strip() == "---STAT---":
            stat_section = True
            continue
        if stat_section:
            if "|" in l or l.strip().startswith("..."):
                file_stats.append(l.strip())
        else:
            body_lines.append(l)
    body = "\n".join(body_lines).strip()

    # Unified diff
    diff_proc = _sp.run(
        ["git", "--git-dir", git_dir, "show", "--unified=4", "--format=", sha],
        capture_output=True, text=True, errors="replace"
    )
    diff_text = diff_proc.stdout

    # Parent commit
    parent_proc = _sp.run(
        ["git", "--git-dir", git_dir, "rev-parse", f"{sha}^"],
        capture_output=True, text=True
    )
    parent_sha = parent_proc.stdout.strip() if parent_proc.returncode == 0 else None

    # Detect if author is agent/bot
    is_agent = (
        "bot" in author_name.lower() or
        "agent" in author_name.lower() or
        "bot@" in author_email or
        "agent@" in author_email
    )

    return {
        "sha": full_sha,
        "short_sha": full_sha[:7] if full_sha else sha[:7],
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
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    import re as _re, subprocess as _sp, os as _os
    repository = _resolve_repository(owner, repo, current_user, db)

    if not _re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        raise HTTPException(status_code=400, detail="Invalid commit SHA")

    try:
        browser = _browser(repository)
        git_dir = str(browser.repository_path)

        # Resolve to full SHA
        full_sha = browser.resolve_commit(sha)

        # Get parent of the commit to revert
        parent = _sp.run(
            ["git", "--git-dir", git_dir, "rev-parse", f"{full_sha}^"],
            capture_output=True, text=True
        )
        if parent.returncode != 0:
            raise HTTPException(status_code=422, detail="Cannot revert initial commit (no parent)")
        parent_sha = parent.stdout.strip()

        # Get current branch HEAD
        branch = "main"
        head = _sp.run(
            ["git", "--git-dir", git_dir, "symbolic-ref", "HEAD"],
            capture_output=True, text=True
        )
        if head.returncode == 0:
            branch = head.stdout.strip().replace("refs/heads/", "")
        current_head = _sp.run(
            ["git", "--git-dir", git_dir, "rev-parse", "HEAD"],
            capture_output=True, text=True
        ).stdout.strip()

        # Build a new tree using the parent commit's tree
        # This effectively reverts all changes made in <sha>
        parent_tree = _sp.run(
            ["git", "--git-dir", git_dir, "rev-parse", f"{parent_sha}^{{tree}}"],
            capture_output=True, text=True
        ).stdout.strip()

        # Create the revert commit with parent_tree but current HEAD as parent
        author_name = current_user.username if current_user else "SUTRA"
        author_email = current_user.email if current_user else "bot@sutra.dev"
        env = _os.environ.copy()
        env.update({
            "GIT_DIR": git_dir,
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        })

        new_commit = _sp.run(
            ["git", "--git-dir", git_dir, "commit-tree", parent_tree,
             "-p", current_head, "-m", f"Revert \"{full_sha[:7]}\" via SUTRA"],
            capture_output=True, text=True, env=env
        )
        if new_commit.returncode != 0:
            raise HTTPException(status_code=422, detail=f"Revert commit failed: {new_commit.stderr.strip()}")

        new_sha = new_commit.stdout.strip()

        # Update branch ref to new commit
        update = _sp.run(
            ["git", "--git-dir", git_dir, "update-ref", f"refs/heads/{branch}", new_sha],
            capture_output=True, text=True
        )
        if update.returncode != 0:
            raise HTTPException(status_code=422, detail=f"Failed to update branch: {update.stderr.strip()}")

        return {
            "reverted": full_sha,
            "new_commit": new_sha,
            "message": f"Reverted {full_sha[:7]} successfully",
        }

    except RepositoryBrowserError as exc:
        raise _browser_error(exc) from exc