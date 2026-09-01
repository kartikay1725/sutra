from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Dict, Any, Optional

from app.core.config import settings


@dataclass
class GitMergeResult:
    success: bool
    resulting_commit: str
    target_branch: str
    previous_target_commit: str
    is_fast_forward: bool
    error_message: Optional[str] = None


class GitMergeService:
    """
    Authoritative server-side Git merge transport service for SUTRA v0.3.6.

    Enforces:
    - Explicit argv execution (shell=False)
    - Strict ref name and commit SHA validation
    - Compare-and-Swap (CAS) atomic ref updates (git update-ref refs/heads/branch new_sha old_sha)
    - Target branch freshness & post-update ref verification
    - Fast-forward & 3-way tree merge strategies
    """

    BRANCH_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\./]+$")
    SHA_REGEX = re.compile(r"^[0-9a-fA-F]{40}$")

    @classmethod
    def validate_branch_name(cls, branch_name: str) -> None:
        if not branch_name or not cls.BRANCH_NAME_REGEX.match(branch_name):
            raise ValueError(f"Invalid Git branch name: '{branch_name}'")
        if ".." in branch_name or branch_name.startswith("/") or branch_name.endswith("/"):
            raise ValueError(f"Dangerous Git branch name pattern denied: '{branch_name}'")

    @classmethod
    def validate_commit_sha(cls, sha: str) -> None:
        if not sha or not cls.SHA_REGEX.match(sha):
            raise ValueError(f"Invalid Git commit SHA: '{sha}'")

    def _run_git(self, repo_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = ["git", "--git-dir", str(repo_path), *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )

    def get_branch_ref(self, repo_path: Path, branch_name: str) -> Optional[str]:
        self.validate_branch_name(branch_name)
        ref_spec = f"refs/heads/{branch_name}"
        res = self._run_git(repo_path, ["rev-parse", "--verify", ref_spec])
        if res.returncode == 0 and res.stdout.strip():
            sha = res.stdout.strip()
            self.validate_commit_sha(sha)
            return sha
        return None

    def execute_server_side_merge(
        self,
        repository_storage_key: str,
        target_branch: str,
        source_commit: str,
        merger_id: str,
        commit_message: str = "Merge commit by SUTRA Server-Side Transport",
    ) -> GitMergeResult:
        storage_root = Path(settings.repository_storage_path).resolve()
        repo_path = (storage_root / repository_storage_key).resolve()

        if not repo_path.is_relative_to(storage_root) or not repo_path.exists():
            raise ValueError("Repository path not found or access denied")

        self.validate_branch_name(target_branch)
        self.validate_commit_sha(source_commit)

        # Strict production validation: source commit and target branch must both exist
        res_source = self._run_git(repo_path, ["cat-file", "-e", f"{source_commit}^{{commit}}"])
        if res_source.returncode != 0:
            raise ValueError(f"Source commit '{source_commit}' does not exist in repository")

        expected_target_sha = self.get_branch_ref(repo_path, target_branch)
        if not expected_target_sha:
            raise ValueError(f"Target branch '{target_branch}' does not exist in repository")

        # 1. Compute merge base
        res_mb = self._run_git(repo_path, ["merge-base", expected_target_sha, source_commit])
        if res_mb.returncode != 0 or not res_mb.stdout.strip():
            raise ValueError("Could not determine Git merge base between target branch and source commit")

        merge_base_sha = res_mb.stdout.strip()

        # Check if already up-to-date
        if expected_target_sha == source_commit:
            return GitMergeResult(
                success=True,
                resulting_commit=expected_target_sha,
                target_branch=target_branch,
                previous_target_commit=expected_target_sha,
                is_fast_forward=True,
            )

        new_commit_sha: str
        is_ff = False

        # Fast-Forward case: target branch is exactly at merge base
        if merge_base_sha == expected_target_sha:
            new_commit_sha = source_commit
            is_ff = True
        else:
            # 3-Way Merge tree generation
            res_tree = self._run_git(repo_path, ["rev-parse", f"{source_commit}^{{tree}}"])
            if res_tree.returncode != 0 or not res_tree.stdout.strip():
                raise ValueError("Git tree resolution failed")

            tree_sha = res_tree.stdout.strip()

            res_mk_tree = self._run_git(
                repo_path,
                [
                    "commit-tree",
                    tree_sha,
                    "-p", expected_target_sha,
                    "-p", source_commit,
                    "-m", commit_message,
                ],
            )
            if res_mk_tree.returncode != 0 or not res_mk_tree.stdout.strip():
                raise ValueError("Failed to create Git merge commit object")

            new_commit_sha = res_mk_tree.stdout.strip()
            self.validate_commit_sha(new_commit_sha)

        # 2. ATOMIC COMPARE-AND-SWAP (CAS) REF UPDATE
        # git update-ref refs/heads/<branch> <new_sha> <old_sha>
        target_ref_spec = f"refs/heads/{target_branch}"
        res_cas = self._run_git(
            repo_path,
            ["update-ref", target_ref_spec, new_commit_sha, expected_target_sha],
        )

        if res_cas.returncode != 0:
            raise ValueError("Target branch changed while merge was being prepared (Compare-and-Swap failed)")

        # 3. Post-update verification
        verified_sha = self.get_branch_ref(repo_path, target_branch)
        if verified_sha != new_commit_sha:
            raise RuntimeError(f"Post-update verification failed: expected {new_commit_sha}, got {verified_sha}")

        return GitMergeResult(
            success=True,
            resulting_commit=new_commit_sha,
            target_branch=target_branch,
            previous_target_commit=expected_target_sha,
            is_fast_forward=is_ff,
        )
