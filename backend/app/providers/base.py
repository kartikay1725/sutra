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


# ============================================================
# ISSUE PROVIDER TYPES
# ============================================================

@dataclass(frozen=True)
class ProviderIssue:
    id: str
    number: int
    title: str
    body: Optional[str]
    state: str
    author_login: Optional[str]
    author_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    html_url: str
    labels: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderIssueComment:
    id: str
    issue_number: int
    body: str
    author_login: Optional[str]
    author_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    html_url: str


class RepositoryProvider(ABC):
    """
    Authoritative substrate interface for repository, branch, commit, file,
    diff, pull request, merge, and issue operations.

    Check publishing is strictly isolated in CheckProvider/CheckService.

    For provider-backed repositories such as GitHub:
        - GitHub remains the source of truth for issues.
        - SUTRA stores governance/provenance/linkage around those issues.
    """

    # ========================================================
    # REPOSITORY
    # ========================================================

    @abstractmethod
    def get_repository_metadata(
        self,
        owner: str,
        name: str,
    ) -> ProviderRepoMetadata:
        """Fetch repository details and detected capabilities."""
        ...

    def get_raw_repository(
        self,
        owner: str,
        name: str,
    ) -> Dict[str, Any]:
        """Fetch raw substrate repository details including fork, parent, and permissions."""
        return {}

    def create_fork(
        self,
        owner: str,
        name: str,
        organization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a fork of an upstream repository on the substrate."""
        raise NotImplementedError("Fork creation is not supported by this provider")

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
        """Update repository configuration on the substrate."""
        return {}

    def delete_repository(
        self,
        owner: str,
        name: str,
    ) -> bool:
        """Delete repository on the substrate if supported."""
        return False

    # ========================================================
    # BRANCHES
    # ========================================================

    @abstractmethod
    def get_branch(
        self,
        owner: str,
        name: str,
        branch: str,
    ) -> Optional[ProviderBranch]:
        """Query branch existence and current HEAD commit."""
        ...

    @abstractmethod
    def list_branches(
        self,
        owner: str,
        name: str,
    ) -> List[ProviderBranch]:
        """List all active branch references."""
        ...

    # ========================================================
    # COMMITS
    # ========================================================

    @abstractmethod
    def get_commit(
        self,
        owner: str,
        name: str,
        sha: str,
    ) -> Optional[ProviderCommit]:
        """Fetch commit object details."""
        ...

    @abstractmethod
    def commit_exists(
        self,
        owner: str,
        name: str,
        sha: str,
    ) -> bool:
        """Verify whether a commit SHA exists on the substrate."""
        ...

    @abstractmethod
    def get_diff_stats(
        self,
        owner: str,
        name: str,
        base: str,
        head: str,
    ) -> ProviderDiffStat:
        """Calculate diff statistics between two commits/refs."""
        ...

    # ========================================================
    # FILES
    # ========================================================

    @abstractmethod
    def read_file(
        self,
        owner: str,
        name: str,
        path: str,
        ref: str,
    ) -> bytes:
        """Read file contents at the specified git ref."""
        ...

    @abstractmethod
    def list_files(
        self,
        owner: str,
        name: str,
        path: str,
        ref: str,
    ) -> List[Dict[str, Any]]:
        """List directory tree contents at the specified git ref."""
        ...

    # ========================================================
    # PULL REQUESTS
    # ========================================================

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
    def get_pull_request(
        self,
        owner: str,
        name: str,
        pr_number: int,
    ) -> Optional[ProviderPullRequest]:
        """Fetch pull request details and mergeability."""
        ...

    def list_pull_requests(
        self,
        owner: str,
        name: str,
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProviderPullRequest]:
        """List pull requests from the authoritative substrate."""
        return []

    @abstractmethod
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
        """Execute authoritative merge on the substrate."""
        ...

    # ========================================================
    # ISSUES
    # ========================================================

    
    def list_issues(
        self,
        owner: str,
        name: str,
        state: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProviderIssue]:
        """
        List issues from the authoritative repository substrate.

        For GitHub-backed repositories this maps directly to GitHub Issues.
        """
        raise NotImplementedError(
            "This repository provider does not support issues."
        )
 

    
    def get_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> Optional[ProviderIssue]:
        """Fetch one issue from the authoritative substrate."""
        raise NotImplementedError(
            "This repository provider does not support issues."
        )

    
    def create_issue(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
    ) -> ProviderIssue:
        """Create an issue on the authoritative substrate."""
        raise NotImplementedError(
            "This repository provider does not support issues."
        )

   
    def list_issue_comments(
        self,
        owner: str,
        name: str,
        issue_number: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProviderIssueComment]:
        """List comments belonging to a provider issue."""
        raise NotImplementedError(
            "This repository provider does not support issues."
        )

    
    def create_issue_comment(
        self,
        owner: str,
        name: str,
        issue_number: int,
        body: str,
    ) -> ProviderIssueComment:
        """Create a comment on a provider issue."""
        raise NotImplementedError(
            "This repository provider does not support issues."
        )

    
    def close_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> ProviderIssue:
        """Close an issue on the authoritative substrate."""
        raise NotImplementedError(
            "This repository provider does not support issues."
        )

    
    def reopen_issue(
        self,
        owner: str,
        name: str,
        issue_number: int,
    ) -> ProviderIssue:
        """Reopen an issue on the authoritative substrate."""
        raise NotImplementedError(
            "This repository provider does not support issues."
        )

    def list_check_runs(
        self,
        owner: str,
        name: str,
        ref: str,
    ) -> List[Dict[str, Any]]:
        """List check runs for a commit ref/SHA on the authoritative substrate."""
        return []

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
        """Create or update a check run on the authoritative substrate."""
        raise NotImplementedError(
            "This repository provider does not support check runs."
        )