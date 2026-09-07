import hmac
import hashlib
from typing import Optional, Dict, Any, Union
from app.providers.events import (
    WebhookEventAdapter,
    NormalizedPushEvent,
    NormalizedPullRequestEvent,
    NormalizedCheckRunEvent,
)


class GitHubWebhookAdapter(WebhookEventAdapter):
    """
    Validates GitHub webhook signatures using HMAC-SHA256 and
    normalizes payloads into unified SUTRA domain events.
    """

    def verify_signature(
        self,
        payload_bytes: bytes,
        headers: Dict[str, str],
        secret: str,
    ) -> bool:
        signature = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
        if not signature or not secret:
            return False

        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def parse_event(
        self,
        event_type_header: str,
        payload: Dict[str, Any],
    ) -> Optional[Union[NormalizedPushEvent, NormalizedPullRequestEvent, Any]]:
        event_type = event_type_header.lower()
        repo_data = payload.get("repository", {})
        owner = repo_data.get("owner", {}).get("login", "")
        name = repo_data.get("name", "")

        if event_type == "push":
            ref = payload.get("ref", "")
            before = payload.get("before", "")
            after = payload.get("after", "")
            commits = [c["id"] for c in payload.get("commits", []) if "id" in c]
            pusher = payload.get("pusher", {}).get("name", "")

            return NormalizedPushEvent(
                provider_type="github",
                repository_owner=owner,
                repository_name=name,
                ref=ref,
                before_sha=before,
                after_sha=after,
                is_created=payload.get("created", False),
                is_deleted=payload.get("deleted", False),
                is_forced=payload.get("forced", False),
                pusher_username=pusher,
                commit_shas=commits,
                raw_payload=payload,
            )

        elif event_type == "pull_request":
            pr_data = payload.get("pull_request", {})
            return NormalizedPullRequestEvent(
                provider_type="github",
                repository_owner=owner,
                repository_name=name,
                pr_number=pr_data.get("number", payload.get("number", 0)),
                action=payload.get("action", ""),
                head_ref=pr_data.get("head", {}).get("ref", ""),
                head_sha=pr_data.get("head", {}).get("sha", ""),
                base_ref=pr_data.get("base", {}).get("ref", ""),
                base_sha=pr_data.get("base", {}).get("sha", ""),
                is_merged=pr_data.get("merged", False),
                raw_payload=payload,
            )

        elif event_type == "check_run":
            check_data = payload.get("check_run", {})
            pr_numbers = [
                pr["number"]
                for pr in check_data.get("pull_requests", [])
                if isinstance(pr, dict) and "number" in pr
            ]
            return NormalizedCheckRunEvent(
                provider_type="github",
                repository_owner=owner,
                repository_name=name,
                check_run_id=check_data.get("id", 0),
                name=check_data.get("name", ""),
                head_sha=check_data.get("head_sha", ""),
                status=check_data.get("status", "completed"),
                conclusion=check_data.get("conclusion"),
                html_url=check_data.get("html_url"),
                details_url=check_data.get("details_url"),
                started_at=check_data.get("started_at"),
                completed_at=check_data.get("completed_at"),
                pull_request_numbers=pr_numbers,
                raw_payload=payload,
            )

        return None
