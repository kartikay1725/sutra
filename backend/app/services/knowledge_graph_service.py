from datetime import datetime, timezone
import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.knowledge_node import KnowledgeNode
from app.models.knowledge_edge import KnowledgeEdge
from app.models.repository import Repository


def upsert_node(
    db: Session,
    repository_id: str,
    entity_type: str,
    name: str,
    summary: str | None = None,
    content_hash: str | None = None,
    metadata: dict | None = None,
) -> KnowledgeNode:
    """
    Creates or updates a knowledge node based on repository_id, entity_type, and name.
    """
    node = db.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.repository_id == repository_id,
            KnowledgeNode.entity_type == entity_type,
            KnowledgeNode.name == name,
        )
    )

    if not node:
        node = KnowledgeNode(
            repository_id=repository_id,
            entity_type=entity_type,
            name=name,
        )
        db.add(node)

    if summary is not None:
        node.summary = summary
    if content_hash is not None:
        node.content_hash = content_hash
    if metadata is not None:
        node.metadata_json = json.dumps(metadata)

    node.updated_at = datetime.now(timezone.utc)
    
    # We commit in the router/handler, or we flush here
    db.flush()
    return node


def add_edge(
    db: Session,
    source_node_id: str,
    target_node_id: str,
    relationship_type: str,
) -> KnowledgeEdge:
    """
    Creates an edge if it doesn't exist.
    """
    edge = db.scalar(
        select(KnowledgeEdge).where(
            KnowledgeEdge.source_node_id == source_node_id,
            KnowledgeEdge.target_node_id == target_node_id,
            KnowledgeEdge.relationship_type == relationship_type,
        )
    )

    if not edge:
        edge = KnowledgeEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_type=relationship_type,
        )
        db.add(edge)
        db.flush()

    return edge


def search_nodes(
    db: Session,
    repository_id: str,
    query: str,
    limit: int = 20,
) -> list[KnowledgeNode]:
    """
    Basic ILIKE search across node names and summaries.
    """
    search_term = f"%{query}%"
    nodes = db.scalars(
        select(KnowledgeNode).where(
            KnowledgeNode.repository_id == repository_id,
            or_(
                KnowledgeNode.name.ilike(search_term),
                KnowledgeNode.summary.ilike(search_term),
            )
        ).limit(limit)
    ).all()
    return list(nodes)


def get_subgraph(
    db: Session,
    node_id: str,
) -> dict:
    """
    Retrieves a node and its immediate incoming/outgoing edges and neighbors.
    """
    node = db.scalar(
        select(KnowledgeNode).where(KnowledgeNode.id == node_id)
    )
    if not node:
        return None

    # Load edges (we could use joinedload in the query, but this is simple enough for depth=1)
    outgoing_edges = db.scalars(
        select(KnowledgeEdge).where(KnowledgeEdge.source_node_id == node_id)
    ).all()
    
    incoming_edges = db.scalars(
        select(KnowledgeEdge).where(KnowledgeEdge.target_node_id == node_id)
    ).all()
    
    neighbor_ids = {e.target_node_id for e in outgoing_edges} | {e.source_node_id for e in incoming_edges}
    
    if neighbor_ids:
        neighbors = db.scalars(
            select(KnowledgeNode).where(KnowledgeNode.id.in_(neighbor_ids))
        ).all()
    else:
        neighbors = []
        
    return {
        "node": node,
        "outgoing_edges": outgoing_edges,
        "incoming_edges": incoming_edges,
        "neighbors": {n.id: n for n in neighbors},
    }


