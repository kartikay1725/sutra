from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        user_id, session_id = decode_access_token(
            credentials.credentials
        )
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
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        user_id, session_id = decode_access_token(credentials.credentials)
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

