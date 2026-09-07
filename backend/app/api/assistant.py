from app.core.config import settings
import json
import re
import urllib.request
import urllib.error
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.assistant_thread import AssistantThread
from app.models.assistant_message import AssistantMessage
from app.models.repository import Repository
from app.models.user import User
from app.models.task import Task
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.ci_job import CIJob
from app.models.agent import Agent
from app.models.knowledge_node import KnowledgeNode
from app.services.code_provenance_service import CodeProvenanceService
from app.services.governance_service import GovernanceService

router = APIRouter(tags=["assistant"])


class ThreadCreate(BaseModel):
    title: str = "New Conversation"
    task_id: Optional[str] = None


class ThreadResponse(BaseModel):
    id: str
    repository_id: str
    user_id: str
    title: str
    task_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str

    model_config = ConfigDict(from_attributes=True)


def _extract_task_id(title: str) -> tuple[Optional[str], str]:
    if title.startswith("[Task:"):
        match = re.match(r"^\[Task:\s*([a-f0-9\-]+)\]\s*(.*)$", title)
        if match:
            return match.group(1).strip(), match.group(2).strip() or "Task Conversation"
    return None, title


def _format_thread(thread: AssistantThread) -> ThreadResponse:
    task_id, clean_title = _extract_task_id(thread.title)
    return ThreadResponse(
        id=thread.id,
        repository_id=thread.repository_id,
        user_id=thread.user_id,
        title=clean_title,
        task_id=task_id,
    )


