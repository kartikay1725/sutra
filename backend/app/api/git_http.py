from app.api import pull_requests
from app.api import pull_requests
from app.api import agent_reviews
import base64
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.repository import Repository
from app.models.user import User
from app.services.git_push_event_service import GitPushEventService
from app.services.repository_service import RepositoryService
from app.services.authorization_service import AuthorizationService


router = APIRouter(
    prefix="/git",
    tags=["git"],
)


ZERO_SHA = "0" * 40


from app.models.agent_registration import AgentRegistrationRequest


@dataclass
class GitPrincipal:
    kind: str
    username: str
    user: User | None = None
    agent: Agent | None = None
    registration_request: AgentRegistrationRequest | None = None

    @property
    def owner_id(self) -> str | None:
        if self.user is not None:
            return self.user.id

        if self.agent is not None:
            return self.agent.owner_id

        return None

    @property
    def actor_id(self) -> str | None:
        if self.agent is not None:
            return self.agent.id

        return None


def authenticate_basic(
    request: Request,
    db: Session,
) -> GitPrincipal | None:

    authorization = request.headers.get("authorization")

    if not authorization:
        return None

    if not authorization.lower().startswith("basic "):
        return None

    try:
        encoded = authorization.split(
            " ",
            1,
        )[1]

        decoded = base64.b64decode(
            encoded,
            validate=True,
        ).decode("utf-8")

        username, password = decoded.split(
            ":",
            1,
        )

    except Exception:
        return None

    # ---------------------------------------------------------
    # Agent authentication
    #
    # Git username:
    #     agent token prefix
    #
    # Git password:
    #     ACTIVE AgentSession token
    # ---------------------------------------------------------
    if password.startswith("sutra_session_"):
        from app.api.agent_dependencies import validate_agent_session_token
        try:
            session = validate_agent_session_token(password, db)
        except HTTPException:
            # If the session is invalid, expired, revoked, etc, it raises a 401.
            # We catch it here to return None and let the standard Git challenge trigger.
            return None

        # Fetch the agent directly from the session
        agent = db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
            )
        )

        # The Git username MUST match the agent's token prefix
        if agent is None or agent.token_prefix != username:
            return None

        return GitPrincipal(
            kind="agent",
            username=agent.name,
            agent=agent,
        )

    # ---------------------------------------------------------
    # Temporary push token authentication
    # ---------------------------------------------------------
    if password.startswith("sutra_temp_push_"):
        import hashlib
        from app.core.redis_service import redis_service
        token_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        token_key = f"temp_push:{token_hash}"

        # 1. Try atomic Redis consumption (single-use guarantee across concurrent requests)
        token_data = None
        try:
            token_data = redis_service.consume_token_atomic(token_key)
        except Exception:
            token_data = None

        if token_data and isinstance(token_data, dict):
            reg_id = token_data.get("registration_id")
            user_id = token_data.get("user_id")
            user = db.scalar(select(User).where(User.id == user_id))
            r = db.scalar(select(AgentRegistrationRequest).where(AgentRegistrationRequest.id == reg_id))
            if r and not r.is_temporary_token_used:
                r.is_temporary_token_used = True
                db.commit()
                return GitPrincipal(
                    kind="temp_agent",
                    username=f"temp_agent_{r.id[:8]}",
                    user=user,
                    registration_request=r,
                )

        # 2. Authoritative PostgreSQL fallback
        reqs = db.scalars(
            select(AgentRegistrationRequest).where(
                AgentRegistrationRequest.status == "pending",
                AgentRegistrationRequest.is_temporary_token_used.is_(False),
            )
        ).all()
        for r in reqs:
            if r.temporary_token_hash and verify_password(password, r.temporary_token_hash):
                r.is_temporary_token_used = True
                db.commit()
                user = db.scalar(select(User).where(User.id == r.requested_for_user_id))
                return GitPrincipal(
                    kind="temp_agent",
                    username=f"temp_agent_{r.id[:8]}",
                    user=user,
                    registration_request=r,
                )

    # ---------------------------------------------------------
    # Human authentication
    # ---------------------------------------------------------

    user = db.scalar(
        select(User).where(
            User.username == username,
        )
    )

    if user is None:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return GitPrincipal(
        kind="human",
        username=user.username,
        user=user,
    )


