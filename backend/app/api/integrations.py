"""
Integrations API — GitHub App Connection Flow
==============================================
Provides endpoints for users to connect/disconnect their GitHub account
and sync repositories through the GitHub App installation mechanism.

Security design:
- All endpoints except /callback require a valid SUTRA JWT (human auth).
- /callback uses a signed, one-time state token to re-derive the user context.
- State tokens are HMAC-SHA256 signed using JWT_SECRET and stored in Redis
  with 10-minute TTL. They are consumed once (deleted on use) to prevent replay.
- installation_id from GitHub is VERIFIED against the GitHub API before storage.
- No GitHub installation access tokens are ever persisted.
- No private key material is ever exposed to the frontend.
"""
import hashlib
import hmac
import json
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.redis_service import redis_service
from app.db.session import get_db
from app.models.user import User
from app.providers.github.auth import GitHubAppAuthService
from app.services.github_installation_service import GitHubInstallationService

logger = logging.getLogger("sutra.api.integrations")

router = APIRouter(
    prefix="/v1/integrations",
    tags=["integrations"],
)

# Redis key prefix for state tokens
_STATE_PREFIX = "github_connect_state:"
_STATE_TTL_SECONDS = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_auth_service() -> GitHubAppAuthService:
    app_id = getattr(settings, "github_app_id", None) or "0"
    pem = getattr(settings, "github_private_key_pem", None) or ""
    return GitHubAppAuthService(app_id=app_id, private_key_pem=pem)


def _sign_state(raw: str) -> str:
    """HMAC-SHA256 sign a state nonce using the JWT_SECRET."""
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _generate_state_token(user_id: str) -> str:
    """
    Generate a signed, one-time state token for CSRF protection.
    Format: {nonce}.{user_id}.{signature}
    Stored in Redis with TTL so it can be consumed exactly once.
    """
    nonce = secrets.token_hex(24)
    raw = f"{nonce}.{user_id}"
    sig = _sign_state(raw)
    token = f"{raw}.{sig}"

    r = redis_service.get_client()
    r.setex(f"{_STATE_PREFIX}{token}", _STATE_TTL_SECONDS, user_id)
    return token


