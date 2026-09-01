from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass(frozen=True)
class ProviderRepoMetadata:
    provider_type: str  # "local" | "github"
    owner: str
    name: str
    default_branch: str
    is_private: bool
    clone_url: str
    external_id: Optional[str] = None
    capabilities: Dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderBranch:
    name: str
    commit_sha: str
    is_protected: bool = False


@dataclass(frozen=True)
class ProviderCommit:
    sha: str
    message: str
    author_name: str
    author_email: str
    committed_at: datetime
    parent_shas: List[str] = field(default_factory=list)
    tree_sha: str = ""


@dataclass(frozen=True)
class ProviderDiffStat:
    files_changed: int
    additions: int
    deletions: int
    changed_files: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderPullRequest:
    number: int
    title: str
    body: Optional[str]
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    is_merged: bool = False
    is_closed: bool = False
    mergeable: Optional[bool] = None
    html_url: str = ""


@dataclass(frozen=True)
class ProviderMergeResult:
    success: bool
    merge_commit_sha: Optional[str]
    message: str


class RepositoryProvider(ABC):
    """
    Authoritative substrate interface for repository, branch, commit, file,
    diff, pull request, and merge operations.
    
    Check publishing is strictly isolated in CheckProvider/CheckService.
    """

    @abstractmethod
    def get_repository_metadata(self, owner: str, name: str) -> ProviderRepoMetadata:
        """Fetch repository details and detected capabilities."""
        ...

    @abstractmethod
    def get_branch(self, owner: str, name: str, branch: str) -> Optional[ProviderBranch]:
        """Query branch existence and current HEAD commit."""
        ...

    @abstractmethod
    def list_branches(self, owner: str, name: str) -> List[ProviderBranch]:
        """List all active branch references."""
        ...

    @abstractmethod
    def get_commit(self, owner: str, name: str, sha: str) -> Optional[ProviderCommit]:
        """Fetch commit object details."""
        ...

    @abstractmethod
    def commit_exists(self, owner: str, name: str, sha: str) -> bool:
        """Verify whether a commit SHA exists on the substrate."""
        ...

    @abstractmethod
    def get_diff_stats(self, owner: str, name: str, base: str, head: str) -> ProviderDiffStat:
        """Calculate diff statistics (files, additions, deletions) between two commits/refs."""
        ...

    @abstractmethod
    def read_file(self, owner: str, name: str, path: str, ref: str) -> bytes:
        """Read file contents at the specified git ref."""
        ...

    @abstractmethod
    def list_files(self, owner: str, name: str, path: str, ref: str) -> List[Dict[str, Any]]:
        """List directory tree contents at the specified git ref."""
        ...

    @abstractmethod
    def create_pull_request(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> ProviderPullRequest:
        """Create a pull request on the substrate."""
        ...

    @abstractmethod
    def get_pull_request(self, owner: str, name: str, pr_number: int) -> Optional[ProviderPullRequest]:
        """Fetch pull request details and mergeability."""
        ...

    @abstractmethod
    def merge_pull_request(
        self,
        owner: str,
        name: str,
        pr_number: int,
        commit_title: str,
        commit_message: str,
        expected_head_sha: str,
        method: str = "squash",  # "merge" | "squash" | "rebase"
    ) -> ProviderMergeResult:
        """Execute authoritative merge on the substrate."""
        ...
