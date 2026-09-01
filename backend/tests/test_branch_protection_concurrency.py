import concurrent.futures
from uuid import uuid4
import pytest
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.branch_protection_rule import BranchProtectionRule
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.user import User
from app.services.branch_protection_service import BranchProtectionService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_bp_concurrency_fixtures():
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(
        id=str(uuid4()),
        username=f"bp_conc_user_{uuid4().hex[:8]}",
        email=f"bpconc_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)
    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"bp_conc_repo_{uuid4().hex[:8]}",
        description="BP Concurrency Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="bp_conc_agent",
        token_prefix="prefix_bpconc_12",
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
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.commit()

    user_id = user.id
    repo_id = repo.id
    db.close()
    engine.dispose()

    return user_id, repo_id, SessionLocal


def test_concurrent_branch_protection_rule_creation():
    user_id, repo_id, SessionLocal = setup_bp_concurrency_fixtures()

    def worker_create(worker_idx: int):
        db = SessionLocal()
        try:
            svc = BranchProtectionService(db)
            rule = svc.create_rule(
                repository_id=repo_id,
                actor_user_id=user_id,
                branch_pattern=f"feature/branch-{worker_idx}",
                required_approvals=1,
            )
            db.commit()
            return rule.id
        finally:
            db.close()

    num_workers = 10
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_create, i) for i in range(num_workers)]
        created_ids = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(created_ids) == num_workers

    db = SessionLocal()
    rules = db.scalars(
        select(BranchProtectionRule).where(BranchProtectionRule.repository_id == repo_id)
    ).all()
    assert len(rules) == num_workers
    db.close()
