from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    password_hash_value: str,
) -> bool:
    return password_hash.verify(
        password,
        password_hash_value,
    )


def create_access_token(subject: str, session_id: str | None = None) -> str:
    if session_id is None:
        from uuid import uuid4
        session_id = str(uuid4())
        
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": subject,
        "jti": session_id,
        "exp": expires,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> tuple[str, str]:
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )

    subject = payload.get("sub")
    session_id = payload.get("jti")

    if not subject:
        raise ValueError("Invalid token subject")
    if not session_id:
        raise ValueError("Invalid token session ID")

    return subject, session_id
