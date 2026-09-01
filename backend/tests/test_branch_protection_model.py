from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.branch_protection_rule import BranchProtectionRule
from app.models.user import User
from app.services.repository_service import RepositoryService


def setup_bp_model_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"bp_muser_{uuid4().hex[:8]}",
        email=f"bpmuser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"bp_mrepo_{uuid4().hex[:8]}",
        description="BP Model Repo",
        visibility="private",
    )
    db.commit()
    return user, repo


def test_create_branch_protection_rule_model(db):
    user, repo = setup_bp_model_fixtures(db)

    rule = BranchProtectionRule(
        repository_id=repo.id,
        branch_pattern="main",
        enabled=True,
        required_approvals=2,
        require_change_review=True,
        require_clean_conflict=True,
        require_resolved_threads=True,
        require_agent_review=False,
        require_no_blocking_agent_findings=False,
        allow_author_self_approval=False,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(rule)
    db.commit()

    saved = db.scalar(
        select(BranchProtectionRule).where(BranchProtectionRule.id == rule.id)
    )
    assert saved is not None
    assert saved.repository_id == repo.id
    assert saved.branch_pattern == "main"
    assert saved.required_approvals == 2
    assert saved.require_resolved_threads is True


def test_branch_protection_rule_unique_constraint(db):
    user, repo = setup_bp_model_fixtures(db)

    rule1 = BranchProtectionRule(
        repository_id=repo.id,
        branch_pattern="main",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(rule1)
    db.commit()

    rule2 = BranchProtectionRule(
        repository_id=repo.id,
        branch_pattern="main",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(rule2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