@router.post(
    "/v1/repositories/{owner}/{repo}/assistant/threads",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_thread(
    owner: str,
    repo: str,
    thread_in: ThreadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repository = db.scalar(
        select(Repository)
        .join(User, Repository.owner_id == User.id)
        .where(User.username == owner, Repository.name == repo)
    )
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repository.visibility != "public" and repository.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    raw_title = thread_in.title
    if thread_in.task_id:
        raw_title = f"[Task: {thread_in.task_id}] {thread_in.title}"

    thread = AssistantThread(
        repository_id=repository.id,
        user_id=current_user.id,
        title=raw_title,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)

    return _format_thread(thread)


@router.get(
    "/v1/repositories/{owner}/{repo}/assistant/threads",
    response_model=List[ThreadResponse],
)
def list_threads(
    owner: str,
    repo: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repository = db.scalar(
        select(Repository)
        .join(User, Repository.owner_id == User.id)
        .where(User.username == owner, Repository.name == repo)
    )
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")

    threads = db.scalars(
        select(AssistantThread)
        .where(
            AssistantThread.repository_id == repository.id,
            AssistantThread.user_id == current_user.id,
        )
        .order_by(AssistantThread.created_at.desc())
    ).all()

    return [_format_thread(t) for t in threads]


# ===========================================================================
# Structured Engineering Context Tools
# ===========================================================================

def tool_get_task(db: Session, repo_id: str, task_id: str) -> Optional[dict]:
    t = db.scalar(select(Task).where(Task.id == task_id, Task.repository_id == repo_id))
    if not t:
        return None
    agent = db.scalar(select(Agent).where(Agent.id == t.assigned_agent_id)) if t.assigned_agent_id else None
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "assigned_agent": agent.name if agent else None,
        "assigned_agent_id": t.assigned_agent_id,
        "resulting_change_id": t.resulting_change_id,
        "resulting_pull_request_id": t.resulting_pull_request_id,
    }


def tool_get_change(db: Session, repo_id: str, change_id: str) -> Optional[dict]:
    c = db.scalar(select(Change).where(Change.id == change_id, Change.repository_id == repo_id))
    if not c:
        return None
    return {
        "id": c.id,
        "status": c.status,
        "intent": c.intent,
        "branch": c.branch,
        "resulting_commit": c.resulting_commit,
        "metadata": json.loads(c.metadata_json or "{}"),
    }


def tool_get_pr(db: Session, repo_id: str, pr_id_or_number: str) -> Optional[dict]:
    stmt = select(PullRequest).where(PullRequest.repository_id == repo_id)
    if pr_id_or_number.isdigit():
        stmt = stmt.where(PullRequest.github_pr_number == int(pr_id_or_number))
    else:
        stmt = stmt.where(PullRequest.id == pr_id_or_number)
    pr = db.scalar(stmt)
    if not pr:
        return None
    return {
        "id": pr.id,
        "number": pr.github_pr_number,
        "title": pr.title,
        "status": pr.status,
        "source_branch": pr.source_branch,
        "target_branch": pr.target_branch,
        "source_commit": pr.source_commit,
        "target_commit": pr.target_commit,
    }


def tool_get_checks(db: Session, pr_id: str) -> list[dict]:
    jobs = db.scalars(select(CIJob).where(CIJob.pull_request_id == pr_id)).all()
    return [{"id": j.id, "status": j.status, "trigger": j.trigger, "commit_sha": j.commit_sha} for j in jobs]


def tool_get_governance(db: Session, pr_id: str) -> dict:
    try:
        gov = GovernanceService(db).evaluate_pull_request(pr_id)
        return {
            "verdict": gov.get("verdict"),
            "is_mergeable": gov.get("is_mergeable"),
            "blocking_reasons": gov.get("blocking_reasons", []),
            "required_approvals": gov.get("required_approvals"),
            "approval_count": len(gov.get("approvals", [])),
        }
    except Exception as e:
        return {"error": str(e)}


def tool_get_provenance(db: Session, repo_id: str, commit_sha: str) -> dict:
    try:
        return CodeProvenanceService(db).resolve_commit(repo_id, commit_sha)
    except Exception as e:
        return {"error": str(e)}


def tool_search_knowledge_graph(db: Session, repo_id: str, query: str) -> list[dict]:
    search_term = f"%{query}%"
    nodes = db.scalars(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.repository_id == repo_id,
            KnowledgeNode.name.ilike(search_term) | KnowledgeNode.summary.ilike(search_term),
        )
        .limit(10)
    ).all()
    return [{"name": n.name, "type": n.entity_type, "summary": n.summary} for n in nodes]


# ===========================================================================
# Engineering Context Builder & Deterministic Synthesizer
# ===========================================================================

def _synthesize_deterministic_response(
    query: str,
    repo: Repository,
    task_info: Optional[dict],
    recent_changes: list[Change],
    open_tasks: list[Task],
    latest_pr: Optional[PullRequest],
    db: Session,
) -> str:
    q = query.lower()

    # Query: Task status or what task produced this
    if "task" in q:
        if task_info:
            return (
                f"### Task #{task_info['id'][:8]}: {task_info['title']}\n\n"
                f"- **Status**: `{task_info['status']}`\n"
                f"- **Assigned Agent**: {task_info['assigned_agent'] or 'None'}\n"
                f"- **Description**: {task_info['description'] or 'No description'}\n"
                f"- **Resulting Change**: `{task_info['resulting_change_id'] or 'None'}`\n"
                f"- **Resulting PR**: `{task_info['resulting_pull_request_id'] or 'None'}`\n\n"
                f"This task is being executed under SUTRA autonomous control-plane governance."
            )
        elif open_tasks:
            lines = [f"- **Task #{t.id[:8]}**: {t.title} (`{t.status}`)" for t in open_tasks[:5]]
            return f"### Active Tasks in {repo.name}\n\n" + "\n".join(lines)
        return f"There are currently no active tasks recorded for repository **{repo.name}**."

    # Query: PR status, blockage, or ready for approval
    if "pr" in q or "pull request" in q or "merge" in q or "block" in q or "approval" in q:
        pr = latest_pr
        if pr:
            gov = tool_get_governance(db, pr.id)
            checks = tool_get_checks(db, pr.id)
            checks_status = ", ".join([f"{c['trigger']}: {c['status']}" for c in checks]) if checks else "No checks recorded"
            blocking = ", ".join(gov.get("blocking_reasons", [])) or "None (Ready for merge)"
            return (
                f"### Pull Request #{pr.github_pr_number or pr.id[:8]}: {pr.title or 'PR'}\n\n"
                f"- **PR Status**: `{pr.status}`\n"
                f"- **Branches**: `{pr.source_branch}` → `{pr.target_branch}`\n"
                f"- **HEAD Commit**: `{pr.source_commit[:8] if pr.source_commit else 'None'}`\n"
                f"- **Governance Verdict**: `{gov.get('verdict')}`\n"
                f"- **CI Checks**: {checks_status}\n"
                f"- **Blocking Conditions**: {blocking}\n\n"
                f"Under SUTRA governance, a PR cannot merge unless CI passes, governance reaches `READY_FOR_MERGE`, "
                f"and an authorized human operator approves and executes the governed merge."
            )
        return f"No active pull requests found in repository **{repo.name}**."

    # Query: CI / checks
    if "ci" in q or "check" in q:
        if latest_pr:
            checks = tool_get_checks(db, latest_pr.id)
            if checks:
                lines = [f"- `{c['trigger']}`: **{c['status']}** (commit: `{c['commit_sha'][:8]}`)" for c in checks]
                return f"### CI Checks for PR #{latest_pr.github_pr_number or latest_pr.id[:8]}\n\n" + "\n".join(lines)
            return f"No CI checks have executed yet for PR #{latest_pr.github_pr_number or latest_pr.id[:8]}."
        return "No recent Pull Request found to inspect CI checks."

    # Query: What changed / commit / provenance
    if "change" in q or "diff" in q or "commit" in q or "who" in q or "agent" in q:
        if recent_changes:
            lines = []
            for c in recent_changes[:4]:
                prov = tool_get_provenance(db, repo.id, c.resulting_commit) if c.resulting_commit else {}
                author = prov.get("agent_name") or prov.get("human_name") or "Autonomous Agent"
                lines.append(f"- **Change #{c.id[:8]}** (`{c.status}`): {c.intent}\n  - Produced by: `{author}`\n  - Resulting commit: `{c.resulting_commit[:8] if c.resulting_commit else 'in-progress'}`")
            return f"### Recent Changes in {repo.name}\n\n" + "\n".join(lines)
        return f"No changes recorded yet in repository **{repo.name}**."

    # Default overview
    task_summary = f"Scoped to Task #{task_info['id'][:8]} ({task_info['status']})" if task_info else f"{len(open_tasks)} active task(s)"
    change_count = len(recent_changes)
    pr_num = getattr(latest_pr, "github_pr_number", None) or (latest_pr.id[:8] if latest_pr else "")
    pr_summary = f"#{pr_num} (`{latest_pr.status}`)" if latest_pr else "None"
    return (
        f"### SUTRA Engineering Assistant — {repo.name}\n\n"
        f"I am connected to the **{repo.name}** control plane. Here is current repository state:\n\n"
        f"- **Tasks**: {task_summary}\n"
        f"- **Recent Changes**: {change_count} recorded\n"
        f"- **Latest PR**: {pr_summary}\n\n"
        f"You can ask me questions such as:\n"
        f"- *'What changed in the last change?'*\n"
        f"- *'Why is this PR blocked?'*\n"
        f"- *'Which agent produced this commit?'*\n"
        f"- *'What are the CI check results?'*"
    )


def _build_repo_system_prompt(thread: AssistantThread, db: Session) -> str:
    repo = db.scalar(select(Repository).where(Repository.id == thread.repository_id))
    if not repo:
        return "You are a helpful AI assistant for a software repository."

    owner = db.scalar(select(User).where(User.id == repo.owner_id))
    owner_name = owner.username if owner else "unknown"

    task_id, _ = _extract_task_id(thread.title)
    task_context = ""
    if task_id:
        t_data = tool_get_task(db, repo.id, task_id)
        if t_data:
            task_context = f"\n=== SCOPED TASK CONTEXT ===\nTask ID: {t_data['id']}\nTitle: {t_data['title']}\nStatus: {t_data['status']}\nAgent: {t_data['assigned_agent']}\n"

    try:
        recent_changes = db.scalars(
            select(Change).where(Change.repository_id == repo.id).order_by(Change.created_at.desc()).limit(5)
        ).all()
        changes_text = "\n".join(f"  - [{c.status}] {c.intent[:120]}" for c in recent_changes) if recent_changes else "  None yet."
    except Exception:
        changes_text = "  Unable to retrieve."

    try:
        kg_nodes = db.scalars(
            select(KnowledgeNode).where(KnowledgeNode.repository_id == repo.id).limit(20)
        ).all()
        kg_text = ", ".join(f"{n.name} ({n.entity_type})" for n in kg_nodes) if kg_nodes else "  No entities indexed yet."
    except Exception:
        kg_text = "  Unable to retrieve."

    try:
        open_tasks = db.scalars(
            select(Task).where(Task.repository_id == repo.id, Task.status.in_(["pending", "in_progress"])).limit(5)
        ).all()
        tasks_text = "\n".join(f"  - [{t.status}] {t.title}" for t in open_tasks) if open_tasks else "  No open tasks."
    except Exception:
        tasks_text = "  Unable to retrieve."

    return f"""You are an AI assistant embedded in SUTRA, an AI-native software development platform.
You have full, live knowledge of the following repository. Always answer questions specifically about this repo.

=== REPOSITORY CONTEXT ===
Name: {repo.name}
Owner: {owner_name}
Description: {repo.description or 'No description provided.'}
Visibility: {repo.visibility}
Default Branch: {getattr(repo, 'default_branch', 'main')}{task_context}

=== RECENT CHANGES ===
{changes_text}

=== CODE ENTITIES (Knowledge Graph) ===
{kg_text}

=== OPEN TASKS ===
{tasks_text}
=========================

You are a knowledgeable, concise technical assistant. Answer questions about this specific repository and its engineering lifecycle.
"""


@router.post(
    "/v1/assistant/threads/{thread_id}/messages",
    response_model=List[MessageResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    thread_id: str,
    message_in: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = db.scalar(
        select(AssistantThread).where(
            AssistantThread.id == thread_id, AssistantThread.user_id == current_user.id
        )
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    repo = db.scalar(select(Repository).where(Repository.id == thread.repository_id))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Save user message
    user_msg = AssistantMessage(
        thread_id=thread.id,
        role=AssistantMessage.ROLE_USER,
        content=message_in.content,
    )
    db.add(user_msg)
    db.commit()

    # Load factual entities for structured synthesis
    task_id, _ = _extract_task_id(thread.title)
    task_info = tool_get_task(db, repo.id, task_id) if task_id else None
    recent_changes = list(db.scalars(
        select(Change).where(Change.repository_id == repo.id).order_by(Change.created_at.desc()).limit(5)
    ).all())
    open_tasks = list(db.scalars(
        select(Task).where(Task.repository_id == repo.id, Task.status.in_(["pending", "in_progress"])).limit(5)
    ).all())
    latest_pr = db.scalar(
        select(PullRequest).where(PullRequest.repository_id == repo.id).order_by(PullRequest.created_at.desc())
    )

    ai_content = None

    # Attempt Groq LLM API if key is configured
    if settings.groq_api_key and settings.groq_api_key.strip():
        system_prompt = _build_repo_system_prompt(thread, db)
        history = db.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.thread_id == thread.id)
            .order_by(AssistantMessage.created_at.asc())
        ).all()

        ollama_messages = [{"role": "system", "content": system_prompt}]
        ollama_messages += [{"role": msg.role, "content": msg.content} for msg in history]

        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "openai/gpt-oss-20b",
            "messages": ollama_messages,
            "stream": False,
        }

        try:
            req = urllib.request.Request(
                groq_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "User-Agent": "SUTRA-Assistant",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                content = response_data.get("choices", [{}])[0].get("message", {}).get("content")
                if content and not content.startswith("Error:"):
                    ai_content = content
        except Exception:
            ai_content = None

    # If Groq is unconfigured or failed, synthesize factual answer deterministically
    if not ai_content:
        ai_content = _synthesize_deterministic_response(
            query=message_in.content,
            repo=repo,
            task_info=task_info,
            recent_changes=recent_changes,
            open_tasks=open_tasks,
            latest_pr=latest_pr,
            db=db,
        )

    # Save AI response
    ai_msg = AssistantMessage(
        thread_id=thread.id,
        role=AssistantMessage.ROLE_ASSISTANT,
        content=ai_content,
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(user_msg)
    db.refresh(ai_msg)

    return [user_msg, ai_msg]


@router.get(
    "/v1/assistant/threads/{thread_id}/messages",
    response_model=List[MessageResponse],
)
def list_messages(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = db.scalar(
        select(AssistantThread).where(
            AssistantThread.id == thread_id, AssistantThread.user_id == current_user.id
        )
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread.id)
        .order_by(AssistantMessage.created_at.asc())
    ).all()

    return list(messages)

