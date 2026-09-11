from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def _resolve_raw_token(
    credentials: HTTPAuthorizationCredentials | None,
    request: Request | None = None,
) -> str | None:
    """Extract raw user token from Authorization header or secure browser cookie."""
    if credentials and credentials.credentials:
        return credentials.credentials.strip()
    if request:
        cookie_token = request.cookies.get("sutra_session") or request.cookies.get("sutra_token")
        if cookie_token and cookie_token.strip():
            return cookie_token.strip()
    return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    raw_token = _resolve_raw_token(credentials, request)

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        user_id, session_id = decode_access_token(raw_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    from app.models.user_session import UserSession
    from datetime import datetime, timezone

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user_session = db.get(UserSession, session_id)
    if user_session is not None:
        if user_session.status != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is revoked")
            
        expires_at = user_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        user_session.last_seen_at = datetime.now(timezone.utc)
        db.flush()

    return user


def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User | None:
    raw_token = _resolve_raw_token(credentials, request)
    if not raw_token:
        return None
    try:
        user_id, session_id = decode_access_token(raw_token)
        user = db.get(User, user_id)
        if user is None:
            return None
        from app.models.user_session import UserSession
        from datetime import datetime, timezone
        user_session = db.get(UserSession, session_id)
        if user_session is not None:
            expires_at = user_session.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if user_session.status != "active" or expires_at < datetime.now(timezone.utc):
                return None
            user_session.last_seen_at = datetime.now(timezone.utc)
            db.flush()
        return user
    except Exception:
        return None


