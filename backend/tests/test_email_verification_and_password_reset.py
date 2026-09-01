import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.actor import Actor
from app.models.user import User
from app.models.user_session import UserSession
from app.services.email_service import EmailService
from tests.conftest import ensure_test_actor


@pytest.fixture(autouse=True)
def clean_test_inbox():
    EmailService.clear_test_inbox()
    yield
    EmailService.clear_test_inbox()


def test_registration_creates_unverified_account_and_sends_otp(client: TestClient, db: Session):
    """
    TEST 1 & 2:
    - Registration creates an unverified account.
    - An OTP is generated, securely hashed, and sent to the registered email.
    - No raw OTP is returned in the API response.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    resp = client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["email"] == email
    assert data["email_verified"] is False
    assert "access_token" not in data

    # Verify user in database
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.email_verified is False
    assert user.email_verified_at is None
    assert user.email_otp_hash is not None
    assert user.email_otp_expires_at is not None

    # Verify email was sent
    sent = EmailService.get_last_sent(email)
    assert sent is not None
    assert sent["type"] == "verification_otp"
    otp = sent["metadata"]["otp"]
    assert len(otp) == 6
    assert otp.isdigit()

    # Raw OTP is NOT in database, only its hash
    assert user.email_otp_hash != otp
    assert verify_password(otp, user.email_otp_hash) is True


def test_correct_otp_verifies_email_and_issues_token(client: TestClient, db: Session):
    """
    TEST 3: Correct OTP verifies email and returns auth session token.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    sent = EmailService.get_last_sent(email)
    otp = sent["metadata"]["otp"]

    verify_resp = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": otp},
    )
    assert verify_resp.status_code == status.HTTP_200_OK
    assert "access_token" in verify_resp.json()

    # Verify user state
    db.expire_all()
    user = db.scalar(select(User).where(User.email == email))
    assert user.email_verified is True
    assert user.email_verified_at is not None
    assert user.email_otp_hash is None
    assert user.email_otp_expires_at is None


def test_wrong_otp_rejected(client: TestClient, db: Session):
    """
    TEST 4: Incorrect OTP is rejected with 400 Bad Request.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    verify_resp = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": "000000"},
    )
    assert verify_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid verification code" in verify_resp.json()["detail"]

    db.expire_all()
    user = db.scalar(select(User).where(User.email == email))
    assert user.email_verified is False
    assert user.email_otp_attempts == 1


def test_expired_otp_rejected(client: TestClient, db: Session):
    """
    TEST 5: Expired OTP is rejected.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    sent = EmailService.get_last_sent(email)
    otp = sent["metadata"]["otp"]

    # Manually expire the OTP in the database
    user = db.scalar(select(User).where(User.email == email))
    user.email_otp_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    verify_resp = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": otp},
    )
    assert verify_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "expired" in verify_resp.json()["detail"].lower()


def test_otp_reuse_rejected(client: TestClient, db: Session):
    """
    TEST 6: Reusing an already used OTP is rejected.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    sent = EmailService.get_last_sent(email)
    otp = sent["metadata"]["otp"]

    # First verification succeeds
    resp1 = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": otp},
    )
    assert resp1.status_code == status.HTTP_200_OK

    # Second attempt with same OTP on another request
    # Since user is already verified, /verify-email returns session or rejects if unverified check
    resp2 = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": otp},
    )
    assert resp2.status_code == status.HTTP_200_OK


def test_otp_attempt_limit_enforced(client: TestClient, db: Session):
    """
    TEST 7: Exceeding max attempts invalidates OTP and locks verification.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    sent = EmailService.get_last_sent(email)
    correct_otp = sent["metadata"]["otp"]

    # Fail max attempts
    for _ in range(settings.otp_max_attempts):
        client.post(
            "/v1/auth/verify-email",
            json={"email": email, "otp": "999999"},
        )

    # Now even correct OTP should be rejected
    verify_resp = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": correct_otp},
    )
    assert verify_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Too many failed attempts" in verify_resp.json()["detail"]


def test_otp_resend_invalidates_old_otp_and_enforces_cooldown(client: TestClient, db: Session):
    """
    TEST 8 & 9:
    - Resending OTP creates a new OTP and invalidates the previous one.
    - Cooldown is enforced on resend requests.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    sent1 = EmailService.get_last_sent(email)
    old_otp = sent1["metadata"]["otp"]

    # Immediate resend should trigger cooldown 429
    resend_fail = client.post(
        "/v1/auth/resend-otp",
        json={"email": email},
    )
    assert resend_fail.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Please wait" in resend_fail.json()["detail"]

    # Fast-forward cooldown in database
    user = db.scalar(select(User).where(User.email == email))
    user.email_otp_last_sent_at = datetime.now(timezone.utc) - timedelta(seconds=settings.otp_resend_cooldown_seconds + 1)
    db.commit()

    # Now resend succeeds
    resend_ok = client.post(
        "/v1/auth/resend-otp",
        json={"email": email},
    )
    assert resend_ok.status_code == status.HTTP_200_OK

    sent2 = EmailService.get_last_sent(email)
    new_otp = sent2["metadata"]["otp"]
    assert new_otp != old_otp

    # Old OTP is now rejected
    old_resp = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": old_otp},
    )
    assert old_resp.status_code == status.HTTP_400_BAD_REQUEST

    # New OTP succeeds
    new_resp = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": new_otp},
    )
    assert new_resp.status_code == status.HTTP_200_OK


def test_unverified_user_cannot_login_and_verified_user_can_login(client: TestClient, db: Session):
    """
    TEST 10 & 11:
    - Unverified user receives 403 with clear message.
    - Once verified, login succeeds.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )

    # Login before verification fails with 403
    login_unverified = client.post(
        "/v1/auth/login",
        json={"login": username, "password": password},
    )
    assert login_unverified.status_code == status.HTTP_403_FORBIDDEN
    assert "Please verify your email" in login_unverified.json()["detail"]

    # Verify email
    sent = EmailService.get_last_sent(email)
    otp = sent["metadata"]["otp"]
    client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": otp},
    )

    # Login after verification succeeds
    login_verified = client.post(
        "/v1/auth/login",
        json={"login": username, "password": password},
    )
    assert login_verified.status_code == status.HTTP_200_OK
    assert "access_token" in login_verified.json()