def _consume_state_token(state: str) -> str:
    """
    Validate and consume a state token. Returns the user_id encoded in it.
    Raises HTTPException 400 if invalid, expired, or already used.
    """
    r = redis_service.get_client()
    stored_user_id = r.get(f"{_STATE_PREFIX}{state}")

    if stored_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state token. Please initiate the connection again.",
        )

    # Verify HMAC signature on state token
    parts = state.rsplit(".", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Malformed state token.")

    raw, provided_sig = parts
    expected_sig = _sign_state(raw)
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(status_code=400, detail="State token signature invalid.")

    # Extract user_id from raw
    raw_parts = raw.split(".")
    if len(raw_parts) != 2:
        raise HTTPException(status_code=400, detail="Malformed state token content.")
    user_id = raw_parts[1]

    # Cross-check with Redis value
    if isinstance(stored_user_id, bytes):
        stored_user_id = stored_user_id.decode("utf-8")
    if stored_user_id != user_id:
        raise HTTPException(status_code=400, detail="State token user mismatch.")

    # Consume the token (delete from Redis — prevents replay)
    r.delete(f"{_STATE_PREFIX}{state}")
    return user_id


# ---------------------------------------------------------------------------
# GET /v1/integrations/github  — connection status
# ---------------------------------------------------------------------------


@router.get("/github", summary="GitHub connection status")
def get_github_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the current user's GitHub connection status.
    Does not expose any tokens or sensitive credentials.
    """
    auth_service = _build_auth_service()
    service = GitHubInstallationService(auth_service)
    installation = service.get_installation_for_user(db, current_user.id)

    if installation is None:
        return {
            "connected": False,
            "account": None,
            "target_type": None,
            "installation_id": None,
            "repo_count": 0,
        }

    from sqlalchemy import select as sql_select, func
    from app.models.repository import Repository
    from app.services.github_sync_worker import get_installation_sync_status

    repo_count = db.scalar(
        sql_select(func.count(Repository.id)).where(
            Repository.github_installation_id == installation.github_installation_id,
            Repository.deleted_at.is_(None),
        )
    ) or 0

    sync_meta = get_installation_sync_status(installation.github_installation_id)
    last_synced = sync_meta.get("last_synced_at")
    if not last_synced:
        max_synced_at = db.scalar(
            sql_select(func.max(Repository.github_objects_synced_at)).where(
                Repository.github_installation_id == installation.github_installation_id,
                Repository.deleted_at.is_(None),
            )
        )
        if max_synced_at:
            last_synced = max_synced_at.isoformat()

    return {
        "connected": True,
        "account": installation.github_account_login,
        "target_type": installation.target_type,
        "installation_id": installation.github_installation_id,
        "repo_count": repo_count,
        "last_synced_at": last_synced,
        "sync_status": sync_meta.get("status", "idle"),
    }


# ---------------------------------------------------------------------------
# GET /v1/integrations/github/connect  — initiate installation flow
# ---------------------------------------------------------------------------


@router.get("/github/connect", summary="Initiate GitHub App installation")
def github_connect(
    current_user: User = Depends(get_current_user),
):
    """
    Returns a redirect URL to the GitHub App installation page.
    Embeds a signed CSRF state token that GitHub echoes back to /callback.

    The private key and App JWT are never sent to the frontend.
    """
    app_slug = getattr(settings, "github_app_slug", None)
    if not app_slug:
        raise HTTPException(
            status_code=503,
            detail=(
                "GitHub App is not configured on this server. "
                "Set GITHUB_APP_SLUG in the server environment."
            ),
        )

    if not getattr(settings, "github_app_id", None):
        raise HTTPException(
            status_code=503,
            detail="GitHub App credentials are not configured on this server.",
        )

    state_token = _generate_state_token(current_user.id)
    install_url = (
        f"https://github.com/apps/{app_slug}/installations/new"
        f"?state={state_token}"
    )

    return {"redirect_url": install_url}


# ---------------------------------------------------------------------------
# GET /v1/integrations/github/callback  — GitHub redirects here after install
# ---------------------------------------------------------------------------


@router.get("/github/callback", summary="GitHub App installation callback")
def github_callback(
    installation_id: int = Query(..., description="GitHub installation ID"),
    setup_action: str = Query("install"),
    state: str = Query(..., description="CSRF state token"),
    db: Session = Depends(get_db),
):
    """
    GitHub redirects to this endpoint after the user installs (or updates) the App.

    Security:
    1. State token is validated and consumed (one-time use, HMAC-signed).
    2. The installation_id is verified against the GitHub API — we don't trust
       the query parameter blindly.
    3. The verified account info is stored in github_installations.
    4. Repos are synced immediately (idempotent).
    5. Redirects to the frontend settings page.

    This endpoint does NOT require a Bearer token — the state token carries
    user identity so the browser redirect flow works correctly.
    """
    # 1. Validate and consume state token → get user_id
    user_id = _consume_state_token(state)

    # 2. Load the user
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User not found.")

    # 3. If GitHub said this was an "uninstall", just return
    if setup_action == "delete":
        auth_service = _build_auth_service()
        service = GitHubInstallationService(auth_service)
        service.delete_installation(db, user_id)
        frontend_url = getattr(settings, "frontend_base_url", "http://localhost:3000")
        return RedirectResponse(
            url=f"{frontend_url}/settings?github=disconnected",
            status_code=302,
        )

    # 4. Verify installation via GitHub API (do NOT trust query params alone)
    auth_service = _build_auth_service()
    service = GitHubInstallationService(auth_service)

    try:
        gh_install = service.verify_installation_from_github(installation_id)
    except Exception as e:
        logger.error(f"Failed to verify GitHub installation {installation_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail="Could not verify GitHub installation. Please try again.",
        )

    account = gh_install.get("account", {})
    github_account_id = account.get("id")
    github_account_login = account.get("login", "unknown")
    target_type = gh_install.get("target_type", "User")

    if not github_account_id:
        raise HTTPException(
            status_code=400,
            detail="GitHub API returned unexpected installation data.",
        )

    # 5. Upsert installation record
    try:
        installation = service.upsert_installation(
            db=db,
            user_id=user_id,
            github_installation_id=installation_id,
            github_account_id=github_account_id,
            github_account_login=github_account_login,
            target_type=target_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 6. Sync repositories (idempotent — safe to run on every install)
    try:
        service.sync_repos_for_user(db=db, user=user, installation=installation)
    except Exception as e:
        # Repo sync failure should not block the connection — log and continue
        logger.error(f"Repo sync failed after install for user {user_id}: {e}")

    # 7. Redirect to frontend
    frontend_url = getattr(settings, "frontend_base_url", "http://localhost:3000")
    return RedirectResponse(
        url=f"{frontend_url}/settings?github=connected",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# DELETE /v1/integrations/github  — disconnect
# ---------------------------------------------------------------------------


@router.delete("/github", summary="Disconnect GitHub integration")
def github_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Removes the user's GitHub installation record.
    Synced GitHub repositories remain in SUTRA's database but become
    inaccessible via the GitHub provider (no valid installation token).
    """
    auth_service = _build_auth_service()
    service = GitHubInstallationService(auth_service)
    removed = service.delete_installation(db, current_user.id)

    if not removed:
        raise HTTPException(
            status_code=404,
            detail="No GitHub connection found for this account.",
        )

    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# POST /v1/integrations/github/sync  — manually trigger repo sync
# ---------------------------------------------------------------------------


@router.post("/github/sync", summary="Sync GitHub repositories")
def github_sync(
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers repository metadata and engineering object synchronization.
    Returns immediately with queued or debounced status.
    Respects 5-minute debounce unless force=True.
    Uses short-lived installation tokens and bounded background concurrency.
    """
    auth_service = _build_auth_service()
    service = GitHubInstallationService(auth_service)
    installation = service.get_installation_for_user(db, current_user.id)

    if installation is None:
        raise HTTPException(
            status_code=404,
            detail="No GitHub connection found. Connect GitHub first.",
        )

    from app.services.github_sync_worker import (
        check_sync_debounce,
        set_sync_debounce,
        GitHubSyncWorker,
    )

    inst_id = installation.github_installation_id

    # Check 5-minute debounce cooldown unless force=True (Q2)
    if not force:
        is_debounced, cooldown = check_sync_debounce(inst_id)
        if is_debounced:
            return {
                "status": "debounced",
                "cooldown_remaining_seconds": cooldown,
                "account": installation.github_account_login,
                "message": f"Sync was recently requested. Cooldown active for {cooldown}s.",
            }

    # Set 5-minute cooldown (300 seconds)
    set_sync_debounce(inst_id, ttl=300)

    # Queue background sync via durable worker / worker queue (Q1)
    GitHubSyncWorker.enqueue_job(
        installation_id=inst_id,
        user_id=current_user.id,
        force=force,
    )

    return {
        "status": "queued",
        "account": installation.github_account_login,
        "message": "Repository sync has been queued.",
    }
