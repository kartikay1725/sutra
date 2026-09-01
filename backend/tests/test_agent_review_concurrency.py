import concurrent.futures
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def setup_agent_concurrency_fixtures():
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        user = User(
            id=str(uuid4()),
            username=f"ag_conc_user_{uuid4().hex[:8]}",
            email=f"agconc_{uuid4().hex[:8]}@example.com",
            password_hash="hash",
        )
        db.add(user)
        db.flush()

        # PullRequestService resolves human PR authors through Actor.
        user_actor = Actor(
            id=user.id,
            owner_id=user.id,
            type="human",
            name=user.username,
            capabilities=(
                '["repository.read", '
                '"repository.write", '
                '"change.create"]'
            ),
        )
        db.add(user_actor)
        db.flush()

        repo = RepositoryService(db).create(
            owner_id=user.id,
            name=f"ag_conc_repo_{uuid4().hex[:8]}",
            description="Agent Concurrency Repo",
            visibility="private",
        )

        agent = Agent(
            id=str(uuid4()),
            owner_id=user.id,
            name="ag_conc_agent",
            token_prefix="prefix_agconc_12",
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
            intent="Agent Concurrency Change",
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
        db.commit()

        svc = PullRequestService(db)

        pr = svc.create_pull_request(
            repo.id,
            user.id,
            change.id,
            "Agent Concurrency PR",
            "main",
        )
        db.commit()

        agent_id = agent.id
        pr_id = pr.id

        return agent_id, pr_id, SessionLocal

    finally:
        db.close()


def test_concurrent_agent_findings_creation():
    agent_id, pr_id, SessionLocal = (
        setup_agent_concurrency_fixtures()
    )

    def worker_finding(worker_idx: int):
        db = SessionLocal()

        try:
            svc = AgentReviewService(db)

            finding = svc.create_agent_finding(
                agent_id=agent_id,
                pull_request_id=pr_id,
                severity=(
                    "low"
                    if worker_idx % 2 == 0
                    else "medium"
                ),
                category="bug",
                message=f"Concurrent finding {worker_idx}",
                path="src/main.py",
                line_number=worker_idx + 1,
            )

            db.commit()
            return finding.id

        finally:
            db.close()

    num_workers = 10

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=num_workers
    ) as executor:
        futures = [
            executor.submit(
                worker_finding,
                i,
            )
            for i in range(num_workers)
        ]

        created_ids = [
            future.result()
            for future in concurrent.futures.as_completed(
                futures
            )
        ]

    assert len(created_ids) == num_workers

    db = SessionLocal()

    try:
        comments = db.scalars(
            select(InlineReviewComment).where(
                InlineReviewComment.pull_request_id
                == pr_id
            )
        ).all()

        assert len(comments) == num_workers

    finally:
        db.close()