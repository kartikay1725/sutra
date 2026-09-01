import re
import subprocess
from pathlib import Path


class RepositoryBrowserError(ValueError):
    pass


class RepositoryBrowserService:
    """
    Read-only Git-backed repository browsing for the SUTRA web product.

    All Git operations use explicit argv lists with shell execution
    disabled. This service never mutates repository state.
    """

    MAX_FILE_BYTES = 2 * 1024 * 1024
    MAX_COMMITS = 100
    MAX_TREE_ENTRIES = 2000

    _REF_RE = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$"
    )

    def __init__(self, repository_path: Path):
        self.repository_path = Path(
            repository_path
        ).resolve()

        if (
            not self.repository_path.exists()
            or not self.repository_path.is_dir()
        ):
            raise RepositoryBrowserError(
                "Git repository storage not found"
            )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @classmethod
    def validate_ref(cls, ref: str) -> str:
        if (
            not ref
            or len(ref) > 256
            or not cls._REF_RE.fullmatch(ref)
        ):
            raise RepositoryBrowserError(
                "Invalid Git ref"
            )

        if (
            ".." in ref
            or "//" in ref
            or ref.endswith("/")
        ):
            raise RepositoryBrowserError(
                "Invalid Git ref"
            )

        return ref

    @staticmethod
    def validate_path(path: str) -> str:
        if path is None or path == "":
            return ""

        if len(path) > 4096:
            raise RepositoryBrowserError(
                "Repository path is too long"
            )

        if "\x00" in path or "\\" in path:
            raise RepositoryBrowserError(
                "Invalid repository path"
            )

        if path.startswith("/"):
            raise RepositoryBrowserError(
                "Invalid repository path"
            )

        parts = path.split("/")

        if any(
            part in {"", ".", ".."}
            for part in parts
        ):
            raise RepositoryBrowserError(
                "Invalid repository path"
            )

        return path

    # ---------------------------------------------------------
    # GIT EXECUTION
    # ---------------------------------------------------------

    def _git(
        self,
        *args: str,
        text: bool = True,
    ) -> subprocess.CompletedProcess:

        return subprocess.run(
            [
                "git",
                "--git-dir",
                str(self.repository_path),
                *args,
            ],
            capture_output=True,
            text=text,
            check=False,
        )

    # ---------------------------------------------------------
    # REF RESOLUTION
    # ---------------------------------------------------------

    def resolve_commit(
        self,
        ref: str,
    ) -> str:

        ref = self.validate_ref(ref)

        result = self._git(
            "rev-parse",
            "--verify",
            "--quiet",
            f"{ref}^{{commit}}",
        )

        if result.returncode != 0:
            raise RepositoryBrowserError(
                "Git ref not found"
            )

        commit = result.stdout.strip()

        if not re.fullmatch(
            r"[0-9a-fA-F]{40}",
            commit,
        ):
            raise RepositoryBrowserError(
                "Invalid Git commit returned by storage"
            )

        return commit

    # ---------------------------------------------------------
    # BRANCHES
    # ---------------------------------------------------------

    def branches(self) -> list[dict[str, str | bool]]:

        result = self._git(
            "for-each-ref",
            "--format=%(refname:short) %(objectname)",
            "refs/heads/",
        )

        if result.returncode != 0:
            raise RepositoryBrowserError(
                result.stderr.strip()
                or "Unable to read branches"
            )

        branches = []

        for record in result.stdout.splitlines():

            if not record.strip():
                continue

            parts = record.strip().split(
                " ",
                1,
            )

            if len(parts) != 2:
                continue

            name, sha = parts

            if not name:
                continue

            if not re.fullmatch(
                r"[0-9a-fA-F]{40}",
                sha,
            ):
                continue

            branches.append(
                {
                    "name": name,
                    "commit": sha,
                    "protected": name == "main",
                }
            )

        branches.sort(
            key=lambda item: (
                not bool(item["protected"]),
                str(item["name"]),
            )
        )

        return branches

    # ---------------------------------------------------------
    # DIRECTORY TREE
    # ---------------------------------------------------------

    def tree(
        self,
        ref: str,
        path: str = "",
    ) -> dict:

        commit = self.resolve_commit(ref)

        path = self.validate_path(path)

        treeish = (
            commit
            if not path
            else f"{commit}:{path}"
        )

        result = self._git(
            "ls-tree",
            "-z",
            "--long",
            treeish,
            text=True,
        )

        if result.returncode != 0:
            raise RepositoryBrowserError(
                "Repository path not found"
            )

        entries = []

        for record in result.stdout.split("\x00"):

            if not record:
                continue

            try:
                header, name = record.split(
                    "\t",
                    1,
                )

                mode, kind, sha, size = (
                    header.split(
                        " ",
                        3,
                    )
                )

            except ValueError:
                continue

            entries.append(
                {
                    "name": name,
                    "path": (
                        f"{path}/{name}"
                        if path
                        else name
                    ),
                    "type": (
                        "directory"
                        if kind == "tree"
                        else "file"
                    ),
                    "mode": mode,
                    "sha": sha,
                    "size": (
                        None
                        if size.strip() == "-"
                        else int(size.strip())
                    ),
                }
            )

            if (
                len(entries)
                >= self.MAX_TREE_ENTRIES
            ):
                break

        entries.sort(
            key=lambda item: (
                item["type"] != "directory",
                str(item["name"]).lower(),
            )
        )

        return {
            "ref": ref,
            "commit": commit,
            "path": path,
            "entries": entries,
            "truncated": (
                len(entries)
                >= self.MAX_TREE_ENTRIES
            ),
        }

    # ---------------------------------------------------------
    # FILE CONTENT
    # ---------------------------------------------------------

    def file(
        self,
        ref: str,
        path: str,
    ) -> dict:

        commit = self.resolve_commit(ref)

        path = self.validate_path(path)

        if not path:
            raise RepositoryBrowserError(
                "A file path is required"
            )

        object_spec = (
            f"{commit}:{path}"
        )

        type_result = self._git(
            "cat-file",
            "-t",
            object_spec,
        )

        if (
            type_result.returncode != 0
            or type_result.stdout.strip()
            != "blob"
        ):
            raise RepositoryBrowserError(
                "File not found"
            )

        size_result = self._git(
            "cat-file",
            "-s",
            object_spec,
        )

        if size_result.returncode != 0:
            raise RepositoryBrowserError(
                "Unable to read file metadata"
            )

        try:
            size = int(
                size_result.stdout.strip()
            )
        except ValueError as exc:
            raise RepositoryBrowserError(
                "Invalid file size"
            ) from exc

        if size > self.MAX_FILE_BYTES:
            raise RepositoryBrowserError(
                (
                    "File exceeds web preview "
                    f"limit of {self.MAX_FILE_BYTES} bytes"
                )
            )

        content_result = self._git(
            "show",
            object_spec,
            text=False,
        )

        if content_result.returncode != 0:
            raise RepositoryBrowserError(
                "Unable to read file"
            )

        raw = content_result.stdout

        try:
            content = raw.decode(
                "utf-8"
            )
            encoding = "utf-8"

        except UnicodeDecodeError:
            content = raw.decode(
                "utf-8",
                errors="replace",
            )
            encoding = "utf-8-replaced"

        return {
            "ref": ref,
            "commit": commit,
            "path": path,
            "size": size,
            "encoding": encoding,
            "content": content,
        }

    # ---------------------------------------------------------
    # COMMIT HISTORY
    # ---------------------------------------------------------

    def commits(
        self,
        ref: str,
        limit: int = 30,
    ) -> dict:

        commit = self.resolve_commit(ref)

        limit = max(
            1,
            min(
                int(limit),
                self.MAX_COMMITS,
            ),
        )

        result = self._git(
            "log",
            f"-n{limit}",
            "--date-order",
            "--format=%H%x00%an%x00%ae%x00%at%x00%s%x1e",
            commit,
        )

        if result.returncode != 0:
            raise RepositoryBrowserError(
                result.stderr.strip()
                or "Unable to read commit history"
            )

        commits = []

        for record in result.stdout.split(
            "\x1e"
        ):

            if not record.strip():
                continue

            fields = (
                record
                .strip("\r\n")
                .split("\x00")
            )

            if len(fields) != 5:
                continue

            (
                sha,
                author_name,
                author_email,
                timestamp,
                subject,
            ) = fields

            if not re.fullmatch(
                r"[0-9a-fA-F]{40}",
                sha,
            ):
                continue

            try:
                committed_at = int(
                    timestamp
                )
            except ValueError:
                continue

            commits.append(
                {
                    "sha": sha,
                    "short_sha": sha[:7],
                    "author_name": author_name,
                    "author_email": author_email,
                    "committed_at": committed_at,
                    "subject": subject,
                }
            )

        return {
            "ref": ref,
            "head": commit,
            "commits": commits,
        }