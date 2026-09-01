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