def find_repository(
    owner: str,
    repo: str,
    db: Session,
) -> tuple[Repository, User]:

    repo_name = repo.removesuffix(".git")

    result = db.execute(
        select(Repository, User)
        .join(
            User,
            User.id == Repository.owner_id,
        )
        .where(
            User.username == owner,
            Repository.slug == repo_name.lower(),
            Repository.deleted_at.is_(None),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return result


def authenticate_git_request(
    request: Request,
    db: Session,
) -> GitPrincipal:

    principal = authenticate_basic(
        request,
        db,
    )

    if principal is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={
                "WWW-Authenticate": (
                    'Basic realm="SUTRA Git"'
                ),
            },
        )

    return principal




def get_branch_refs(
    repository_path: Path,
) -> dict[str, str]:

    result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repository_path),
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/heads/",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise ValueError(
            result.stderr.strip()
            or "Unable to read repository refs"
        )

    refs: dict[str, str] = {}

    for line in result.stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        parts = line.split(
            " ",
            1,
        )

        if len(parts) != 2:
            continue

        ref, commit = parts

        if not ref.startswith("refs/heads/"):
            continue

        refs[ref] = commit

    return refs

def authorize_repository_access(
    principal: GitPrincipal,
    repository: Repository,
    repository_owner: User,
    db: Session,
    capability: str,
) -> None:

    if principal.kind == "human":
        if principal.owner_id != repository_owner.id:
            if capability == AuthorizationService.READ and repository.visibility == "public":
                return
            raise HTTPException(
                status_code=403,
                detail="Repository access denied",
            )
        return

    if principal.kind == "temp_agent":
        if capability != AuthorizationService.WRITE:
            raise HTTPException(
                status_code=403,
                detail="Temporary push token only authorized for Git write/push operations.",
            )
        req_repo = principal.registration_request.requested_repo_name
        if repository.slug.lower() != req_repo.lower():
            raise HTTPException(
                status_code=403,
                detail=f"Temporary push token only authorized for repository: {req_repo}",
            )
        return

    if principal.agent is None:
        raise HTTPException(
            status_code=401,
            detail="Agent identity unavailable",
        )

    actor = db.scalar(
        select(Actor).where(
            Actor.id == principal.agent.id,
            Actor.type == "agent",
            Actor.owner_id == principal.agent.owner_id,
        )
    )

    if actor is None:
        raise HTTPException(
            status_code=403,
            detail="Agent actor identity not found",
        )

    decision = AuthorizationService.check(
        actor=actor,
        repository=repository,
        capability=capability,
        db=db,
    )

    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail=decision.reason,
        )


def record_agent_push_event(
    db: Session,
    repository: Repository,
    principal: GitPrincipal,
    before_refs: dict[str, str],
    after_refs: dict[str, str],
) -> None:
    """Persist the successful Git transport fact only.

    Semantic Change derivation is intentionally deferred to
    GitPushEventProcessor so a successful Git push has exactly
    one source event and cannot create duplicate Changes.
    """

    if principal.kind != "agent" or principal.agent is None:
        return

    actor = db.scalar(
        select(Actor).where(
            Actor.id == principal.agent.id,
            Actor.type == "agent",
            Actor.owner_id == principal.agent.owner_id,
        )
    )

    if actor is None:
        raise ValueError(
            "Agent actor identity not found"
        )

    GitPushEventService(db).create_event(
        repository=repository,
        actor=actor,
        before_refs=before_refs,
        after_refs=after_refs,
    )
    db.commit()


