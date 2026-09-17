import logging
import urllib.parse
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, case, desc

from app.api.dependencies import get_current_user_optional
from app.api.integrations import _build_auth_service
from app.core.redis_service import redis_service
from app.db.session import get_db
from app.models.repository import Repository
from app.models.actor import Actor
from app.models.task import Task
from app.models.pull_request import PullRequest
from app.models.issue import Issue
from app.models.change import Change
from app.models.user import User
from app.services.github_installation_service import GitHubInstallationService

logger = logging.getLogger("sutra.api.search")

router = APIRouter(prefix="/v1/search", tags=["search"])


class SearchResult(BaseModel):
    type: str  # "repository", "user", "organization", "task", "pull_request", "issue", "change"
    name: str
    description: str | None = None
    url: str


@router.get("", response_model=list[SearchResult])
def search(
    q: str = Query(..., min_length=1),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    results: list[dict] = []
    clean_q = q.strip()
    if not clean_q:
        return results

    # Authorized repository filter predicate
    def repo_access_filter(repo_model=Repository):
        if current_user:
            return or_(
                repo_model.visibility == "public",
                repo_model.owner_id == current_user.id,
                repo_model.provider_owner == current_user.username,
            )
        return repo_model.visibility == "public"

    # Numeric query parsing for issue / PR number references (#18, 18, etc.)
    stripped_hash = clean_q.lstrip("#").strip()
    clean_num = stripped_hash if stripped_hash.isdigit() else None

    # Handle owner/repo query format (e.g. "kartikay1725/sutra")
    owner_part: str | None = None
    repo_part: str | None = None
    if "/" in clean_q:
        parts = clean_q.split("/", 1)
        owner_part = parts[0].strip()
        repo_part = parts[1].strip()

    if owner_part and repo_part:
        repo_filter_clause = or_(
            (
                (Actor.name.ilike(f"%{owner_part}%") | Repository.provider_owner.ilike(f"%{owner_part}%"))
                & (Repository.name.ilike(f"%{repo_part}%") | Repository.slug.ilike(f"%{repo_part}%"))
            ),
            Repository.name.ilike(f"%{clean_q}%"),
            Repository.description.ilike(f"%{clean_q}%"),
        )
    else:
        search_term = f"%{clean_q}%"
        repo_filter_clause = or_(
            Repository.name.ilike(search_term),
            Repository.slug.ilike(search_term),
            Repository.description.ilike(search_term),
            Repository.provider_owner.ilike(search_term),
            Actor.name.ilike(search_term),
        )

    # Smart ranking for repos:
    # 1. User-owned repositories first
    # 2. Exact match on name
    # 3. Starts-with on name
    # 4. Substring in name
    # 5. Recently updated
    order_clauses = []
    if current_user:
        order_clauses.append(
            case((Repository.owner_id == current_user.id, 1), else_=2)
        )
    order_clauses.extend([
        case(
            (Repository.name.ilike(clean_q), 1),
            (Repository.name.ilike(f"{clean_q}%"), 2),
            (Repository.name.ilike(f"%{clean_q}%"), 3),
            else_=4,
        ),
        Repository.updated_at.desc(),
    ])

    # 1. Search database repositories
    repo_rows = (
        db.query(Repository, Actor.name.label("owner_name"))
        .join(Actor, Repository.owner_id == Actor.id)
        .filter(
            Repository.deleted_at.is_(None),
            repo_access_filter(Repository),
            repo_filter_clause,
        )
        .order_by(*order_clauses)
        .limit(10)
        .all()
    )

    seen_repo_keys: set[str] = set()
    for repo, owner_name in repo_rows:
        display_owner = repo.provider_owner or owner_name or (current_user.username if current_user and repo.owner_id == current_user.id else "repository")
        display_name = f"{display_owner}/{repo.name}"
        repo_key = f"{display_owner}/{repo.name}".lower()
        if repo_key in seen_repo_keys:
            continue
        seen_repo_keys.add(repo_key)
        results.append({
            "type": "repository",
            "name": display_name,
            "description": repo.description or f"{repo.visibility.capitalize()} repository",
            "url": f"/repositories/{urllib.parse.quote(repo.name)}",
        })

    # 2. If user is connected to GitHub, also search connected GitHub repositories (cached in Redis)
    if current_user:
        try:
            auth_service = _build_auth_service()
            gh_service = GitHubInstallationService(auth_service)
            installation = gh_service.get_installation_for_user(db, current_user.id)
            if installation:
                cache_key = f"github:user_repos:{installation.github_installation_id}"
                cached_repos = None
                try:
                    cached_repos = redis_service.get(cache_key)
                except Exception:
                    pass

                if cached_repos is None:
                    try:
                        cached_repos = gh_service.list_repos_for_installation(installation.github_installation_id)
                        try:
                            redis_service.set(cache_key, cached_repos, ex=120)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"Could not fetch GitHub repositories for search: {e}")
                        cached_repos = []

                q_lower = clean_q.lower()
                for gh_repo in (cached_repos or []):
                    gh_name = gh_repo.get("name", "")
                    gh_owner = gh_repo.get("owner", {}).get("login", "")
                    gh_key = f"{gh_owner}/{gh_name}".lower()
                    if not gh_name or gh_key in seen_repo_keys or gh_name.lower() in seen_repo_keys:
                        continue
                    gh_desc = gh_repo.get("description") or ""

                    matches = False
                    if owner_part and repo_part:
                        matches = (owner_part.lower() in gh_owner.lower() and repo_part.lower() in gh_name.lower())
                    else:
                        matches = (
                            q_lower in gh_name.lower()
                            or q_lower in gh_owner.lower()
                            or (gh_desc and q_lower in gh_desc.lower())
                        )

                    if matches:
                        try:
                            gh_service.sync_repos_for_user(db, current_user, installation)
                            db.commit()
                        except Exception:
                            pass

                        seen_repo_keys.add(gh_key)
                        seen_repo_keys.add(gh_name.lower())
                        results.append({
                            "type": "repository",
                            "name": f"{gh_owner}/{gh_name}",
                            "description": gh_desc or f"{'Private' if gh_repo.get('private') else 'Public'} GitHub repository",
                            "url": f"/repositories/{urllib.parse.quote(gh_name)}",
                        })
                        if len(results) >= 10:
                            break
        except Exception as e:
            logger.warning(f"GitHub repository search check failed: {e}")

    # 3. Search users / orgs
    actors = (
        db.query(Actor)
        .filter(Actor.name.ilike(f"%{clean_q}%"))
        .filter(Actor.type.in_(["user", "organization"]))
        .limit(10)
        .all()
    )
    for actor in actors:
        results.append({
            "type": actor.type,
            "name": actor.name,
            "description": actor.type.capitalize(),
            "url": f"/profile/{actor.name}",
        })

    # 4. Search tasks (strictly scoped to accessible repositories, user's repos prioritized)
    task_order = []
    if current_user:
        task_order.append(case((Repository.owner_id == current_user.id, 1), else_=2))
    task_order.extend([
        case((Task.status.in_(["open", "in_progress", "assigned"]), 1), else_=2),
        Task.updated_at.desc(),
    ])

    task_filters = [
        Task.title.ilike(f"%{clean_q}%"),
        Task.description.ilike(f"%{clean_q}%"),
        Task.execution_summary.ilike(f"%{clean_q}%"),
        Task.validation_summary.ilike(f"%{clean_q}%"),
        Task.id.ilike(f"%{clean_q}%"),
        Task.task_type.ilike(f"%{clean_q}%"),
        Task.status.ilike(f"%{clean_q}%"),
        Repository.name.ilike(f"%{clean_q}%"),
        Repository.slug.ilike(f"%{clean_q}%"),
    ]

    task_rows = (
        db.query(Task, Repository.name.label("repo_name"))
        .join(Repository, Repository.id == Task.repository_id)
        .filter(
            Repository.deleted_at.is_(None),
            repo_access_filter(Repository),
            or_(*task_filters),
        )
        .order_by(*task_order)
        .limit(10)
        .all()
    )
    for task, repo_name in task_rows:
        task_type_str = task.task_type.capitalize() if task.task_type else "Task"
        results.append({
            "type": "task",
            "name": task.title,
            "description": f"{task_type_str} · {task.status} in {repo_name}",
            "url": f"/tasks/{task.id}",
        })

    # 5. Search pull requests (strictly scoped to accessible repositories, user's repos prioritized)
    pr_order = []
    if current_user:
        pr_order.append(case((Repository.owner_id == current_user.id, 1), else_=2))
    pr_order.extend([
        case((PullRequest.status == "open", 1), (PullRequest.status == "approved", 2), else_=3),
        PullRequest.updated_at.desc(),
    ])

    pr_filters = [
        PullRequest.title.ilike(f"%{clean_q}%"),
        PullRequest.description.ilike(f"%{clean_q}%"),
        PullRequest.target_branch.ilike(f"%{clean_q}%"),
        PullRequest.status.ilike(f"%{clean_q}%"),
        Repository.name.ilike(f"%{clean_q}%"),
        Repository.slug.ilike(f"%{clean_q}%"),
    ]
    if clean_num:
        pr_filters.extend([
            PullRequest.title.ilike(f"%#{clean_num}%"),
            PullRequest.title.ilike(f"%PR {clean_num}%"),
            PullRequest.title.ilike(f"%PR #{clean_num}%"),
        ])

    pr_rows = (
        db.query(PullRequest, Repository.name.label("repo_name"))
        .join(Repository, Repository.id == PullRequest.repository_id)
        .filter(
            Repository.deleted_at.is_(None),
            repo_access_filter(Repository),
            or_(*pr_filters),
        )
        .order_by(*pr_order)
        .limit(10)
        .all()
    )
    for pr, repo_name in pr_rows:
        results.append({
            "type": "pull_request",
            "name": pr.title,
            "description": f"PR · {pr.status} in {repo_name}",
            "url": f"/repositories/{urllib.parse.quote(repo_name)}/pull-requests/{pr.id}",
        })

    # 6. Search issues (strictly scoped to accessible repositories, user's repos prioritized)
    issue_order = []
    if current_user:
        issue_order.append(case((Repository.owner_id == current_user.id, 1), else_=2))
    issue_order.extend([
        case((Issue.status == "open", 1), else_=2),
        Issue.updated_at.desc(),
    ])

    issue_filters = [
        Issue.title.ilike(f"%{clean_q}%"),
        Issue.body.ilike(f"%{clean_q}%"),
        Issue.status.ilike(f"%{clean_q}%"),
        Issue.github_author_login.ilike(f"%{clean_q}%"),
        Repository.name.ilike(f"%{clean_q}%"),
        Repository.slug.ilike(f"%{clean_q}%"),
    ]
    if clean_num:
        issue_filters.append(Issue.github_issue_number == int(clean_num))

    issue_rows = (
        db.query(Issue, Repository.name.label("repo_name"))
        .join(Repository, Repository.id == Issue.repository_id)
        .filter(
            Repository.deleted_at.is_(None),
            repo_access_filter(Repository),
            or_(*issue_filters),
        )
        .order_by(*issue_order)
        .limit(10)
        .all()
    )
    for issue, repo_name in issue_rows:
        issue_ref = f"#{issue.github_issue_number}" if issue.github_issue_number else f"Issue {issue.id[:8]}"
        results.append({
            "type": "issue",
            "name": f"{issue_ref}: {issue.title}",
            "description": f"{issue.status.capitalize()} issue by {issue.github_author_login or 'author'} in {repo_name}",
            "url": f"/repositories/{urllib.parse.quote(repo_name)}/issues/{issue.github_issue_number or issue.id}",
        })

    # 7. Search changes (strictly scoped to accessible repositories, user's repos prioritized)
    change_order = []
    if current_user:
        change_order.append(case((Repository.owner_id == current_user.id, 1), else_=2))
    change_order.append(Change.updated_at.desc())

    change_filters = [
        Change.intent.ilike(f"%{clean_q}%"),
        Change.id.ilike(f"%{clean_q}%"),
        Change.status.ilike(f"%{clean_q}%"),
        Repository.name.ilike(f"%{clean_q}%"),
        Repository.slug.ilike(f"%{clean_q}%"),
    ]

    change_rows = (
        db.query(Change, Repository.name.label("repo_name"))
        .join(Repository, Repository.id == Change.repository_id)
        .filter(
            Repository.deleted_at.is_(None),
            repo_access_filter(Repository),
            or_(*change_filters),
        )
        .order_by(*change_order)
        .limit(10)
        .all()
    )
    for change, repo_name in change_rows:
        intent_summary = change.intent.splitlines()[0] if change.intent else f"Change {change.id[:8]}"
        results.append({
            "type": "change",
            "name": intent_summary,
            "description": f"Change {change.id[:8]} · {change.status} in {repo_name}",
            "url": f"/repositories/{urllib.parse.quote(repo_name)}/changes/{change.id}",
        })

    return results
