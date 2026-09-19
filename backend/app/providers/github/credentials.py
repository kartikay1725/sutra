from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import json
import logging

from app.core.redis_service import redis_service
from app.providers.credentials import CredentialProvider, DownstreamCredential
from app.providers.github.auth import GitHubAppAuthService

logger = logging.getLogger("sutra.providers.github.credentials")


class GitHubCredentialProvider(CredentialProvider):
    """
    Brokers strictly scoped, short-lived GitHub App Installation Access Tokens
    for agents, with SUTRA-enforced 10-minute maximum horizon and active revocation.
    """

    def __init__(self, auth_service: GitHubAppAuthService):
        self.auth_service = auth_service

    def _map_capabilities_to_permissions(self, capabilities: List[str]) -> Dict[str, str]:
        """
        Minimal capability mapping.
        repository.write maps strictly to contents:write.
        Never grants pull_requests:write or admin rights to agent tokens.
        """
        perms = {"metadata": "read"}
        if "repository.write" in capabilities:
            perms["contents"] = "write"
        elif "repository.read" in capabilities:
            perms["contents"] = "read"

        if "workflow.write" in capabilities:
            perms["workflows"] = "write"
        elif "workflow.read" in capabilities:
            perms["workflows"] = "read"
        return perms

    def issue_agent_token(
        self,
        agent_id: str,
        session_id: str,
        owner: str,
        repo: str,
        sutra_capabilities: List[str],
        max_ttl_seconds: int = 600,
    ) -> DownstreamCredential:
        # Enforce effective TTL <= 10 minutes (600 seconds)
        effective_ttl = min(max(max_ttl_seconds, 60), 600)
        now = datetime.now(timezone.utc)
        effective_expires_at = now + timedelta(seconds=effective_ttl)

        inst_id = self.auth_service.get_installation_id(owner, repo)
        permissions = self._map_capabilities_to_permissions(sutra_capabilities)

        token_data = self.auth_service.create_installation_token(
            installation_id=inst_id,
            repositories=[repo],
            permissions=permissions,
        )

        raw_token = token_data["token"]
        clone_url = f"https://x-access-token:{raw_token}@github.com/{owner}/{repo}.git"

        # Record in Redis for active revocation tracking
        token_record = {
            "token": raw_token,
            "agent_id": agent_id,
            "session_id": session_id,
            "owner": owner,
            "repo": repo,
            "expires_at": effective_expires_at.isoformat(),
        }
        
        try:
            r = redis_service.get_client()
            r.sadd(f"github_tokens:session:{session_id}", json.dumps(token_record))
            r.expire(f"github_tokens:session:{session_id}", effective_ttl + 60)
        except Exception as e:
            logger.warning(f"Failed to record GitHub token in Redis for session {session_id}: {e}")

        return DownstreamCredential(
            token=raw_token,
            token_type="installation",
            expires_at=effective_expires_at,
            effective_ttl_seconds=effective_ttl,
            repository=f"{owner}/{repo}",
            permissions=permissions,
            clone_url=clone_url,
            provider_token_id=raw_token[:10],
        )

    def revoke_credential(
        self,
        session_id: str,
        token_or_id: str,
    ) -> bool:
        # Actively revoke downstream token on GitHub
        revoked = self.auth_service.revoke_installation_token(token_or_id)
        try:
            r = redis_service.get_client()
            members = r.smembers(f"github_tokens:session:{session_id}")
            for m in members:
                try:
                    data = json.loads(m)
                    if data.get("token") == token_or_id:
                        r.srem(f"github_tokens:session:{session_id}", m)
                except Exception:
                    pass
        except Exception:
            pass
        return revoked

    def revoke_all_session_credentials(
        self,
        session_id: str,
    ) -> int:
        count = 0
        try:
            r = redis_service.get_client()
            members = r.smembers(f"github_tokens:session:{session_id}")
            for m in members:
                try:
                    data = json.loads(m)
                    token = data.get("token")
                    if token:
                        if self.auth_service.revoke_installation_token(token):
                            count += 1
                except Exception as e:
                    logger.warning(f"Error revoking token for session {session_id}: {e}")
            r.delete(f"github_tokens:session:{session_id}")
        except Exception as e:
            logger.error(f"Failed to retrieve tokens from Redis for session {session_id}: {e}")
        return count
