from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class CheckStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CheckConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CheckRunReport:
    check_name: str
    head_sha: str
    status: CheckStatus
    conclusion: Optional[CheckConclusion]
    title: str
    summary: str
    details_url: str
    external_id: str  # SUTRA Change ID / PR ID


class CheckProvider(ABC):
    """
    Substrate adapter interface for publishing and updating status checks / check runs.
    """

    @abstractmethod
    def report_check_run(
        self,
        owner: str,
        name: str,
        report: CheckRunReport,
    ) -> str:
        """
        Publish or update a check run on the substrate.
        Returns the provider check run ID / status reference.
        """
        ...
