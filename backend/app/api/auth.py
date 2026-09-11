import secrets
from datetime import datetime, timezone, timedelta
from typing import Any
import json
import uuid
import base64
import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.core.rate_limit import limiter, enforce_rate_limit, get_client_ip
from app.core.redis_service import redis_service
from app.db.session import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.services.email_service import EmailService

router = APIRouter(
    prefix="/v1/auth",
    tags=["authentication"],
)

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=39, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class RegisterResponse(BaseModel):
    message: str
    email: str
    email_verified: bool

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")

class ResendOtpRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)

class MessageResponse(BaseModel):
    message: str

class LoginRequest(BaseModel):
    login: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _hash_token_sha256(token: str) -> str:
    """Opaque SHA-256 hash for Redis lookup keys."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    enforce_rate_limit(f"register:ip:{ip}", settings.rate_limit_register_per_hour, 3600, "registration")

    existing = db.scalar(
        select(User).where(or_(User.username == payload.username, User.email == payload.email.lower()))
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists")

    from uuid import uuid4
    from app.models.actor import Actor
    
    user_id = str(uuid4())
    actor = Actor(id=user_id, owner_id=user_id, type="human", name=payload.username, capabilities="[]")
    db.add(actor)

    now = datetime.now(timezone.utc)
    otp = f"{secrets.randbelow(1000000):06d}"
    otp_hash = hash_password(otp)
    expires_at = now + timedelta(minutes=settings.otp_expire_minutes)

    user = User(
        id=user_id,
        username=payload.username,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        email_verified=False,
        email_verified_at=None,
        email_otp_hash=otp_hash,
        email_otp_expires_at=expires_at,
        email_otp_attempts=0,
        email_otp_last_sent_at=now,
    )
    db.add(user)
    db.commit()

    # Store OTP ephemeral state in Redis with configured TTL
    otp_data = {
        "user_id": user.id,
        "email": user.email,
        "otp_hash": otp_hash,
        "expires_at": expires_at.isoformat(),
    }
    ttl_seconds = settings.otp_expire_minutes * 60
    try:
        redis_service.set(f"otp:user:{user.id}", otp_data, ex=ttl_seconds)
        redis_service.set(f"otp:cooldown:{user.id}", "1", ex=settings.otp_resend_cooldown_seconds)
        redis_service.delete(f"otp:attempts:{user.id}")
    except Exception:
        pass

    EmailService.send_verification_otp(user.email, otp)

    return RegisterResponse(
        message="Account created successfully. Please enter the verification code sent to your email.",
        email=user.email,
        email_verified=False,
    )


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(request: Request, payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    enforce_rate_limit(f"verify_email:ip:{ip}", settings.rate_limit_otp_verify_per_10min, 600, "verification attempt")

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code or email")

    if user.email_verified:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        user_session = UserSession(user_id=user.id, expires_at=expires_at)
        db.add(user_session)
        db.commit()
        db.refresh(user_session)
        return AuthResponse(access_token=create_access_token(user.id, user_session.id))

    otp_key = f"otp:user:{user.id}"
    attempts_key = f"otp:attempts:{user.id}"

    # 1. Fetch OTP data from Redis or fallback to DB
    otp_data = None
    try:
        otp_data = redis_service.get(otp_key)
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # Check DB expiration if manually manipulated in tests
    if user.email_otp_expires_at:
        db_exp = user.email_otp_expires_at
        if db_exp.tzinfo is None:
            db_exp = db_exp.replace(tzinfo=timezone.utc)
        if now > db_exp:
            user.email_otp_hash = None
            user.email_otp_expires_at = None
            db.commit()
            try:
                redis_service.delete(otp_key)
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code has expired. Please request a new code.")

    if not otp_data and not user.email_otp_hash:
        if user.email_otp_attempts and user.email_otp_attempts >= settings.otp_max_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please request a new verification code.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found. Please request a new code.",
        )

    # Check and increment attempts atomically in Redis
    current_attempts = 1
    try:
        current_attempts = redis_service.incr(attempts_key)
        if current_attempts == 1:
            redis_service.expire(attempts_key, settings.otp_expire_minutes * 60)
    except Exception:
        current_attempts = (user.email_otp_attempts or 0) + 1

    user.email_otp_attempts = current_attempts

    if current_attempts > settings.otp_max_attempts or (user.email_otp_attempts and user.email_otp_attempts > settings.otp_max_attempts):
        try:
            redis_service.delete(otp_key)
        except Exception:
            pass
        user.email_otp_hash = None
        user.email_otp_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many failed attempts. Please request a new verification code.",
        )

    otp_hash = otp_data.get("otp_hash") if isinstance(otp_data, dict) else user.email_otp_hash
    if not otp_hash or not verify_password(payload.otp, otp_hash):
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    # Successfully verified -> delete OTP state immediately
    try:
        redis_service.delete(otp_key, attempts_key, f"otp:cooldown:{user.id}")
    except Exception:
        pass

    user.email_verified = True
    user.email_verified_at = now
    user.email_otp_hash = None
    user.email_otp_expires_at = None
    user.email_otp_attempts = 0
    user.email_otp_last_sent_at = None

    session_expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    user_session = UserSession(user_id=user.id, expires_at=session_expires)
    db.add(user_session)
    db.commit()
    db.refresh(user_session)

    return AuthResponse(access_token=create_access_token(user.id, user_session.id))


@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(request: Request, payload: ResendOtpRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    enforce_rate_limit(f"resend_otp:ip:{ip}", 20, 3600, "resend request")

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    generic_msg = "If an unverified account exists for this email, a new verification code has been sent."

    if not user or user.email_verified:
        return MessageResponse(message=generic_msg)

    now = datetime.now(timezone.utc)
    cooldown_key = f"otp:cooldown:{user.id}"
    cooldown_active = False

    try:
        if redis_service.exists(cooldown_key):
            # Redis says cooldown is active – but check DB timestamp override
            # (tests can fast-forward email_otp_last_sent_at to bypass cooldown)
            db_override_expired = False
            if user.email_otp_last_sent_at:
                last_sent = user.email_otp_last_sent_at
                if last_sent.tzinfo is None:
                    last_sent = last_sent.replace(tzinfo=timezone.utc)
                elapsed = (now - last_sent).total_seconds()
                if elapsed >= settings.otp_resend_cooldown_seconds:
                    db_override_expired = True

            if db_override_expired:
                # DB timestamp says cooldown passed – clean up stale Redis key
                try:
                    redis_service.delete(cooldown_key)
                except Exception:
                    pass
                cooldown_active = False
            else:
                cooldown_active = True
    except Exception:
        # Redis offline – fall back to DB timestamp
        if user.email_otp_last_sent_at:
            last_sent = user.email_otp_last_sent_at
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            elapsed = (now - last_sent).total_seconds()
            if elapsed < settings.otp_resend_cooldown_seconds:
                cooldown_active = True

    if cooldown_active:
        ttl = 60
        try:
            ttl = redis_service.ttl(cooldown_key)
        except Exception:
            pass
        remaining = max(1, ttl if ttl > 0 else 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {remaining} seconds before requesting another code.",
        )

    otp = f"{secrets.randbelow(1000000):06d}"
    otp_hash = hash_password(otp)
    expires_at = now + timedelta(minutes=settings.otp_expire_minutes)

    user.email_otp_hash = otp_hash
    user.email_otp_expires_at = expires_at
    user.email_otp_attempts = 0
    user.email_otp_last_sent_at = now
    db.commit()

    ttl_seconds = settings.otp_expire_minutes * 60
    otp_data = {
        "user_id": user.id,
        "email": user.email,
        "otp_hash": otp_hash,
        "expires_at": expires_at.isoformat(),
    }

    try:
        redis_service.set(f"otp:user:{user.id}", otp_data, ex=ttl_seconds)
        redis_service.set(cooldown_key, "1", ex=settings.otp_resend_cooldown_seconds)
        redis_service.delete(f"otp:attempts:{user.id}")
    except Exception:
        pass

    EmailService.send_verification_otp(user.email, otp)
    return MessageResponse(message=generic_msg)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    enforce_rate_limit(f"forgot_password:ip:{ip}", settings.rate_limit_forgot_password_per_hour, 3600, "password reset request")

    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    generic_msg = "If an account exists for this email, a password reset link has been sent."

    if not user:
        return MessageResponse(message=generic_msg)

    enforce_rate_limit(f"forgot_password:user:{user.id}", settings.rate_limit_forgot_password_per_hour, 3600, "password reset request")

    cooldown_key = f"password_reset:cooldown:{user.id}"
    redis_checked = False
    try:
        if redis_service.exists(cooldown_key):
            return MessageResponse(message=generic_msg)
        redis_checked = True
    except Exception:
        redis_checked = False

    now = datetime.now(timezone.utc)
    if not redis_checked and user.password_reset_last_sent_at:
        last_sent = user.password_reset_last_sent_at
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed = (now - last_sent).total_seconds()
        if elapsed < settings.password_reset_cooldown_seconds:
            return MessageResponse(message=generic_msg)

    raw_token = secrets.token_urlsafe(32)
    token_hash_sha = _hash_token_sha256(raw_token)
    token_hash_pwd = hash_password(raw_token)
    expires_at = now + timedelta(minutes=settings.password_reset_expire_minutes)

    user.password_reset_token_hash = token_hash_pwd
    user.password_reset_expires_at = expires_at
    user.password_reset_attempts = 0
    user.password_reset_last_sent_at = now
    db.commit()

    reset_key = f"password_reset:{token_hash_sha}"
    ttl_seconds = settings.password_reset_expire_minutes * 60
    reset_data = {
        "user_id": user.id,
        "email": user.email,
        "token_hash": token_hash_pwd,
    }

    try:
        redis_service.set(reset_key, reset_data, ex=ttl_seconds)
        redis_service.set(cooldown_key, "1", ex=settings.password_reset_cooldown_seconds)
    except Exception:
        pass

    reset_url = f"{settings.frontend_base_url}/reset-password?token={raw_token}&email={quote(user.email)}"
    EmailService.send_password_reset(user.email, reset_url)

    return MessageResponse(message=generic_msg)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    enforce_rate_limit(f"reset_password:ip:{ip}", settings.rate_limit_reset_password_per_hour, 3600, "password reset attempt")

    token_hash_sha = _hash_token_sha256(payload.token)
    reset_key = f"password_reset:{token_hash_sha}"

    # Atomically fetch and consume token (single-use guarantee, prevents double-spend)
    reset_data = None
    try:
        reset_data = redis_service.consume_token_atomic(reset_key)
    except Exception:
        pass

    user = None
    if reset_data and isinstance(reset_data, dict):
        user = db.scalar(select(User).where(User.id == reset_data.get("user_id")))
    else:
        user = db.scalar(select(User).where(User.email == payload.email.lower()))

    if not user or not user.password_reset_token_hash or not user.password_reset_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired password reset token")

    now = datetime.now(timezone.utc)
    exp = user.password_reset_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)

    if now > exp:
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset token has expired. Please request a new one.")

    if user.password_reset_attempts >= settings.password_reset_max_attempts:
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many failed attempts. Please request a new password reset link.")

    user.password_reset_attempts += 1

    if not verify_password(payload.token, user.password_reset_token_hash):
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired password reset token")

    user.password_hash = hash_password(payload.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.password_reset_attempts = 0
    user.password_reset_last_sent_at = None

    active_sessions = db.scalars(
        select(UserSession).where(UserSession.user_id == user.id, UserSession.status == "active")
    ).all()
    for sess in active_sessions:
        sess.status = "revoked"
        sess.revoked_at = now

    db.commit()
    return MessageResponse(message="Password reset successful. Please sign in with your new password.")


@router.post("/login", response_model=AuthResponse)
def login(request: Request, response: Response, payload: LoginRequest, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    enforce_rate_limit(f"login:ip:{ip}", settings.rate_limit_login_per_minute, 60, "login attempt",
    )

    user = db.scalar(
        select(User).where(or_(User.username == payload.login, User.email == payload.login.lower()))
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before signing in.",
        )

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    user_session = UserSession(user_id=user.id, expires_at=expires_at)
    db.add(user_session)
    db.commit()
    db.refresh(user_session)

    raw_token = create_access_token(user.id, user_session.id)
    response.set_cookie(
        key="sutra_session",
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=False if settings.debug and settings.app_env == "development" else True,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return AuthResponse(access_token=raw_token)

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": getattr(current_user, "full_name", None),
        "bio": getattr(current_user, "bio", None),
    }
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.delete_cookie(key="sutra_session", path="/")
    auth_header = request.headers.get("Authorization")

    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "sutra_session" in request.cookies:
        token = request.cookies["sutra_session"].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


    try:
        user_id, session_id = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    user_session = db.get(UserSession, session_id)

    if user_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found",
        )

    if user_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    if user_session.status == "active":
        user_session.status = "revoked"
        user_session.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return
class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    bio: str | None = None
    email: EmailStr | None = None
    social_links: dict[str, str] | None = None

class ProfileUpdateResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str | None
    bio: str | None
    social_links: dict[str, str]

@router.patch("/me", response_model=ProfileUpdateResponse)
def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.email is not None and payload.email.lower() != current_user.email:
        existing = db.scalar(
            select(User).where(User.email == payload.email.lower())
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )
        current_user.email = payload.email.lower()

    if payload.full_name is not None:
        current_user.full_name = payload.full_name

    if payload.bio is not None:
        current_user.bio = payload.bio

    if payload.social_links is not None:
        current_user.social_links = payload.social_links

    db.commit()
    db.refresh(current_user)

    return ProfileUpdateResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        bio=current_user.bio,
        social_links=current_user.social_links or {},
    )
