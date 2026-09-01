from app.core.config import settings
import json
import urllib.request
import urllib.error
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.assistant_thread import AssistantThread
from app.models.assistant_message import AssistantMessage
from app.models.repository import Repository
from app.models.user import User

router = APIRouter(tags=["assistant"])


class ThreadCreate(BaseModel):
    title: str = "New Conversation"


class ThreadResponse(BaseModel):
    id: str
    repository_id: str
    user_id: str
    title: str

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str

    class Config:
        from_attributes = True


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

    thread = AssistantThread(
        repository_id=repository.id,
        user_id=current_user.id,
        title=thread_in.title,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)

    return thread


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

    return list(threads)


def _build_repo_system_prompt(thread: AssistantThread, db: Session) -> str:
    """
    Build a rich system prompt injecting live repository context —
    name, description, recent changes, KG entities, and open tasks —
    so the AI assistant has real knowledge of the specific repo.
    """
    repo = db.scalar(select(Repository).where(Repository.id == thread.repository_id))
    if not repo:
        return "You are a helpful AI assistant for a software repository."

    owner = db.scalar(select(User).where(User.id == repo.owner_id))
    owner_name = owner.username if owner else "unknown"

    # Gather recent changes
    try:
        from app.models.change import Change
        recent_changes = db.scalars(
            select(Change)
            .where(Change.repository_id == repo.id)
            .order_by(Change.created_at.desc())
            .limit(5)
        ).all()
        changes_text = "\n".join(
            f"  - [{c.status}] {c.intent[:120]}" for c in recent_changes
        ) if recent_changes else "  None yet."
    except Exception:
        changes_text = "  Unable to retrieve."

    # Gather KG nodes
    try:
        from app.models.knowledge_node import KnowledgeNode
        kg_nodes = db.scalars(
            select(KnowledgeNode)
            .where(KnowledgeNode.repository_id == repo.id)
            .limit(20)
        ).all()
        kg_text = ", ".join(
            f"{n.name} ({n.entity_type})" for n in kg_nodes
        ) if kg_nodes else "  No entities indexed yet."
    except Exception:
        kg_text = "  Unable to retrieve."

    # Gather open tasks
    try:
        from app.models.task import Task
        open_tasks = db.scalars(
            select(Task)
            .where(Task.repository_id == repo.id, Task.status.in_(["pending", "in_progress"]))
            .limit(5)
        ).all()
        tasks_text = "\n".join(
            f"  - [{t.status}] {t.title}" for t in open_tasks
        ) if open_tasks else "  No open tasks."
    except Exception:
        tasks_text = "  Unable to retrieve."

    return f"""You are an AI assistant embedded in SUTRA, an AI-native software development platform.
You have full, live knowledge of the following repository. Always answer questions specifically about this repo.

=== REPOSITORY CONTEXT ===
Name: {repo.name}
Owner: {owner_name}
Description: {repo.description or 'No description provided.'}
Visibility: {repo.visibility}
Default Branch: {getattr(repo, 'default_branch', 'master')}

=== RECENT CHANGES ===
{changes_text}

=== CODE ENTITIES (Knowledge Graph) ===
{kg_text}

=== OPEN TASKS ===
{tasks_text}
=========================

You are a knowledgeable, concise technical assistant. Answer questions about this specific repository.
If the user asks about unrelated topics, gently redirect to repository-related discussions.
Format code with markdown code blocks when appropriate.
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

    # Save user message
    user_msg = AssistantMessage(
        thread_id=thread.id,
        role=AssistantMessage.ROLE_USER,
        content=message_in.content,
    )
    db.add(user_msg)
    db.commit()

    # Fetch all previous messages for context
    history = db.scalars(
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread.id)
        .order_by(AssistantMessage.created_at.asc())
    ).all()

    # Build system prompt with real, live repo context
    system_prompt = _build_repo_system_prompt(thread, db)

    # Format for Ollama: system message first, then conversation history
    ollama_messages = [{"role": "system", "content": system_prompt}]
    ollama_messages += [{"role": msg.role, "content": msg.content} for msg in history]

    groq_url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "openai/gpt-oss-20b",
        "messages": ollama_messages,
        "stream": False
    }

    try:
        req = urllib.request.Request(
            groq_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.groq_api_key}",
                "User-Agent": "SUTRA-Assistant"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            ai_content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "Error: No content in response")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        ai_content = f"[Groq HTTP Error {e.code}] {body}"
    except Exception as e:
        ai_content = f"[Groq Connection Error] {str(e)}"

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
