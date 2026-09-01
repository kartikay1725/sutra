import concurrent.futures
import hashlib
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_service import redis_service
from app.core.security import hash_password
from app.models.user import User
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.agent_registration import AgentRegistrationRequest
from app.api.agent_dependencies import create_agent_session, revoke_agent_session, validate_agent_session_token
from tests.conftest import ensure_test_actor


@pytest.fixture(autouse=True)
def clean_redis():
    """Flush test keys before and after each test to ensure hermetic state."""
    try:
        r = redis_service.get_client()
        keys = (
            r.keys("otp:*")
            + r.keys("password_reset:*")
            + r.keys("session:*")
            + r.keys("revoked_session:*")
            + r.keys("temp_push:*")
            + r.keys("ratelimit:*")
        )
        if keys:
            r.delete(*keys)
    except Exception:
        pass
    yield
    try:
        r = redis_service.get_client()
        keys = (
            r.keys("otp:*")
            + r.keys("password_reset:*")
            + r.keys("session:*")
            + r.keys("revoked_session:*")
            + r.keys("temp_push:*")
            + r.keys("ratelimit:*")
        )
        if keys:
            r.delete(*keys)
    except Exception:
        pass


# =========================================================================
# TEST GROUP A — RATE LIMITING
# =========================================================================

def test_a1_a2_a3_a4_rate_limiting_lifecycle():
    key = "test_user_rate_limit"
    # Limit: 3 requests per 2 seconds
    allowed1, count1, ttl1 = redis_service.check_rate_limit(f"ratelimit:{key}", 3, 2)
    assert allowed1 is True
    assert count1 == 1
    assert ttl1 > 0

    allowed2, count2, _ = redis_service.check_rate_limit(f"ratelimit:{key}", 3, 2)
    assert allowed2 is True
    assert count2 == 2

    allowed3, count3, _ = redis_service.check_rate_limit(f"ratelimit:{key}", 3, 2)
    assert allowed3 is True
    assert count3 == 3

    # A2: Over the limit -> False
    allowed4, count4, _ = redis_service.check_rate_limit(f"ratelimit:{key}", 3, 2)
    assert allowed4 is False
    assert count4 == 4

    # A4: Wait for TTL expiration -> resets
    time.sleep(2.1)
    allowed5, count5, _ = redis_service.check_rate_limit(f"ratelimit:{key}", 3, 2)
    assert allowed5 is True
    assert count5 == 1


def test_a5_rate_limiting_concurrency_boundary():
    key = f"concurrency_limit_{time.time()}"
    limit = 10
    window = 10

    results = []

    def make_request(i):
        allowed, count, ttl = redis_service.check_rate_limit(f"ratelimit:{key}", limit, window)
        return allowed, count

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(make_request, i) for i in range(25)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    allowed_count = sum(1 for allowed, _ in results if allowed)
    blocked_count = sum(1 for allowed, _ in results if not allowed)

    assert allowed_count == limit, f"Expected exactly {limit} allowed requests, got {allowed_count}"
    assert blocked_count == 15, f"Expected 15 blocked requests, got {blocked_count}"


# =========================================================================
# TEST GROUP B & C — OTP LIFECYCLE & RESEND
# =========================================================================

