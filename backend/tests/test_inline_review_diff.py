from uuid import uuid4

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def _create_human_actor(
    db,
    user: User,
) -> Actor:
    actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    db.add(actor)
    db.flush()

    return actor


def test_parse_patch_text():
    sample_patch = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,4 +1,5 @@
 import os
+import sys

 def main():
-    print("hello")
+    print("hello world")
diff --git a/bin/logo.png b/bin/logo.png
Binary files a/bin/logo.png and b/bin/logo.png differ
"""

    files = PullRequestService._parse_patch_text(
        sample_patch
    )

    assert len(files) == 2

    app_file = files[0]

    assert app_file["path"] == "src/app.py"
    assert app_file["is_binary"] is False
    assert len(app_file["hunks"]) == 1

    hunk = app_file["hunks"][0]

    assert hunk["old_start"] == 1
    assert hunk["new_start"] == 1
    assert len(hunk["lines"]) == 6

    add_line = next(
        line
        for line in hunk["lines"]
        if line["content"] == "import sys"
    )

    assert add_line["type"] == "add"
    assert add_line["new_line_number"] == 2

    binary_file = files[1]

    assert binary_file["path"] == "bin/logo.png"
    assert binary_file["is_binary"] is True


def test_get_pull_request_files_service(db):
    user = User(
        id=str(uuid4()),
        username=f"diff_user_{uuid4().hex[:8]}",
        email=f"duser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add(user)
    db.flush()

    # PullRequestService resolves the author through Actor.
    _create_human_actor(
        db,
        user,
    )

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"diff_repo_{uuid4().hex[:8]}",
        description="Diff Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="diff_agent",
        token_prefix="prefix_diff_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Diff Change",
        risk_level="low",
        resulting_commit=(
            "1111111111111111111111111111111111111111"
        ),
        base_commit=(
            "0000000000000000000000000000000000000000"
        ),
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    db.add(change)

    cf1 = ChangeFile(
        change_id=change.id,
        path="src/main.py",
        operation="added",
        old_hash=None,
        new_hash="abc1234",
    )

    db.add(cf1)
    db.commit()

    svc = PullRequestService(db)

    pr = svc.create_pull_request(
        repo.id,
        user.id,
        change.id,
        "Diff PR",
        "main",
    )

    db.commit()

    result = svc.get_pull_request_files(
        pr.id,
        user.id,
    )

    assert result is not None

    pr_out, files_out = result

    assert pr_out.id == pr.id
    assert len(files_out) == 1
    assert files_out[0]["path"] == "src/main.py"
    assert files_out[0]["operation"] == "added"