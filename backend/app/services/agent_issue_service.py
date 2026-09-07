from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.issue import Issue
from app.models.repository import Repository
from app.models.task import Task

from app.providers.github.repository import GitHubRepositoryProvider


class AgentIssueService:
    """
    Creates GitHub-backed issues on behalf of an authenticated SUTRA agent.

    GitHub is the source of truth for the issue.
    SUTRA stores the provenance chain:

        Agent
          ↓
        AgentSession
          ↓
        Task
          ↓
        Issue
          ↓
        GitHub Issue
    """

    def __init__(
        self,
        db: Session,
        provider: GitHubRepositoryProvider,
    ):
        self.db = db
        self.provider = provider

    def create_issue(
        self,
        *,
        session: AgentSession,
        task: Task,
        title: str,
        body: str,
    ) -> Issue:
        # ---------------------------------------------------------
        # 1. Validate session → agent
        # ---------------------------------------------------------

        agent = self.db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )

        if agent is None:
            raise PermissionError(
                "Agent session does not belong to an active agent"
            )

        # ---------------------------------------------------------
        # 2. Validate task ownership
        # ---------------------------------------------------------

        if task.assigned_agent_id != agent.id:
            raise PermissionError(
                "Agent is not assigned to this task"
            )

        # ---------------------------------------------------------
        # 3. Validate session owns the task lease
        # ---------------------------------------------------------

        if task.claimed_by_session_id != session.id:
            raise PermissionError(
                "Agent session does not hold the task lease"
            )

        # ---------------------------------------------------------
        # 4. Validate task repository
        # ---------------------------------------------------------

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == task.repository_id,
            )
        )

        if repository is None:
            raise ValueError(
                "Task repository not found"
            )

        if repository.provider_type != "github":
            raise ValueError(
                "Agent Issues are currently supported "
                "only for GitHub repositories"
            )

        if not repository.provider_owner:
            raise ValueError(
                "GitHub repository owner metadata is missing"
            )

        # ---------------------------------------------------------
        # 5. Create GitHub issue
        # ---------------------------------------------------------

        github_issue = self.provider.create_issue(
            owner=repository.provider_owner,
            name=repository.name,
            title=self._build_title(
                agent=agent,
                title=title,
            ),
            body=self._build_body(
                agent=agent,
                session=session,
                task=task,
                body=body,
            ),
        )

        # ---------------------------------------------------------
        # 6. Create SUTRA provenance/linkage record
        # ---------------------------------------------------------

        issue = Issue(
            repository_id=repository.id,
            github_issue_id=str(github_issue.id),
            github_issue_number=github_issue.number,
            github_html_url=github_issue.html_url,

            source_type="agent",

            author_id=agent.id,

            agent_id=agent.id,
            agent_session_id=session.id,
            task_id=task.id,

            title=github_issue.title,
            body=github_issue.body or "",
            status=github_issue.state,

            github_author_login=github_issue.author_login,

            created_at=github_issue.created_at,
            updated_at=github_issue.updated_at,
            closed_at=github_issue.closed_at,
        )

        self.db.add(issue)
        self.db.flush()

        return issue

    @staticmethod
    def _build_title(
        *,
        agent: Agent,
        title: str,
    ) -> str:
        clean_title = title.strip()

        if not clean_title:
            raise ValueError(
                "Issue title cannot be empty"
            )

        # Keep the registered SUTRA agent identity visible
        # directly in GitHub.
        return f"[Agent: {agent.name}] {clean_title}"

    @staticmethod
    def _build_body(
        *,
        agent: Agent,
        session: AgentSession,
        task: Task,
        body: str,
    ) -> str:
        clean_body = body.strip()

        if not clean_body:
            raise ValueError(
                "Issue body cannot be empty"
            )

        return (
            f"## SUTRA Agent Issue\n\n"
            f"**Agent:** {agent.name}\n"
            f"**Agent ID:** `{agent.id}`\n"
            f"**Session ID:** `{session.id}`\n"
            f"**Task ID:** `{task.id}`\n"
            f"**Task:** {task.title}\n\n"
            f"### Details\n\n"
            f"{clean_body}\n"
        )