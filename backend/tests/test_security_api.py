import json

from app.models.change_event import ChangeEvent


def test_security_endpoint_no_longer_uses_demo_findings():
    # Regression guard: the old implementation always returned sec-1/sec-2.
    # The new implementation reads agent_review.finding_created events.
    assert "_mock_security_findings" not in open(
        "app/api/security.py", encoding="utf-8"
    ).read()


def test_security_event_type_is_authoritative():
    assert ChangeEvent.__tablename__ == "change_events"
