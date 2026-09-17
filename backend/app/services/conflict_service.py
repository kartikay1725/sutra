import subprocess
from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.repository import Repository


@dataclass
class ConflictResult:
    level: str
    reason: str
    paths: list[str]
    related_change_ids: list[str]


class ConflictService:
    """
    Deterministic conflict analysis for SUTRA Changes.

    File overlap is only the first signal.

    Git's three-way merge analysis is the final authority for
    determining whether two recorded commits can actually coexist.
    """

    LEVEL_NONE = "none"
    LEVEL_OVERLAP = "overlap"
    LEVEL_POTENTIAL = "potential_conflict"
    LEVEL_CONFLICT = "conflict"

    def __init__(self, db: Session):
        self.db = db

    def _repo_path(
        self,
        repository: Repository,
    ):
        return (
            __import__("pathlib").Path(
                settings.repository_storage_path
            )
            / repository.storage_key
        )

    def _git(
        self,
        repository: Repository,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        repo_dir = self._repo_path(repository)
        if not repo_dir.exists():
            return subprocess.CompletedProcess(
                args=list(args),
                returncode=0,
                stdout="",
                stderr="",
            )

        try:
            result = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(repo_dir),
                    *args,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=2.5,
            )
            return result
        except Exception as exc:
            return subprocess.CompletedProcess(
                args=list(args),
                returncode=1,
                stdout="",
                stderr=str(exc),
            )

    def _files_for_change(
        self,
        change_id: str,
    ) -> dict[str, ChangeFile]:

        files = self.db.scalars(
            select(ChangeFile).where(
                ChangeFile.change_id == change_id
            )
        ).all()

        return {
            self._normalize_path(file.path): file
            for file in files
        }

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = str(
            PurePosixPath(
                path.replace("\\", "/")
            )
        )

        while normalized.startswith("./"):
            normalized = normalized[2:]

        return normalized

    def _find_merge_base(
        self,
        repository: Repository,
        first_commit: str,
        second_commit: str,
    ) -> str | None:

        result = self._git(
            repository,
            "merge-base",
            first_commit,
            second_commit,
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    def _git_merge_is_clean(
        self,
        repository: Repository,
        first_commit: str,
        second_commit: str,
    ) -> tuple[bool, str]:

        result = self._git(
            repository,
            "merge-tree",
            "--write-tree",
            first_commit,
            second_commit,
        )

        if result.returncode == 0:
            return (
                True,
                "Git three-way merge analysis completed cleanly.",
            )

        output = (
            result.stdout.strip()
            or result.stderr.strip()
            or "Git reported a merge conflict."
        )

        return (
            False,
            output,
        )

    def compare_changes(
        self,
        source_change: Change,
        target_change: Change,
    ) -> ConflictResult:

        if (
            not source_change.resulting_commit
            or not target_change.resulting_commit
        ):
            return ConflictResult(
                level=self.LEVEL_POTENTIAL,
                reason=(
                    "Both changes must have resulting commits "
                    "before Git merge analysis can run."
                ),
                paths=[],
                related_change_ids=[
                    target_change.id
                ],
            )

        source_files = self._files_for_change(
            source_change.id
        )

        target_files = self._files_for_change(
            target_change.id
        )

        source_paths = set(source_files)
        target_paths = set(target_files)

        overlap = sorted(
            source_paths.intersection(target_paths)
        )

        if not overlap:
            return ConflictResult(
                level=self.LEVEL_NONE,
                reason=(
                    "Changes modify independent files."
                ),
                paths=[],
                related_change_ids=[
                    target_change.id
                ],
            )

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == source_change.repository_id
            )
        )

        if repository is None:
            return ConflictResult(
                level=self.LEVEL_POTENTIAL,
                reason=(
                    "Repository could not be loaded for "
                    "Git merge analysis."
                ),
                paths=overlap,
                related_change_ids=[
                    target_change.id
                ],
            )

        merge_base = self._find_merge_base(
            repository,
            source_change.resulting_commit,
            target_change.resulting_commit,
        )

        if not merge_base:
            return ConflictResult(
                level=self.LEVEL_POTENTIAL,
                reason=(
                    "Git could not determine a common ancestor "
                    "for the two changes."
                ),
                paths=overlap,
                related_change_ids=[
                    target_change.id
                ],
            )

        clean, merge_reason = self._git_merge_is_clean(
            repository,
            source_change.resulting_commit,
            target_change.resulting_commit,
        )

        if clean:
            return ConflictResult(
                level=self.LEVEL_OVERLAP,
                reason=(
                    "Changes overlap on files, but Git "
                    "determines that they can be merged cleanly."
                ),
                paths=overlap,
                related_change_ids=[
                    target_change.id
                ],
            )

        return ConflictResult(
            level=self.LEVEL_CONFLICT,
            reason=(
                "Git three-way merge analysis detected "
                "an actual merge conflict."
            ),
            paths=overlap,
            related_change_ids=[
                target_change.id
            ],
        )

    def analyze(
        self,
        change: Change,
    ) -> ConflictResult:

        related_changes = self.db.scalars(
            select(Change).where(
                Change.repository_id == change.repository_id,
                Change.id != change.id,
                Change.status == "recorded",
            )
        ).all()

        if not related_changes:
            return ConflictResult(
                level=self.LEVEL_NONE,
                reason=(
                    "No recorded changes to compare against."
                ),
                paths=[],
                related_change_ids=[],
            )

        priority = {
            self.LEVEL_NONE: 0,
            self.LEVEL_OVERLAP: 1,
            self.LEVEL_POTENTIAL: 2,
            self.LEVEL_CONFLICT: 3,
        }

        best = ConflictResult(
            level=self.LEVEL_NONE,
            reason="No overlapping files detected.",
            paths=[],
            related_change_ids=[],
        )

        for target in related_changes:
            result = self.compare_changes(
                change,
                target,
            )

            if (
                priority[result.level]
                > priority[best.level]
            ):
                best = result
                continue

            if result.level == best.level:
                best.paths = sorted(
                    set(best.paths).union(
                        result.paths
                    )
                )

                best.related_change_ids = sorted(
                    set(
                        best.related_change_ids
                    ).union(
                        result.related_change_ids
                    )
                )

        return best
