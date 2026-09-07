import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import hash_password

from app.models.user import User
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.models.issue import Issue


GITHUB_OWNER = "kartikay1725"
GITHUB_REPOSITORY = "dam-project"


def test_live_agent_issue_e2e():
    """
    Full live Agent Issue E2E:

        temporary SUTRA user
              ↓
        temporary SUTRA repository
              ↓
        registered Agent
              ↓
        Agent Actor
              ↓
        AgentSession
              ↓
        claimed Task
              ↓
        real SUTRA Agent Issue endpoint
              ↓
        real GitHub App
              ↓
        real GitHub Issue
              ↓
        SUTRA Issue provenance
    """

    db = SessionLocal()

    user = None
    repository = None
    agent = None
    actor = None
    session = None
    task = None

    github_issue_number = None

    try:
        # =========================================================
        # 1. Build REAL GitHub provider
        # =========================================================

        from app.providers.github.auth import (
            GitHubAppAuthService,
        )
        from app.providers.github.repository import (
            GitHubRepositoryProvider,
        )

        assert settings.github_app_id
        assert settings.github_private_key_pem
        assert settings.github_api_base_url

        auth = GitHubAppAuthService(
            app_id=settings.github_app_id,
            private_key_pem=settings.github_private_key_pem,
            base_url=settings.github_api_base_url,
        )

        provider = GitHubRepositoryProvider(
            auth_service=auth,
            base_url=settings.github_api_base_url,
        )

        # =========================================================
        # 2. Verify the real GitHub repository exists
        # =========================================================

        # Fetching the repository through the existing provider is
        # intentionally used rather than inventing GitHub metadata.
        #
        # The provider's branch call also proves the installation
        # can access the repository.
        branches = provider.list_branches(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
        )

        assert branches, (
            f"GitHub repository "
            f"{GITHUB_OWNER}/{GITHUB_REPOSITORY} "
            f"returned no branches"
        )

        default_branch = "master"

        assert any(
            getattr(branch, "name", None) == default_branch
            for branch in branches
        ), (
            f"Expected GitHub branch '{default_branch}' "
            f"was not found"
        )

        print()
        print(
            f"Verified GitHub repository: "
            f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}"
        )
        print(
            f"Verified default branch: {default_branch}"
        )

        # =========================================================
        # 3. Create temporary SUTRA user
        # =========================================================

        user = User(
            id=str(uuid4()),
            username=f"live_agent_user_{uuid4().hex[:8]}",
            email=f"live_agent_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("password123"),
        )

        db.add(user)
        db.flush()

        # =========================================================
        # 4. Create temporary SUTRA GitHub repository mapping
        #
        # We use a synthetic SUTRA repository UUID and a real
        # GitHub installation ID. The GitHub provider remains the
        # authoritative external system.
        # =========================================================

        repository = Repository(
            id=str(uuid4()),
            owner_id=user.id,
            name=GITHUB_REPOSITORY,
            slug=GITHUB_REPOSITORY,
            description=(
                "Temporary SUTRA mapping for live "
                "Agent Issue E2E test"
            ),
            visibility="private",
            storage_key=(
                f"github-test/"
                f"{uuid4().hex}"
            ),
            provider_type="github",
            provider_owner=GITHUB_OWNER,
            external_id=f"live-e2e-{uuid4().hex}",
            github_installation_id=(
                settings.github_installation_id
                if hasattr(settings, "github_installation_id")
                else 158557464
            ),
            default_branch=default_branch,
            settings={},
        )

        db.add(repository)
        db.flush()

        assert repository.provider_type == "github"
        assert repository.provider_owner == GITHUB_OWNER
        assert repository.github_installation_id
        assert repository.default_branch == default_branch

        print(
            f"SUTRA repository ID: {repository.id}"
        )
        print(
            f"GitHub installation ID: "
            f"{repository.github_installation_id}"
        )

        # =========================================================
        # 5. Temporary registered Agent
        # =========================================================

        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name=f"Atlas-Live-{uuid4().hex[:6]}",
            description=(
                "Temporary live Agent Issue E2E agent"
            ),
            provider="test",
            model="test-model",
            token_hash=hash_password(
                f"unused-agent-token-{uuid4().hex}"
            ),
            token_prefix=uuid4().hex[:16],
            status="active",
            is_active=True,
        )

        db.add(agent)
        db.flush()

        print(f"Agent: {agent.name}")
        print(f"Agent ID: {agent.id}")

        # =========================================================
        # 6. Agent Actor
        # =========================================================

        actor = Actor(
            id=agent.id,
            type="agent",
            name=agent.name,
            owner_id=user.id,
            capabilities=(
                '["repository.read",'
                '"repository.write",'
                '"change.create",'
                '"change.commit",'
                '"change.conflict.read"]'
            ),
        )

        db.add(actor)
        db.flush()

        # =========================================================
        # 7. Real AgentSession
        # =========================================================

        session_token = (
            f"sutra_session_{uuid4().hex}_{uuid4().hex}"
        )

        session = AgentSession(
            id=str(uuid4()),
            agent_id=agent.id,
            token_hash=hash_password(session_token),
            token_prefix=session_token[:32],
            status="active",
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(hours=1)
            ),
            last_seen_at=datetime.now(timezone.utc),
        )

        db.add(session)
        db.flush()

        print(f"Session ID: {session.id}")

        # =========================================================
        # 8. Claimed Task
        # =========================================================

        task = Task(
            id=str(uuid4()),
            repository_id=repository.id,
            created_by=user.id,
            assigned_agent_id=agent.id,
            assigned_user_id=None,
            claimed_by_session_id=session.id,
            lease_expires_at=(
                datetime.now(timezone.utc)
                + timedelta(hours=1)
            ),
            resulting_change_id=None,
            resulting_pull_request_id=None,
            title=(
                f"Live Agent Issue E2E "
                f"{uuid4().hex[:8]}"
            ),
            description=(
                "Create a real GitHub issue through "
                "the authenticated SUTRA agent."
            ),
            status=Task.STATUS_IN_PROGRESS,
            priority=Task.PRIORITY_MEDIUM,
            priority_index=0.0,
            task_type=Task.TYPE_FEATURE,
            source="live_test",
        )

        db.add(task)
        db.commit()

        print(f"Task ID: {task.id}")

        # =========================================================
        # 9. Call REAL SUTRA Agent Issue API
        # =========================================================

        marker = uuid4().hex[:8]

        requested_title = (
            f"Live Agent Issue E2E {marker}"
        )

        requested_body = (
            "This issue was created by the real "
            "SUTRA Agent Issue E2E test."
        )

        print()
        print(
            "Calling real SUTRA Agent Issue endpoint..."
        )

        with TestClient(app) as client:
            response = client.post(
                f"/v1/agent/tasks/{task.id}/issues",
                headers={
                    "Authorization":
                        f"Bearer {session_token}",
                },
                json={
                    "title": requested_title,
                    "body": requested_body,
                },
            )

        print(
            f"HTTP STATUS: {response.status_code}"
        )
        print(
            f"RESPONSE: {response.text}"
        )

        assert response.status_code == 201, response.text

        data = response.json()
        github_issue_number = data["github_issue_number"]
        # =========================================================
        # 10. Verify API response
        # =========================================================

        assert data["github_issue_number"] > 0
        

        expected_title = (
            f"[Agent: {agent.name}] "
            f"{requested_title}"
        )

        assert data["title"] == expected_title
        assert data["status"] == "open"
        assert data["source_type"] == "agent"
        assert data["agent_id"] == agent.id
        assert data["agent_session_id"] == session.id
        assert data["task_id"] == task.id
        assert data["github_html_url"].startswith("https://github.com/")


        # =========================================================
        # 11. Verify SUTRA provenance persistence
        # =========================================================

        stored_issue = db.scalar(
            select(Issue).where(
                Issue.repository_id == repository.id,
                Issue.github_issue_number
                == github_issue_number,
            )
        )

        assert stored_issue is not None

        assert stored_issue.source_type == "agent"
        assert stored_issue.agent_id == agent.id
        assert (
            stored_issue.agent_session_id
            == session.id
        )
        assert stored_issue.task_id == task.id
        assert stored_issue.author_id == agent.id
        assert (
            stored_issue.github_issue_number
            == github_issue_number
        )

        # =========================================================
        # 12. Directly verify the REAL GitHub issue
        # =========================================================

        github_issue = provider.get_issue(
            owner=GITHUB_OWNER,
            name=GITHUB_REPOSITORY,
            issue_number=github_issue_number,
        )

        assert github_issue is not None
        assert (
            github_issue.number
            == github_issue_number
        )
        assert github_issue.state == "open"
        assert github_issue.title == expected_title
        assert github_issue.html_url

        # =========================================================
        # 13. Verify SUTRA agent identity is visible on GitHub
        # =========================================================

        assert (
            f"**Agent:** {agent.name}"
            in github_issue.body
        )

        assert (
            f"**Agent ID:** `{agent.id}`"
            in github_issue.body
        )

        assert (
            f"**Session ID:** `{session.id}`"
            in github_issue.body
        )

        assert (
            f"**Task ID:** `{task.id}`"
            in github_issue.body
        )

        assert requested_body in github_issue.body

        # =========================================================
        # 14. FINAL RESULT
        # =========================================================

        print()
        print("=" * 76)
        print("LIVE AGENT ISSUE E2E PASSED")
        print("=" * 76)
        print(
            "PASS: Real GitHub repository access"
        )
        print(
            "PASS: Temporary SUTRA GitHub repository mapping"
        )
        print(
            "PASS: Registered SUTRA Agent"
        )
        print(
            "PASS: Agent Actor identity"
        )
        print(
            "PASS: Real AgentSession authentication"
        )
        print(
            "PASS: Claimed Task authorization"
        )
        print(
            "PASS: Real SUTRA Agent Issue endpoint"
        )
        print(
            "PASS: Real GitHub Issue creation"
        )
        print(
            "PASS: SUTRA Issue provenance persistence"
        )
        print(
            "PASS: Agent identity written to GitHub"
        )
        print()
        print(
            f"GitHub Issue: #{github_issue_number}"
        )
        print(
            f"GitHub URL: {github_issue.html_url}"
        )
        print(
            f"Agent: {agent.name}"
        )
        print(
            f"Agent ID: {agent.id}"
        )
        print(
            f"Session ID: {session.id}"
        )
        print(
            f"Task ID: {task.id}"
        )
        print("=" * 76)

    finally:
        # =========================================================
        # Cleanup temporary SUTRA data.
        #
        # GitHub issue is intentionally NOT deleted.
        # =========================================================

        try:
            db.rollback()

            if task is not None:
                db.query(Task).filter(
                    Task.id == task.id
                ).delete(
                    synchronize_session=False
                )
                db.flush()

            if session is not None:
                db.query(AgentSession).filter(
                    AgentSession.id == session.id
                ).delete(
                    synchronize_session=False
                )
                db.flush()

            if actor is not None:
                db.query(Actor).filter(
                    Actor.id == actor.id
                ).delete(
                    synchronize_session=False
                )
                db.flush()

            if agent is not None:
                db.query(Agent).filter(
                    Agent.id == agent.id
                ).delete(
                    synchronize_session=False
                )
                db.flush()

            if repository is not None:
                db.query(Repository).filter(
                    Repository.id == repository.id
                ).delete(
                    synchronize_session=False
                )
                db.flush()

            if user is not None:
                db.query(User).filter(
                    User.id == user.id
                ).delete(
                    synchronize_session=False
                )
                db.flush()

            db.commit()

        finally:
            db.close()