def index_repository_files(
    db: Session,
    repository: Repository,
    commit_sha: str = "HEAD",
) -> int:
    """
    Scans repository tree at commit_sha and indexes files and functions into KnowledgeNode/KnowledgeEdge.
    """
    import subprocess
    import ast
    from pathlib import Path
    from app.core.config import settings

    repo_path = Path(settings.repository_storage_path).resolve() / repository.storage_key
    if not repo_path.exists():
        return 0

    try:
        res = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", commit_sha],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return 0

        file_paths = [p.strip() for p in res.stdout.splitlines() if p.strip()]
        indexed_count = 0
        for path in file_paths:
            file_node = upsert_node(
                db=db,
                repository_id=repository.id,
                entity_type="file",
                name=path,
                summary=f"File {path} in repository {repository.name}",
                metadata={"path": path, "commit_sha": commit_sha},
            )
            indexed_count += 1

            if path.endswith(".py"):
                try:
                    content_res = subprocess.run(
                        ["git", "show", f"{commit_sha}:{path}"],
                        cwd=str(repo_path),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if content_res.returncode == 0:
                        parsed = ast.parse(content_res.stdout)
                        for item in parsed.body:
                            if isinstance(item, ast.FunctionDef):
                                func_node = upsert_node(
                                    db=db,
                                    repository_id=repository.id,
                                    entity_type="function",
                                    name=f"{path}:{item.name}",
                                    summary=f"Function {item.name}() in {path}",
                                    metadata={"file": path, "function": item.name, "line": item.lineno},
                                )
                                add_edge(
                                    db=db,
                                    source_node_id=file_node.id,
                                    target_node_id=func_node.id,
                                    relationship_type="defines",
                                )
                                indexed_count += 1
                            elif isinstance(item, ast.ClassDef):
                                class_node = upsert_node(
                                    db=db,
                                    repository_id=repository.id,
                                    entity_type="class",
                                    name=f"{path}:{item.name}",
                                    summary=f"Class {item.name} in {path}",
                                    metadata={"file": path, "class": item.name, "line": item.lineno},
                                )
                                add_edge(
                                    db=db,
                                    source_node_id=file_node.id,
                                    target_node_id=class_node.id,
                                    relationship_type="defines",
                                )
                                indexed_count += 1
                except Exception:
                    pass

        db.flush()
        return indexed_count
    except Exception:
        return 0


def index_engineering_lifecycle(
    db: Session,
    repository: Repository | str,
) -> dict[str, int]:
    """
    Ingests and interlinks authoritative SUTRA engineering lifecycle entities:
    Task -> Agent -> Change -> Commit -> PullRequest -> Discussion.
    """
    from app.models.task import Task
    from app.models.change import Change
    from app.models.pull_request import PullRequest
    from app.models.agent import Agent
    from app.models.discussion import Discussion

    repo_id = repository.id if hasattr(repository, "id") else str(repository)
    node_count = 0
    edge_count = 0

    # 1. Tasks & Agents
    tasks = db.scalars(
        select(Task).where(Task.repository_id == repo_id)
    ).all()

    for t in tasks:
        task_node = upsert_node(
            db=db,
            repository_id=repo_id,
            entity_type="task",
            name=f"Task #{t.id[:8]}: {t.title}",
            summary=t.description or f"Task in status {t.status}",
            metadata={"task_id": t.id, "status": t.status, "priority": t.priority},
        )
        node_count += 1

        if t.assigned_agent_id:
            agent = db.scalar(select(Agent).where(Agent.id == t.assigned_agent_id))
            if agent:
                agent_node = upsert_node(
                    db=db,
                    repository_id=repo_id,
                    entity_type="agent",
                    name=f"Agent: {agent.name}",
                    summary=agent.description or "Autonomous SUTRA Agent",
                    metadata={"agent_id": agent.id},
                )
                node_count += 1
                add_edge(
                    db=db,
                    source_node_id=task_node.id,
                    target_node_id=agent_node.id,
                    relationship_type="assigned_to",
                )
                edge_count += 1

        # 2. Resulting Change
        if t.resulting_change_id:
            change = db.scalar(select(Change).where(Change.id == t.resulting_change_id))
            if change:
                files = []
                try:
                    meta = json.loads(change.metadata_json or "{}")
                    files = meta.get("files", [])
                except Exception:
                    pass

                change_node = upsert_node(
                    db=db,
                    repository_id=repo_id,
                    entity_type="change",
                    name=f"Change #{change.id[:8]}",
                    summary=change.intent,
                    metadata={"change_id": change.id, "status": change.status, "files": files},
                )
                node_count += 1
                add_edge(
                    db=db,
                    source_node_id=task_node.id,
                    target_node_id=change_node.id,
                    relationship_type="produced",
                )
                edge_count += 1

                # 3. Code files touched
                for f in files:
                    file_node = upsert_node(
                        db=db,
                        repository_id=repo_id,
                        entity_type="file",
                        name=f,
                        summary=f"Repository file: {f}",
                    )
                    node_count += 1
                    add_edge(
                        db=db,
                        source_node_id=change_node.id,
                        target_node_id=file_node.id,
                        relationship_type="modifies",
                    )
                    edge_count += 1

        # 4. Resulting PR linked from task
        if t.resulting_pull_request_id:
            pr = db.scalar(select(PullRequest).where(PullRequest.id == t.resulting_pull_request_id))
            if pr:
                pr_node = upsert_node(
                    db=db,
                    repository_id=repo_id,
                    entity_type="pull_request",
                    name=f"PR #{pr.id[:8]}: {pr.title or 'Pull Request'}",
                    summary=f"Pull Request in status {pr.status}",
                    metadata={"pull_request_id": pr.id, "status": pr.status},
                )
                node_count += 1
                add_edge(
                    db=db,
                    source_node_id=task_node.id,
                    target_node_id=pr_node.id,
                    relationship_type="reviewed_in",
                )
                edge_count += 1

    # 4b. All PullRequests in repository (including GitHub-created PRs)
    all_prs = db.scalars(
        select(PullRequest).where(PullRequest.repository_id == repo_id)
    ).all()
    for pr in all_prs:
        pr_node = upsert_node(
            db=db,
            repository_id=repo_id,
            entity_type="pull_request",
            name=f"PR #{pr.id[:8]}: {pr.title or 'Pull Request'}",
            summary=f"Pull Request in status {pr.status}",
            metadata={"pull_request_id": pr.id, "status": pr.status, "target_branch": pr.target_branch},
        )
        node_count += 1

        if pr.source_change_id:
            ch_node = db.scalar(
                select(KnowledgeNode).where(
                    KnowledgeNode.repository_id == repo_id,
                    KnowledgeNode.entity_type == "change",
                    KnowledgeNode.metadata_json.contains(pr.source_change_id),
                )
            )
            if not ch_node:
                ch = db.scalar(select(Change).where(Change.id == pr.source_change_id))
                if ch:
                    ch_node = upsert_node(
                        db=db,
                        repository_id=repo_id,
                        entity_type="change",
                        name=f"Change #{ch.id[:8]}",
                        summary=ch.intent,
                        metadata={"change_id": ch.id, "status": ch.status},
                    )
                    node_count += 1
            if ch_node:
                add_edge(
                    db=db,
                    source_node_id=ch_node.id,
                    target_node_id=pr_node.id,
                    relationship_type="reviewed_in",
                )
                edge_count += 1

    # 5. Issues
    from app.models.issue import Issue
    issues = db.scalars(
        select(Issue).where(Issue.repository_id == repo_id)
    ).all()

    for iss in issues:
        iss_node = upsert_node(
            db=db,
            repository_id=repo_id,
            entity_type="issue",
            name=f"Issue #{iss.github_issue_number or iss.id[:8]}: {iss.title}",
            summary=iss.body[:200] if iss.body else f"Issue in status {iss.status}",
            metadata={
                "issue_id": iss.id,
                "github_issue_number": iss.github_issue_number,
                "status": iss.status,
                "task_id": iss.task_id,
                "agent_id": iss.agent_id,
            },
        )
        node_count += 1

        if iss.task_id:
            t_node = db.scalar(
                select(KnowledgeNode).where(
                    KnowledgeNode.repository_id == repo_id,
                    KnowledgeNode.entity_type == "task",
                    KnowledgeNode.metadata_json.contains(iss.task_id),
                )
            )
            if t_node:
                add_edge(
                    db=db,
                    source_node_id=iss_node.id,
                    target_node_id=t_node.id,
                    relationship_type="tracks_task",
                )
                edge_count += 1

    # 6. Discussions
    discussions = db.scalars(
        select(Discussion).where(Discussion.repository_id == repo_id)
    ).all()

    for d in discussions:
        disc_node = upsert_node(
            db=db,
            repository_id=repo_id,
            entity_type="discussion",
            name=f"Discussion: {d.title}",
            summary=d.body[:200] if d.body else f"Discussion in {d.category}",
            metadata={"discussion_id": d.id, "category": d.category},
        )
        node_count += 1

        import re
        task_uuid_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', f"{d.title} {d.body}")
        if task_uuid_match:
            tid = task_uuid_match.group(0)
            task_node = db.scalar(
                select(KnowledgeNode).where(
                    KnowledgeNode.repository_id == repo_id,
                    KnowledgeNode.entity_type == "task",
                    KnowledgeNode.metadata_json.contains(tid),
                )
            )
            if task_node:
                add_edge(
                    db=db,
                    source_node_id=disc_node.id,
                    target_node_id=task_node.id,
                    relationship_type="discussed_in",
                )
                edge_count += 1

    db.flush()
    return {"nodes": node_count, "edges": edge_count}


def get_file_context(
    db: Session,
    repository_id: str,
    file_path: str,
) -> dict:
    """
    Retrieves full engineering context for a file:
    defined symbols, historical changes, producing tasks, and modifying commits.
    """
    file_node = db.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.repository_id == repository_id,
            KnowledgeNode.entity_type == "file",
            KnowledgeNode.name == file_path,
        )
    )
    if not file_node:
        return {"file": file_path, "symbols": [], "related_entities": []}

    sub = get_subgraph(db, file_node.id)
    symbols = []
    related = []
    if sub:
        for nid, neighbor in sub["neighbors"].items():
            if neighbor.entity_type in ("function", "class", "module"):
                symbols.append({"name": neighbor.name, "type": neighbor.entity_type})
            else:
                related.append({"name": neighbor.name, "type": neighbor.entity_type, "summary": neighbor.summary})

    return {
        "file": file_path,
        "symbols": symbols,
        "related_entities": related,
    }


