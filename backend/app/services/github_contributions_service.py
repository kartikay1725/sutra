import json
import logging
import re
from typing import Tuple
import httpx
from app.core.redis_service import redis_service

logger = logging.getLogger("sutra.github_contributions")

_CACHE_PREFIX = "github_contributions:"
_CACHE_TTL_SECONDS = 1800  # 30 minutes


def clean_github_username(raw: str | None) -> str | None:
    """Extract clean GitHub login from username or profile URL."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().rstrip("/")
    if not cleaned:
        return None
    # Handle full URLs: https://github.com/octocat
    if "github.com/" in cleaned:
        cleaned = cleaned.split("github.com/")[-1].split("/")[0]
    # Handle @mentions
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    # Validate GitHub username characters
    if re.match(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$", cleaned):
        return cleaned
    return None


def fetch_github_contributions(username: str) -> Tuple[dict[str, int], bool]:
    """
    Fetches the last 365 days of public GitHub contributions for a GitHub user.
    Returns (dict[date_str, count], success_bool).
    Results are cached in Redis to prevent external rate-limiting.
    """
    clean_user = clean_github_username(username)
    if not clean_user:
        return {}, False

    cache_key = f"{_CACHE_PREFIX}{clean_user.lower()}"

    # 1. Check Redis Cache
    try:
        cached = redis_service.get(cache_key)
        if cached:
            if isinstance(cached, str):
                data = json.loads(cached)
                return data, True
            elif isinstance(cached, dict):
                return cached, True
    except Exception as e:
        logger.debug(f"Redis cache check failed for {cache_key}: {e}")

    result_map: dict[str, int] = {}
    success = False

    # 2. Primary Provider: jogruber GitHub contributions API
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(f"https://github-contributions-api.jogruber.de/v4/{clean_user}?y=last")
            if resp.status_code == 200:
                payload = resp.json()
                items = payload.get("contributions", [])
                for item in items:
                    d = item.get("date")
                    c = item.get("count", 0)
                    if d and isinstance(c, (int, float)):
                        result_map[d] = int(c)
                if result_map:
                    success = True
    except Exception as e:
        logger.debug(f"Primary GitHub contribution API failed for {clean_user}: {e}")

    # 3. Secondary Provider: Deno GitHub contributions API
    if not success:
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(f"https://github-contributions-api.deno.dev/{clean_user}.json")
                if resp.status_code == 200:
                    payload = resp.json()
                    # format: list of weeks or list of days
                    contributions = payload.get("contributions", [])
                    if isinstance(contributions, list):
                        for week in contributions:
                            days = week.get("days", []) if isinstance(week, dict) else []
                            for day in days:
                                d = day.get("date")
                                c = day.get("contributionCount", 0)
                                if d:
                                    result_map[d] = int(c)
                    if result_map:
                        success = True
        except Exception as e:
            logger.debug(f"Secondary GitHub contribution API failed for {clean_user}: {e}")

    # 4. Fallback: Direct GitHub HTML profile contributions table
    if not success:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            with httpx.Client(timeout=4.0, headers=headers) as client:
                resp = client.get(f"https://github.com/users/{clean_user}/contributions")
                if resp.status_code == 200:
                    matches = re.findall(
                        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d+)"',
                        resp.text,
                    )
                    for d, lvl in matches:
                        result_map[d] = int(lvl)
                    if result_map:
                        success = True
        except Exception as e:
            logger.debug(f"Direct GitHub contributions scrape failed for {clean_user}: {e}")

    # 5. Store in Redis if successfully retrieved
    if success and result_map:
        try:
            redis_service.set(cache_key, json.dumps(result_map), ex=_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.debug(f"Redis cache set failed for {cache_key}: {e}")

    return result_map, success