async def run_git_http_backend(
    request: Request,
    repository: Repository,
    owner: User,
    git_path: str,
    db: Session,
) -> Response:

    body = await request.body()

    content_encoding = request.headers.get("content-encoding", "")
    if "gzip" in content_encoding:
        import gzip
        body = gzip.decompress(body)

    storage_root = Path(settings.repository_storage_path).resolve()
    repository_path = (storage_root / repository.storage_key).resolve()

    if not repository_path.is_relative_to(storage_root):
        raise HTTPException(
            status_code=403,
            detail="Repository path traversal denied",
        )

    if not repository_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Git repository storage not found",
        )

    method = request.method.upper()

    query_string = request.url.query

    content_type = request.headers.get(
        "content-type",
        "",
    )

    content_length = str(len(body))

    # ---------------------------------------------------------
    # SUTRA authentication boundary
    #
    # IMPORTANT:
    # Authentication happens for BOTH GET and POST.
    #
    # Git clone/fetch begins with:
    #
    #   GET /info/refs?service=git-upload-pack
    #
    # Therefore authenticating only POST is insufficient.
    # ---------------------------------------------------------

    principal = authenticate_git_request(
        request,
        db,
    )

    if git_path == "git-receive-pack":
        required_capability = AuthorizationService.WRITE
    else:
        required_capability = AuthorizationService.READ

    authorize_repository_access(
        principal=principal,
        repository=repository,
        repository_owner=owner,
        db=db,
        capability=required_capability,
    )

    remote_user = principal.username

    before_refs: dict[str, str] = {}

    is_receive_pack = (
        git_path == "git-receive-pack"
    )

    # ---------------------------------------------------------
    # Ensure the server-side pre-receive gate exists before Git
    # accepts any agent receive-pack operation. Git invokes this
    # hook after unpacking the incoming objects but before updating
    # refs, which is the authoritative synchronous policy boundary.
    # ---------------------------------------------------------

    if is_receive_pack:
        RepositoryService.ensure_receive_hook(repository_path)

    if (
        principal.kind == "agent"
        and is_receive_pack
        and method == "POST"
    ):
        before_refs = get_branch_refs(
            repository_path
        )

    repository_storage_root = storage_root
    env = os.environ.copy()

    database_url = settings.database_url

    # SQLite URLs using a relative path are resolved relative to the
    # subprocess working directory. Git invokes receive hooks from inside
    # the bare repository, so a URL such as:
    #
    #   sqlite:///./sutra_test.db
    #
    # would otherwise point at a different database.
    #
    # Resolve SQLite file URLs against the SUTRA backend project root before
    # passing them to git/http-backend and its receive hooks.
    if database_url.startswith("sqlite:///"):
        sqlite_path = database_url[len("sqlite:///"):]

        if sqlite_path.startswith("./"):
            sqlite_path = sqlite_path[2:]

        sqlite_file = Path(sqlite_path).resolve()
        if not sqlite_file.exists():
            backend_file = (Path(__file__).resolve().parents[2] / sqlite_path).resolve()
            if backend_file.exists():
                sqlite_file = backend_file

        database_url = (
            "sqlite:///"
            + sqlite_file.as_posix()
        )

    env.update(
        {
            "DATABASE_URL": database_url,
            "GIT_PROJECT_ROOT": str(repository_storage_root),
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": (
                f"/{repository.storage_key}/{git_path}"
            ),
            "REQUEST_METHOD": method,
            "QUERY_STRING": query_string,
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": content_length,
            "REMOTE_USER": remote_user,
            "SUTRA_REPOSITORY_ID": repository.id,
            "SUTRA_PRINCIPAL_KIND": principal.kind,
            "SUTRA_ACTOR_ID": principal.actor_id or "",
            "GIT_DIR": str(repository_path),
            "SUTRA_REPOSITORY_PATH": str(repository_path),
            "REMOTE_ADDR": (
                request.client.host
                if request.client
                else "127.0.0.1"
            ),
        }
    )

    git_protocol = request.headers.get("git-protocol")

    if git_protocol:
        env["GIT_PROTOCOL"] = git_protocol
    else:
        env.pop("GIT_PROTOCOL", None)

    process = subprocess.run(
        ["git", "http-backend"],
        input=body,
        capture_output=True,
        env=env,
    )

    if process.returncode != 0:
        msg = (
            "[SUTRA] git http-backend failed\n"
            f"returncode={process.returncode}\n"
            f"stderr={process.stderr.decode('utf-8', errors='replace')}"
        )
        print(
            msg.encode("ascii", errors="replace").decode("ascii"),
            flush=True,
        )

    raw_output = process.stdout

    header_end = raw_output.find(
        b"\r\n\r\n"
    )

    separator_length = 4

    if header_end == -1:

        header_end = raw_output.find(
            b"\n\n"
        )

        separator_length = 2

    if header_end == -1:
        raise HTTPException(
            status_code=502,
            detail="Invalid response from Git backend",
        )

    raw_headers = raw_output[
        :header_end
    ]

    response_body = raw_output[
        header_end + separator_length:
    ]

    headers: dict[str, str] = {}

    status_code = 200

    for line in raw_headers.splitlines():

        if b":" not in line:
            continue

        key, value = line.split(
            b":",
            1,
        )

        key_text = key.decode(
            "latin-1"
        ).strip()

        value_text = value.decode(
            "latin-1"
        ).strip()

        if key_text.lower() == "status":

            try:
                status_code = int(
                    value_text.split(
                        " ",
                        1,
                    )[0]
                )

            except (
                ValueError,
                IndexError,
            ):
                status_code = 200

        else:
            headers[key_text] = value_text

    # ---------------------------------------------------------
    # Never create a Change when Git itself failed.
    # ---------------------------------------------------------

    if process.returncode != 0:

        if not response_body:

            raise HTTPException(
                status_code=500,
                detail="Internal Server Error during Git operation",
            )

        return Response(
            content=response_body,
            status_code=status_code,
            headers=headers,
        )

    # ---------------------------------------------------------
    # Persist the successful transport fact. Semantic Change
    # derivation is performed asynchronously by GitPushEventProcessor.
    # ---------------------------------------------------------

    if (
        principal.kind == "agent"
        and is_receive_pack
        and method == "POST"
    ):

        try:

            after_refs = get_branch_refs(
                repository_path
            )

            if before_refs != after_refs:
                record_agent_push_event(
                    db=db,
                    repository=repository,
                    principal=principal,
                    before_refs=before_refs,
                    after_refs=after_refs,
                )

        except Exception as exc:

            # Git already succeeded.
            #
            # Never turn a successful Git push into
            # a failed Git operation because metadata
            # recording failed.
            db.rollback()

            print(
                "[SUTRA] GitPushEvent persistence failed after a successful push: "
                f"{exc}"
            )

    if (
        principal.kind == "temp_agent"
        and is_receive_pack
        and method == "POST"
    ):
        try:
            principal.registration_request.is_temporary_token_used = True
            db.commit()
            print(f"[SUTRA] Temporary push token consumed successfully for request {principal.registration_request.id}")
        except Exception as exc:
            db.rollback()
            print(f"[SUTRA] Failed to mark temporary push token as used: {exc}")

    return Response(
        content=response_body,
        status_code=status_code,
        headers=headers,
    )


@router.api_route(
    "/{owner}/{repo}.git/{git_path:path}",
    methods=["GET", "POST"],
    summary="Git Smart HTTP Transport",
    description="Git transport endpoint. Authenticates via HTTP Basic Auth. For agents, username is the permanent token prefix (first 16 chars) and password is the active AgentSession token.",
)
async def git_smart_http(
    owner: str,
    repo: str,
    git_path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if git_path not in {"info/refs", "git-receive-pack", "git-upload-pack"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid Git endpoint",
        )

    repository, repository_owner = find_repository(
        owner,
        repo,
        db,
    )

    return await run_git_http_backend(
        request,
        repository,
        repository_owner,
        git_path,
        db,
    )