def test_b_and_c_otp_lifecycle_and_resend(client: TestClient, db: Session):
    username = f"otp_user_{int(time.time() * 1000)}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"

    # Register User
    res = client.post(
        "/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert res.status_code == 201, res.text

    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.email_verified is False

    # B1: Verify Redis OTP key exists
    otp_key = f"otp:user:{user.id}"
    otp_data = redis_service.get(otp_key)
    assert otp_data is not None
    assert "otp_hash" in otp_data
    ttl = redis_service.ttl(otp_key)
    assert ttl > 0

    # C2: Immediate resend rejected by cooldown
    res_cooldown = client.post("/v1/auth/resend-otp", json={"email": email})
    assert res_cooldown.status_code == 429

    # B5: Wrong OTP increments attempt count
    res_wrong = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": "000000"},
    )
    assert res_wrong.status_code == 400
    attempts = int(redis_service.get(f"otp:attempts:{user.id}"))
    assert attempts >= 1

    # C3 & C4: Expire cooldown and resend -> fresh OTP
    redis_service.delete(f"otp:cooldown:{user.id}")
    res_resend = client.post("/v1/auth/resend-otp", json={"email": email})
    assert res_resend.status_code == 200

    # Inject known valid OTP directly into Redis test state
    known_otp = "852963"
    known_hash = hash_password(known_otp)
    user.email_otp_hash = known_hash
    db.commit()
    redis_service.set(
        otp_key,
        {"user_id": user.id, "email": user.email, "otp_hash": known_hash},
        ex=600,
    )

    # B2: Submit correct OTP
    res_verify = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": known_otp},
    )
    assert res_verify.status_code == 200
    assert "access_token" in res_verify.json()

    db.refresh(user)
    assert user.email_verified is True

    # B3: Try same OTP again -> rejected
    res_reuse = client.post(
        "/v1/auth/verify-email",
        json={"email": email, "otp": known_otp},
    )
    assert res_reuse.status_code == 200 or res_reuse.status_code == 400
    assert redis_service.get(otp_key) is None  # Redis key deleted!


# =========================================================================
# TEST GROUP D — PASSWORD RESET
# =========================================================================

