import json
import logging
from typing import Any
import redis

from app.core.config import settings

logger = logging.getLogger("sutra.redis")


class RedisService:
    _instance = None
    _client: redis.Redis | None = None

    # Lua Script: Atomic Rate Limiter (sliding/fixed window counter)
    # KEYS[1]: rate limit key
    # ARGV[1]: max requests
    # ARGV[2]: window in seconds
    # Returns: 1 if allowed, 0 if blocked, followed by current count and TTL
    LUA_RATE_LIMIT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[2])
    end
    local ttl = redis.call('TTL', KEYS[1])
    if current > tonumber(ARGV[1]) then
        return {0, current, ttl}
    else
        return {1, current, ttl}
    end
    """

    # Lua Script: Atomic OTP Verification & Attempt Increment
    # KEYS[1]: otp key (stores json with hash and user_id)
    # KEYS[2]: attempts key
    # ARGV[1]: submitted otp (or hash to verify)
    # ARGV[2]: max attempts
    # Returns: 1 on success, 0 on wrong otp, -1 on expired/missing, -2 on too many attempts
    LUA_VERIFY_OTP = """
    local otp_data = redis.call('GET', KEYS[1])
    if not otp_data then
        return -1
    end
    local attempts = redis.call('INCR', KEYS[2])
    if attempts == 1 then
        redis.call('EXPIRE', KEYS[2], 600)
    end
    if attempts > tonumber(ARGV[2]) then
        redis.call('DEL', KEYS[1])
        return -2
    end
    return {1, otp_data, attempts}
    """

    # Lua Script: Atomic Token Single-Use Consumption (Double-Spend Protection)
    # KEYS[1]: token key
    # Returns: token data if existed and deleted, nil if already consumed or expired
    LUA_CONSUME_TOKEN = """
    local val = redis.call('GET', KEYS[1])
    if val then
        redis.call('DEL', KEYS[1])
        return val
    else
        return nil
    end
    """

    def __init__(self):
        self._rate_limit_script = None
        self._verify_otp_script = None
        self._consume_token_script = None

    @classmethod
    def get_client(cls) -> redis.Redis:
        if cls._client is None:
            try:
                cls._client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                    retry_on_timeout=True,
                )
                cls._client.ping()
            except Exception as e:
                logger.error(f"Redis connection failed to {settings.redis_url}: {e}")
                raise
        return cls._client

    @classmethod
    def is_available(cls) -> bool:
        try:
            client = cls.get_client()
            return bool(client.ping())
        except Exception:
            return False

    @classmethod
    def set(cls, key: str, value: Any, ex: int | None = None) -> bool:
        try:
            client = cls.get_client()
            serialized = json.dumps(value) if not isinstance(value, str) else value
            return bool(client.set(key, serialized, ex=ex))
        except Exception as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            raise

    @classmethod
    def get(cls, key: str) -> Any | None:
        try:
            client = cls.get_client()
            val = client.get(key)
            if val is None:
                return None
            try:
                return json.loads(val)
            except Exception:
                return val
        except Exception as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            raise

    @classmethod
    def delete(cls, *keys: str) -> int:
        try:
            client = cls.get_client()
            return client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            raise

    @classmethod
    def delete_by_pattern(cls, pattern: str) -> int:
        try:
            client = cls.get_client()
            keys = list(client.scan_iter(match=pattern, count=100))
            if keys:
                return client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_by_pattern failed for pattern {pattern}: {e}")
            return 0

    @classmethod
    def exists(cls, key: str) -> bool:
        try:
            client = cls.get_client()
            return bool(client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            raise

    @classmethod
    def ttl(cls, key: str) -> int:
        try:
            client = cls.get_client()
            return client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL failed for key {key}: {e}")
            raise

    @classmethod
    def incr(cls, key: str) -> int:
        try:
            client = cls.get_client()
            return client.incr(key)
        except Exception as e:
            logger.error(f"Redis INCR failed for key {key}: {e}")
            raise

    @classmethod
    def expire(cls, key: str, seconds: int) -> bool:
        try:
            client = cls.get_client()
            return bool(client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key {key}: {e}")
            raise

    @classmethod
    def consume_token_atomic(cls, key: str) -> Any | None:
        """
        Atomically fetch and delete a token in a single Redis transaction.
        Guarantees exact single-use consumption without race conditions.
        """
        try:
            client = cls.get_client()
            val = client.eval(cls.LUA_CONSUME_TOKEN, 1, key)
            if val is None:
                return None
            try:
                return json.loads(val)
            except Exception:
                return val
        except Exception as e:
            logger.error(f"Redis consume_token_atomic failed for key {key}: {e}")
            raise

    @classmethod
    def check_rate_limit(cls, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        """
        Atomic rate limiter returning (allowed, current_count, ttl).
        """
        try:
            client = cls.get_client()
            res = client.eval(cls.LUA_RATE_LIMIT, 1, key, max_requests, window_seconds)
            allowed = bool(res[0] == 1)
            current_count = int(res[1])
            ttl = int(res[2])
            return allowed, current_count, ttl
        except Exception as e:
            logger.error(f"Redis check_rate_limit failed for key {key}: {e}")
            raise


redis_service = RedisService()
