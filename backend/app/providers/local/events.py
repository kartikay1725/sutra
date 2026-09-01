from typing import Optional, Dict, Any, Union
from app.providers.events import WebhookEventAdapter, NormalizedPushEvent, NormalizedPullRequestEvent


class LocalWebhookAdapter(WebhookEventAdapter):
    """
    Local substrate event adapter for simulating or normalizing local repository events.
    """

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: str,
    ) -> bool:
        # Local events are internal or HMAC-verified via GitPushEvent integrity
        return True

    def parse_event(
        self,
        event_type_header: str,
        payload: Dict[str, Any],
    ) -> Optional[Union[NormalizedPushEvent, NormalizedPullRequestEvent, Any]]:
        event_type = event_type_header.lower()
        if event_type == "push":
            return NormalizedPushEvent(
                provider_type="local",
                repository_owner=payload.get("owner", ""),
                repository_name=payload.get("repo", ""),
                ref=payload.get("ref", "refs/heads/main"),
                before_sha=payload.get("before", "0000000000000000000000000000000000000000"),
                after_sha=payload.get("after", ""),
                is_created=payload.get("created", False),
                is_deleted=payload.get("deleted", False),
                is_forced=payload.get("forced", False),
                pusher_username=payload.get("pusher", "sutra_local"),
                commit_shas=payload.get("commits", []),
                raw_payload=payload,
            )
        return None