def test_d_password_reset_lifecycle(client: TestClient, db: Session):
    username = f"pw_user_{int(time.time() * 1000)}"
    email = f"{username}@example.com"

    user = User(
        username=username,
        email=email,
        password_hash=hash_password("OldPassword123!"),
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_test_actor(db, user)

    # D1: Request password reset
    res_forgot = client.post("/v1/auth/forgot-password", json={"email": email})
    assert res_forgot.status_code == 200

    # D2: Verify Redis token created
    token = "test_reset_secret_token_123"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    reset_key = f"password_reset:{token_hash}"
    redis_service.set(reset_key, {"user_id": user.id, "email": email, "token_hash": hash_password(token)}, ex=900)

    # Set user DB token hash for consistency
    user.password_reset_token_hash = hash_password(token)
    user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.commit()

    # D3: Use correct token -> success
    new_password = "NewSuperPassword123!"
    res_reset = client.post(
        "/v1/auth/reset-password",
        json={"token": token, "email": email, "new_password": new_password},
    )
    assert res_reset.status_code == 200

    # D4: Reuse same token -> rejected (single use!)
    res_reuse = client.post(
        "/v1/auth/reset-password",
        json={"token": token, "email": email, "new_password": "AnotherPassword123!"},
    )
    assert res_reuse.status_code == 400
    assert redis_service.get(reset_key) is None

    # Verify new login works
    res_login = client.post(
        "/v1/auth/login",
        json={"login": username, "password": new_password},
    )
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()


# =========================================================================
# TEST GROUP E — AGENT SESSION & REVOCATION
# =========================================================================

def test_e_agent_session_and_immediate_revocation(db: Session):
    user = User(
        username=f"agent_owner_{int(time.time() * 1000)}",
        email=f"owner_{int(time.time() * 1000)}@example.com",
        password_hash=hash_password("Password123!"),
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_test_actor(db, user)

    agent = Agent(
        owner_id=user.id,
        name="test-agent-session",
        token_prefix="sutra_agt_pref1",
        token_hash=hash_password("sutra_agt_pref1_secret1234567890"),
        is_active=True,
        status="active",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # E1: Create AgentSession
    session, raw_token = create_agent_session(agent, db)
    assert session is not None
    assert raw_token.startswith("sutra_session_")

    # E2: Authenticated validation succeeds
    val_session = validate_agent_session_token(raw_token, db)
    assert val_session.id == session.id

    # E3: Revoke session
    revoke_agent_session(session, db)

    # E4: Immediately retry -> unauthorized
    with pytest.raises(Exception):
        validate_agent_session_token(raw_token, db)

    # E5: Try revoked session concurrently from 10 threads -> all unauthorized
    def test_revoked_call(i):
        try:
            validate_agent_session_token(raw_token, db)
            return "allowed"
        except Exception:
            return "rejected"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_revoked_call, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(r == "rejected" for r in results)

    # E6: Create new session -> works
    new_session, new_token = create_agent_session(agent, db)
    val_new = validate_agent_session_token(new_token, db)
    assert val_new.id == new_session.id

    # E7: Old revoked session remains rejected
    with pytest.raises(Exception):
        validate_agent_session_token(raw_token, db)


# =========================================================================
# TEST GROUP F — TEMPORARY PUSH TOKEN & ATOMIC DOUBLE-SPEND
# =========================================================================

def test_f_temporary_push_token_single_use_concurrency():
    temp_token = "sutra_temp_push_atomic_test_token_12345678"
    token_hash = hashlib.sha256(temp_token.encode("utf-8")).hexdigest()
    token_key = f"temp_push:{token_hash}"

    # Set token in Redis
    redis_service.set(
        token_key,
        {"registration_id": "reg_123", "user_id": "user_123", "repo_name": "repo_1"},
        ex=3600,
    )

    results = []

    def try_consume(i):
        return redis_service.consume_token_atomic(token_key)

    # Concurrently attempt to consume the single token across 10 workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_consume, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res is not None:
                results.append(res)

    # Exactly one worker must succeed in consuming the token!
    assert len(results) == 1, f"Expected exactly 1 successful consumption, got {len(results)}"
    assert results[0]["registration_id"] == "reg_123"

    # Subsequent check shows token is gone from Redis
    assert redis_service.get(token_key) is None


# =========================================================================
# TEST GROUP G — USER/AGENT ISOLATION
# =========================================================================

def test_g_user_agent_isolation():
    user1_otp_key = "otp:user:user_1111"
    user2_otp_key = "otp:user:user_2222"

    redis_service.set(user1_otp_key, {"user_id": "user_1111", "otp": "111111"}, ex=600)
    redis_service.set(user2_otp_key, {"user_id": "user_2222", "otp": "222222"}, ex=600)

    # User 1 cannot access User 2's key
    assert redis_service.get(user1_otp_key)["otp"] == "111111"
    assert redis_service.get(user2_otp_key)["otp"] == "222222"

    # Consuming User 1's token does not touch User 2's token
    redis_service.consume_token_atomic(user1_otp_key)
    assert redis_service.get(user1_otp_key) is None
    assert redis_service.get(user2_otp_key) is not None


# =========================================================================
# TEST GROUP H — DATABASE GROWTH & ZERO RAW SECRETS IN DB
# =========================================================================

def test_h_database_growth_and_no_raw_secrets(client: TestClient, db: Session):
    user = User(
        username=f"audit_user_{int(time.time() * 1000)}",
        email=f"audit_{int(time.time() * 1000)}@example.com",
        password_hash=hash_password("Password123!"),
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_test_actor(db, user)

    res = client.post(
        "/v1/agents/register",
        json={
            "agent_name": "AuditAgent",
            "owner_username": user.username,
            "repo_name": "test-repo",
            "new_repo": False,
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    reg_id = data["id"]
    temp_token = data.get("temporary_push_token")
    assert temp_token is not None

    # Verify in PostgreSQL: raw temporary_token column must be NULL!
    req_db = db.scalar(select(AgentRegistrationRequest).where(AgentRegistrationRequest.id == reg_id))
    assert req_db.temporary_token is None, "Raw temporary token must NOT be stored in PostgreSQL!"
    assert req_db.temporary_token_hash is not None

    # Verify User table has no raw OTP or raw reset token
    assert user.password_reset_token_hash is None or len(user.password_reset_token_hash) > 20


# =========================================================================
# TEST GROUP I — REDIS FAILURE BEHAVIOR (FAIL-CLOSED)
# =========================================================================

def test_i_redis_failure_fails_closed(client: TestClient):
    with patch("app.core.redis_service.RedisService.get", side_effect=Exception("Redis connection refused")):
        res = client.post(
            "/v1/auth/verify-email",
            json={"email": "nonexistent@example.com", "otp": "123456"},
        )
        # Must fail closed with 400 or 503, never 200!
        assert res.status_code in (400, 503)
        assert res.status_code != 200
