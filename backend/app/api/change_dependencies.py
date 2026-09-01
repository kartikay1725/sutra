from collections import deque

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.change import Change
from app.models.change_dependency import ChangeDependency
from app.models.repository import Repository
from app.models.user import User


router = APIRouter(
    prefix="/v1/changes",
    tags=["change-graph"],
)


RELATIONSHIPS = {
    "depends_on",
    "conflicts_with",
    "supersedes",
    "derived_from",
}


class DependencyRequest(BaseModel):
    target_change_id: str
    relationship: str = Field(
        pattern=r"^(depends_on|conflicts_with|supersedes|derived_from)$"
    )
    reason: str | None = Field(
        default=None,
        max_length=5000,
    )


class DependencyResponse(BaseModel):
    id: str
    source_change_id: str
    target_change_id: str
    relationship: str
    reason: str | None


class GraphNode(BaseModel):
    id: str
    intent: str
    status: str
    risk_level: str
    actor_id: str
    resulting_commit: str | None


class GraphEdge(BaseModel):
    source_change_id: str
    target_change_id: str
    relationship: str
    reason: str | None


class ChangeGraphResponse(BaseModel):
    root_change_id: str
    depth: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    topological_order: list[str]


def get_owned_change(
    change_id: str,
    current_user: User,
    db: Session,
) -> Change:
    change = db.scalar(
        select(Change)
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
    )

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    return change


def load_graph_edges(
    root: Change,
    db: Session,
) -> list[ChangeDependency]:
    return db.scalars(
        select(ChangeDependency)
        .join(
            Change,
            Change.id == ChangeDependency.source_change_id,
        )
        .where(
            Change.repository_id == root.repository_id,
        )
    ).all()


def detect_cycle(
    source_id: str,
    target_id: str,
    edges: list[ChangeDependency],
) -> bool:
    adjacency: dict[str, list[str]] = {}

    for edge in edges:
        adjacency.setdefault(
            edge.source_change_id,
            [],
        ).append(edge.target_change_id)

    adjacency.setdefault(
        source_id,
        [],
    ).append(target_id)

    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True

        if node in visited:
            return False

        visited.add(node)
        active.add(node)

        for child in adjacency.get(node, []):
            if visit(child):
                return True

        active.remove(node)
        return False

    return visit(source_id)


def topological_sort(
    node_ids: set[str],
    edges: list[ChangeDependency],
) -> list[str]:
    adjacency: dict[str, set[str]] = {
        node_id: set()
        for node_id in node_ids
    }

    indegree: dict[str, int] = {
        node_id: 0
        for node_id in node_ids
    }

    for edge in edges:
        if (
            edge.source_change_id not in node_ids
            or edge.target_change_id not in node_ids
        ):
            continue

        if edge.target_change_id not in adjacency[
            edge.source_change_id
        ]:
            adjacency[
                edge.source_change_id
            ].add(edge.target_change_id)

            indegree[
                edge.target_change_id
            ] += 1

    queue = deque(
        sorted(
            node
            for node, degree in indegree.items()
            if degree == 0
        )
    )

    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)

        for child in sorted(
            adjacency[node]
        ):
            indegree[child] -= 1

            if indegree[child] == 0:
                queue.append(child)

    if len(result) != len(node_ids):
        raise ValueError(
            "Change graph contains a cycle"
        )

    return result


@router.post(
    "/{change_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dependency(
    change_id: str,
    payload: DependencyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = get_owned_change(
        change_id,
        current_user,
        db,
    )

    target = get_owned_change(
        payload.target_change_id,
        current_user,
        db,
    )

    if source.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A change cannot depend on itself",
        )

    if source.repository_id != target.repository_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Changes must belong to the same repository",
        )

    if payload.relationship not in RELATIONSHIPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported relationship",
        )

    existing = db.scalar(
        select(ChangeDependency).where(
            ChangeDependency.source_change_id == source.id,
            ChangeDependency.target_change_id == target.id,
            ChangeDependency.relationship == payload.relationship,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dependency already exists",
        )

    all_edges = load_graph_edges(
        source,
        db,
    )

    if payload.relationship == "depends_on":
        if detect_cycle(
            source.id,
            target.id,
            all_edges,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Dependency would create a cycle",
            )

    dependency = ChangeDependency(
        source_change_id=source.id,
        target_change_id=target.id,
        relationship=payload.relationship,
        reason=payload.reason,
    )

    db.add(dependency)
    db.commit()
    db.refresh(dependency)

    return DependencyResponse(
        id=dependency.id,
        source_change_id=dependency.source_change_id,
        target_change_id=dependency.target_change_id,
        relationship=dependency.relationship,
        reason=dependency.reason,
    )


@router.get(
    "/{change_id}/dependencies",
    response_model=list[DependencyResponse],
)
def list_dependencies(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = get_owned_change(
        change_id,
        current_user,
        db,
    )

    dependencies = db.scalars(
        select(ChangeDependency).where(
            or_(
                ChangeDependency.source_change_id == change.id,
                ChangeDependency.target_change_id == change.id,
            )
        ).order_by(
            ChangeDependency.created_at.asc()
        )
    ).all()

    return [
        DependencyResponse(
            id=item.id,
            source_change_id=item.source_change_id,
            target_change_id=item.target_change_id,
            relationship=item.relationship,
            reason=item.reason,
        )
        for item in dependencies
    ]


@router.get(
    "/{change_id}/graph",
    response_model=ChangeGraphResponse,
)
def get_change_graph(
    change_id: str,
    depth: int = 3,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if depth < 1 or depth > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Depth must be between 1 and 20",
        )

    root = get_owned_change(
        change_id,
        current_user,
        db,
    )

    all_edges = load_graph_edges(
        root,
        db,
    )

    adjacency: dict[str, list[ChangeDependency]] = {}

    for edge in all_edges:
        adjacency.setdefault(
            edge.source_change_id,
            [],
        ).append(edge)

    visited: dict[str, int] = {
        root.id: 0
    }

    queue = deque([root.id])

    while queue:
        current_id = queue.popleft()
        current_depth = visited[current_id]

        if current_depth >= depth:
            continue

        for edge in adjacency.get(
            current_id,
            [],
        ):
            target = edge.target_change_id

            if target not in visited:
                visited[target] = (
                    current_depth + 1
                )
                queue.append(target)

    node_ids = set(visited.keys())

    graph_edges = [
        edge
        for edge in all_edges
        if (
            edge.source_change_id in node_ids
            and edge.target_change_id in node_ids
        )
    ]

    changes = db.scalars(
        select(Change).where(
            Change.id.in_(node_ids)
        )
    ).all()

    nodes = [
        GraphNode(
            id=item.id,
            intent=item.intent,
            status=item.status,
            risk_level=item.risk_level,
            actor_id=item.actor_id,
            resulting_commit=item.resulting_commit,
        )
        for item in changes
    ]

    try:
        ordering = topological_sort(
            node_ids,
            graph_edges,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return ChangeGraphResponse(
        root_change_id=root.id,
        depth=depth,
        nodes=nodes,
        edges=[
            GraphEdge(
                source_change_id=edge.source_change_id,
                target_change_id=edge.target_change_id,
                relationship=edge.relationship,
                reason=edge.reason,
            )
            for edge in graph_edges
        ],
        topological_order=ordering,
    )
