import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.services.git_merge_service import GitMergeService
from app.providers.base import (
    RepositoryProvider,
    ProviderRepoMetadata,
    ProviderBranch,
    ProviderCommit,
    ProviderDiffStat,
    ProviderPullRequest,
    ProviderMergeResult,
)


class LocalRepositoryProvider(RepositoryProvider):
    """
    Substrate adapter wrapping SUTRA local bare Git repository storage,
    subprocess Git operations, and GitMergeService.
    """

    def __init__(self, db: Session):
        self.db = db
        self.merge_service = GitMergeService()

    def _resolve_repo_path(self, owner: str, name: str) -> Path:
        slug = name.lower()
        repo = self.db.scalar(
            select(Repository).where(
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            # Fallback direct lookup by storage path if name is a storage_key
            storage_root = Path(settings.repository_storage_path).resolve()
            direct_path = (storage_root / name).resolve()
            if direct_path.exists() and direct_path.is_relative_to(storage_root):
                return direct_path
            raise ValueError(f"Local repository '{owner}/{name}' not found")

        storage_root = Path(settings.repository_storage_path).resolve()
        repo_path = (storage_root / repo.storage_key).resolve()
        if not repo_path.is_relative_to(storage_root) or not repo_path.exists():
            raise ValueError(f"Local repository path for '{slug}' is invalid or missing")
        return repo_path

    def _run_git(self, repo_path: Path, args: List[str]) -> subprocess.CompletedProcess[str]:
        cmd = ["git", "--git-dir", str(repo_path), *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )

    def get_repository_metadata(self, owner: str, name: str) -> ProviderRepoMetadata:
        slug = name.lower()
        repo = self.db.scalar(
            select(Repository).where(
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )
        default_branch = repo.default_branch if repo else "main"
        is_private = repo.visibility == "private" if repo else True
        external_id = repo.id if repo else name

        clone_url = f"{settings.sutra_base_url}/git/{owner}/{name}.git"
        return ProviderRepoMetadata(
            provider_type="local",
            owner=owner,
            name=name,
            default_branch=default_branch,
            is_private=is_private,
            clone_url=clone_url,
            external_id=external_id,
            capabilities={
                "rulesets": False,
                "pre_receive_hook": True,
                "check_runs": False,
            },
        )

    def get_branch(self, owner: str, name: str, branch: str) -> Optional[ProviderBranch]:
        repo_path = self._resolve_repo_path(owner, name)
        res = self._run_git(repo_path, ["rev-parse", "--verify", f"refs/heads/{branch}"])
        if res.returncode == 0 and res.stdout.strip():
            return ProviderBranch(
                name=branch,
                commit_sha=res.stdout.strip(),
                is_protected=False,
            )
        return None

    def list_branches(self, owner: str, name: str) -> List[ProviderBranch]:
        repo_path = self._resolve_repo_path(owner, name)
        res = self._run_git(repo_path, ["for-each-ref", "--format=%(refname:short)|%(objectname)", "refs/heads/"])
        branches = []
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                if "|" in line:
                    b_name, b_sha = line.split("|", 1)
                    branches.append(ProviderBranch(name=b_name.strip(), commit_sha=b_sha.strip()))
        return branches

    def get_commit(self, owner: str, name: str, sha: str) -> Optional[ProviderCommit]:
        repo_path = self._resolve_repo_path(owner, name)
        # Format: %H%x00%an%x00%ae%x00%aI%x00%P%x00%T%x00%B
        res = self._run_git(
            repo_path,
            ["log", "-1", "--format=%H%x00%an%x00%ae%x00%aI%x00%P%x00%T%x00%B", sha],
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None

        parts = res.stdout.split("\x00")
        if len(parts) < 7:
            return None

        c_sha, aname, aemail, adate_str, parents_str, tree_sha, msg = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
        try:
            c_date = datetime.fromisoformat(adate_str)
        except Exception:
            c_date = datetime.now(timezone.utc)

        parents = [p.strip() for p in parents_str.split() if p.strip()]
        return ProviderCommit(
            sha=c_sha.strip(),
            message=msg.strip(),
            author_name=aname.strip(),
            author_email=aemail.strip(),
            committed_at=c_date,
            parent_shas=parents,
            tree_sha=tree_sha.strip(),
        )

    def commit_exists(self, owner: str, name: str, sha: str) -> bool:
        try:
            repo_path = self._resolve_repo_path(owner, name)
            res = self._run_git(repo_path, ["cat-file", "-e", f"{sha}^{{commit}}"])
            return res.returncode == 0
        except Exception:
            return False

    def get_diff_stats(self, owner: str, name: str, base: str, head: str) -> ProviderDiffStat:
        repo_path = self._resolve_repo_path(owner, name)
        res = self._run_git(repo_path, ["diff", "--numstat", base, head])
        files_changed = 0
        additions = 0
        deletions = 0
        changed_files = []

        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    add_str, del_str, file_path = parts[0], parts[1], parts[2]
                    a_count = int(add_str) if add_str.isdigit() else 0
                    d_count = int(del_str) if del_str.isdigit() else 0
                    files_changed += 1
                    additions += a_count
                    deletions += d_count
                    changed_files.append({
                        "filename": file_path,
                        "additions": a_count,
                        "deletions": d_count,
                    })

        return ProviderDiffStat(
            files_changed=files_changed,
            additions=additions,
            deletions=deletions,
            changed_files=changed_files,
        )

    def read_file(self, owner: str, name: str, path: str, ref: str) -> bytes:
        repo_path = self._resolve_repo_path(owner, name)
        clean_path = path.lstrip("/")
        res = subprocess.run(
            ["git", "--git-dir", str(repo_path), "show", f"{ref}:{clean_path}"],
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            raise FileNotFoundError(f"File '{path}' not found at ref '{ref}' in local repo")
        return res.stdout

    def list_files(self, owner: str, name: str, path: str, ref: str) -> List[Dict[str, Any]]:
        repo_path = self._resolve_repo_path(owner, name)
        tree_target = f"{ref}:{path.lstrip('/')}" if path and path != "/" else ref
        res = self._run_git(repo_path, ["ls-tree", "-l", tree_target])
        items = []
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    mode, ftype, sha = parts[0], parts[1], parts[2]
                    fname = line.split(maxsplit=4)[-1]
                    items.append({
                        "name": fname,
                        "type": "dir" if ftype == "tree" else "file",
                        "sha": sha,
                        "mode": mode,
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
        # In local provider, SUTRA's PullRequest database record is the PR
        slug = name.lower()
        repo = self.db.scalar(
            select(Repository).where(
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )
        repo_id = repo.id if repo else ""
        
        # Determine latest PR number for this repo
        count = len(
            self.db.scalars(
                select(PullRequest).where(PullRequest.repository_id == repo_id)
            ).all()
        )
        pr_number = count + 1
        
        head_b = self.get_branch(owner, name, head_branch)
        base_b = self.get_branch(owner, name, base_branch)
        
        return ProviderPullRequest(
            number=pr_number,
            title=title,
            body=body,
            head_ref=head_branch,
            head_sha=head_b.commit_sha if head_b else "",
            base_ref=base_branch,
            base_sha=base_b.commit_sha if base_b else "",
            is_merged=False,
            is_closed=False,
            mergeable=True,
            html_url=f"{settings.sutra_base_url}/repositories/{owner}/{name}/pull-requests/{pr_number}",
        )

    def get_pull_request(self, owner: str, name: str, pr_number: int) -> Optional[ProviderPullRequest]:
        slug = name.lower()
        repo = self.db.scalar(
            select(Repository).where(
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            return None
            
        prs = self.db.scalars(
            select(PullRequest)
            .where(PullRequest.repository_id == repo.id)
            .order_by(PullRequest.created_at.asc())
        ).all()
        
        if 0 < pr_number <= len(prs):
            pr = prs[pr_number - 1]
            return ProviderPullRequest(
                number=pr_number,
                title=pr.title,
                body=pr.description,
                head_ref=pr.source_branch or "",
                head_sha=pr.source_commit or "",
                base_ref=pr.target_branch,
                base_sha=pr.target_commit or "",
                is_merged=pr.status == PullRequest.STATUS_MERGED,
                is_closed=pr.status in {PullRequest.STATUS_CLOSED, PullRequest.STATUS_REJECTED},
                mergeable=True,
                html_url=f"{settings.sutra_base_url}/repositories/{owner}/{name}/pull-requests/{pr_number}",
            )
        return None

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
        slug = name.lower()
        repo = self.db.scalar(
            select(Repository).where(
                Repository.slug == slug,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            return ProviderMergeResult(success=False, merge_commit_sha=None, message="Repository not found")

        prs = self.db.scalars(
            select(PullRequest)
            .where(PullRequest.repository_id == repo.id)
            .order_by(PullRequest.created_at.asc())
        ).all()
        
        if not (0 < pr_number <= len(prs)):
            return ProviderMergeResult(success=False, merge_commit_sha=None, message=f"PR #{pr_number} not found")

        pr = prs[pr_number - 1]
        try:
            res = self.merge_service.execute_server_side_merge(
                repository_storage_key=repo.storage_key,
                target_branch=pr.target_branch,
                source_commit=expected_head_sha,
                merger_id="sutra_local_provider",
                commit_message=f"{commit_title}\n\n{commit_message}" if commit_message else commit_title,
            )
            return ProviderMergeResult(
                success=res.success,
                merge_commit_sha=res.resulting_commit,
                message="Local merge successful",
            )
        except Exception as e:
            return ProviderMergeResult(
                success=False,
                merge_commit_sha=None,
                message=f"Local merge failed: {e}",
            )