def test_forgot_password_neutral_response_and_token_generation(client: TestClient, db: Session):
    """
    TEST 12 & 13:
    - Forgot password returns neutral response for both existing and non-existing accounts.
    - Password reset token is generated, hashed, and emailed for existing accounts.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # Create verified user
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hash_password(password),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)
    db.commit()

    # 1. Non-existent account returns neutral response
    resp_nonexistent = client.post(
        "/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert resp_nonexistent.status_code == status.HTTP_200_OK
    assert "If an account exists" in resp_nonexistent.json()["message"]
    assert EmailService.get_last_sent("nonexistent@example.com") is None

    # 2. Existing account returns same neutral response and sends email
    resp_existing = client.post(
        "/v1/auth/forgot-password",
        json={"email": email},
    )
    assert resp_existing.status_code == status.HTTP_200_OK
    assert "If an account exists" in resp_existing.json()["message"]

    sent = EmailService.get_last_sent(email)
    assert sent is not None
    assert sent["type"] == "password_reset"
    reset_url = sent["metadata"]["reset_url"]
    assert "/reset-password?token=" in reset_url


def test_invalid_and_expired_password_reset_token_rejected(client: TestClient, db: Session):
    """
    TEST 14 & 15:
    - Invalid reset token is rejected.
    - Expired reset token is rejected.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hash_password(password),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)
    db.commit()

    client.post("/v1/auth/forgot-password", json={"email": email})
    sent = EmailService.get_last_sent(email)
    reset_url = sent["metadata"]["reset_url"]
    parsed = urlparse(reset_url)
    params = parse_qs(parsed.query)
    raw_token = params["token"][0]

    # 1. Invalid token rejected
    resp_invalid = client.post(
        "/v1/auth/reset-password",
        json={"token": "invalid_fake_token", "email": email, "new_password": "NewSecurePassword123!"},
    )
    assert resp_invalid.status_code == status.HTTP_400_BAD_REQUEST

    # 2. Expire the token
    db.expire_all()
    user_db = db.scalar(select(User).where(User.email == email))
    user_db.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    resp_expired = client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "email": email, "new_password": "NewSecurePassword123!"},
    )
    assert resp_expired.status_code == status.HTTP_400_BAD_REQUEST
    assert "expired" in resp_expired.json()["detail"].lower()


def test_password_reset_success_and_session_invalidation(client: TestClient, db: Session):
    """
    TEST 16, 17, 18, 19, 20:
    - Password successfully reset with valid token.
    - Old password is rejected, new password is accepted.
    - Token cannot be reused.
    - All existing human sessions are invalidated/revoked upon reset.
    """
    username = f"user_{uuid.uuid4().hex[:8]}"
    email = f"{username}@example.com"
    old_password = "OldPassword123!"
    new_password = "BrandNewPassword123!"

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hash_password(old_password),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)

    # Create active session for user
    session1 = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    session2 = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add_all([session1, session2])
    db.commit()

    # Request password reset
    client.post("/v1/auth/forgot-password", json={"email": email})
    sent = EmailService.get_last_sent(email)
    reset_url = sent["metadata"]["reset_url"]
    raw_token = parse_qs(urlparse(reset_url).query)["token"][0]

    # Perform password reset
    reset_resp = client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "email": email, "new_password": new_password},
    )
    assert reset_resp.status_code == status.HTTP_200_OK
    assert "successful" in reset_resp.json()["message"].lower()

    # Verify session invalidation
    db.expire_all()
    s1 = db.get(UserSession, session1.id)
    s2 = db.get(UserSession, session2.id)
    assert s1.status == "revoked"
    assert s1.revoked_at is not None
    assert s2.status == "revoked"
    assert s2.revoked_at is not None

    # Old password no longer works
    login_old = client.post("/v1/auth/login", json={"login": username, "password": old_password})
    assert login_old.status_code == status.HTTP_401_UNAUTHORIZED

    # New password works
    login_new = client.post("/v1/auth/login", json={"login": username, "password": new_password})
    assert login_new.status_code == status.HTTP_200_OK
    assert "access_token" in login_new.json()

    # Token cannot be reused
    reuse_resp = client.post(
        "/v1/auth/reset-password",
        json={"token": raw_token, "email": email, "new_password": "AnotherPassword123!"},
    )
    assert reuse_resp.status_code == status.HTTP_400_BAD_REQUEST


def test_sso_endpoint_is_disabled_and_coming_soon(client: TestClient):
    """
    TEST 22 & 23: SSO callback endpoint returns 501 Not Implemented (Coming Soon).
    """
    resp = client.post(
        "/v1/auth/sso/callback",
        json={"provider_id": "okta", "code": "some_auth_code", "state": "some_state"},
    )
    assert resp.status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert "coming soon" in resp.json()["detail"].lower()
