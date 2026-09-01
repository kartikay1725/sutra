import json
from typing import Union

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import (
    get_current_agent_session,
)
from app.api.dependencies import (
    bearer_scheme,
    get_current_user,
)
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.user import User
from app.services import knowledge_graph_service
from app.services.authorization_service import (
    AuthorizationService,
)


router = APIRouter(
    prefix="/v1/repositories/{owner_name}/{repo_name}/graph",
    tags=["knowledge_graph"],
)


# ---------------------------------------------------------------------------
# Principal authentication
# ---------------------------------------------------------------------------

def get_graph_principal(
    authorization: str | None = Header(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> tuple[str, Union[User, Agent]]:
    """
    Authenticate either:
      - a normal SUTRA user JWT
      - an active SUTRA AgentSession
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication header",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    token = token.strip()

    # -----------------------------------------------------------------------
    # Agent session
    # -----------------------------------------------------------------------

    if token.startswith("sutra_session_"):
        session = get_current_agent_session(
            authorization=authorization,
            db=db,
        )

        agent = db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )

        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Agent is inactive or revoked",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        return "agent", agent

    # -----------------------------------------------------------------------
    # Normal user JWT
    # -----------------------------------------------------------------------

    credentials = HTTPAuthorizationCredentials(
        scheme=scheme,
        credentials=token,
    )

    user = get_current_user(
        credentials=credentials,
        db=db,
    )

    return "user", user


# ---------------------------------------------------------------------------
# Repository + authorization helpers
# ---------------------------------------------------------------------------

def _get_repository(
    owner_name: str,
    repo_name: str,
    db: Session,
) -> Repository:

    repo = db.scalar(
        select(Repository)
        .join(
            Actor,
            Actor.id == Repository.owner_id,
        )
        .where(
            Actor.name == owner_name,
            Repository.slug == repo_name.lower(),
            Repository.deleted_at.is_(None),
        )
    )

    if repo is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repo


def _get_or_create_agent_actor(
    agent: Agent,
    db: Session,
) -> Actor:

    actor = db.scalar(
        select(Actor).where(
            Actor.id == agent.id,
            Actor.type == "agent",
        )
    )

    if actor is None:
        actor = Actor(
            id=agent.id,
            owner_id=agent.owner_id,
            type="agent",
            name=agent.name,
            capabilities=json.dumps(
                [
                    "repository.read",
                    "repository.write",
                    "change.create",
                    "change.commit",
                    "change.conflict.read",
                    "knowledge_graph.read",
                    "knowledge_graph.write",
                ]
            ),
        )

        db.add(actor)
        db.flush()

    return actor


def _authorize_graph_access(
    principal_type: str,
    principal: Union[User, Agent],
    repository: Repository,
    capability: str,
    db: Session,
) -> None:

    # Human user path
    if principal_type == "user":
        if repository.owner_id != principal.id:
            # Allow reading public repositories
            if capability == AuthorizationService.KNOWLEDGE_GRAPH_READ and repository.visibility == "public":
                return
            if repository.visibility == "private":
                raise HTTPException(
                    status_code=404,
                    detail="Repository not found",
                )
            raise HTTPException(
                status_code=403,
                detail="Forbidden",
            )
        return

    # Agent path.
    agent = principal

    if not agent.is_active or agent.status != "active":
        raise HTTPException(
            status_code=401,
            detail="Agent is inactive or revoked",
        )

    from app.models.agent_repository_access import AgentRepositoryAccess
    access = db.scalar(
        select(AgentRepositoryAccess).where(
            AgentRepositoryAccess.agent_id == agent.id,
            AgentRepositoryAccess.repository_id == repository.id,
            AgentRepositoryAccess.enabled.is_(True),
        )
    )

    actor = _get_or_create_agent_actor(
        agent,
        db,
    )

    decision = AuthorizationService.check(
        actor=actor,
        repository=repository,
        capability=capability,
        db=db,
    )

    if not decision.allowed:
        if access is None and repository.visibility == "private":
            raise HTTPException(
                status_code=404,
                detail="Repository not found",
            )
        raise HTTPException(
            status_code=403,
            detail=decision.reason,
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UpsertNodeRequest(BaseModel):
    entity_type: str
    name: str
    summary: str | None = None
    content_hash: str | None = None
    metadata_json: dict | None = None


class AddEdgeRequest(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_type: str


class NodeResponse(BaseModel):
    id: str
    entity_type: str
    name: str
    summary: str | None
    content_hash: str | None
    metadata_json: dict


class EdgeResponse(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str


class SubgraphResponse(BaseModel):
    node: NodeResponse
    outgoing_edges: list[EdgeResponse]
    incoming_edges: list[EdgeResponse]
    neighbors: dict[str, NodeResponse]


class GraphDataResponse(BaseModel):
    nodes: list[NodeResponse]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_node(node) -> NodeResponse:
    return NodeResponse(
        id=node.id,
        entity_type=node.entity_type,
        name=node.name,
        summary=node.summary,
        content_hash=node.content_hash,
        metadata_json=(
            json.loads(node.metadata_json)
            if node.metadata_json
            else {}
        ),
    )


# ---------------------------------------------------------------------------
# Write: node
# ---------------------------------------------------------------------------

@router.post(
    "/nodes",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_node_endpoint(
    owner_name: str,
    repo_name: str,
    payload: UpsertNodeRequest,
    principal_data=Depends(
        get_graph_principal,
    ),
    db: Session = Depends(get_db),
):
    principal_type, principal = principal_data

    repo = _get_repository(
        owner_name,
        repo_name,
        db,
    )

    _authorize_graph_access(
        principal_type,
        principal,
        repo,
        AuthorizationService.KNOWLEDGE_GRAPH_WRITE,
        db,
    )

    node = knowledge_graph_service.upsert_node(
        db=db,
        repository_id=repo.id,
        entity_type=payload.entity_type,
        name=payload.name,
        summary=payload.summary,
        content_hash=payload.content_hash,
        metadata=payload.metadata_json,
    )

    db.commit()
    db.refresh(node)

    return _format_node(node)


# ---------------------------------------------------------------------------
# Write: edge
# ---------------------------------------------------------------------------

@router.post(
    "/edges",
    response_model=EdgeResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_edge_endpoint(
    owner_name: str,
    repo_name: str,
    payload: AddEdgeRequest,
    principal_data=Depends(
        get_graph_principal,
    ),
    db: Session = Depends(get_db),
):
    principal_type, principal = principal_data

    repo = _get_repository(
        owner_name,
        repo_name,
        db,
    )

    _authorize_graph_access(
        principal_type,
        principal,
        repo,
        AuthorizationService.KNOWLEDGE_GRAPH_WRITE,
        db,
    )

    edge = knowledge_graph_service.add_edge(
        db=db,
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        relationship_type=payload.relationship_type,
    )

    db.commit()
    db.refresh(edge)

    return EdgeResponse(
        id=edge.id,
        source_node_id=edge.source_node_id,
        target_node_id=edge.target_node_id,
        relationship_type=edge.relationship_type,
    )


# ---------------------------------------------------------------------------
# Read: complete graph
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=GraphDataResponse,
)
def get_graph_data(
    owner_name: str,
    repo_name: str,
    limit: int = Query(
        50,
        le=500,
    ),
    principal_data=Depends(
        get_graph_principal,
    ),
    db: Session = Depends(get_db),
):
    principal_type, principal = principal_data

    repo = _get_repository(
        owner_name,
        repo_name,
        db,
    )

    _authorize_graph_access(
        principal_type,
        principal,
        repo,
        AuthorizationService.KNOWLEDGE_GRAPH_READ,
        db,
    )

    from app.models.knowledge_node import KnowledgeNode

    nodes = db.scalars(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.repository_id == repo.id,
        )
        .limit(limit)
    ).all()

    return GraphDataResponse(
        nodes=[
            _format_node(node)
            for node in nodes
        ]
    )


# ---------------------------------------------------------------------------
# Read: search
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=list[NodeResponse],
)
def search_graph_nodes(
    owner_name: str,
    repo_name: str,
    q: str = Query(
        ...,
        min_length=1,
    ),
    limit: int = Query(
        20,
        le=100,
    ),
    principal_data=Depends(
        get_graph_principal,
    ),
    db: Session = Depends(get_db),
):
    principal_type, principal = principal_data

    repo = _get_repository(
        owner_name,
        repo_name,
        db,
    )

    _authorize_graph_access(
        principal_type,
        principal,
        repo,
        AuthorizationService.KNOWLEDGE_GRAPH_READ,
        db,
    )

    nodes = knowledge_graph_service.search_nodes(
        db=db,
        repository_id=repo.id,
        query=q,
        limit=limit,
    )

    return [
        _format_node(node)
        for node in nodes
    ]


# ---------------------------------------------------------------------------
# Read: node subgraph
# ---------------------------------------------------------------------------

@router.get(
    "/nodes/{node_id}",
    response_model=SubgraphResponse,
)
def get_node_subgraph(
    owner_name: str,
    repo_name: str,
    node_id: str,
    principal_data=Depends(
        get_graph_principal,
    ),
    db: Session = Depends(get_db),
):
    principal_type, principal = principal_data

    repo = _get_repository(
        owner_name,
        repo_name,
        db,
    )

    _authorize_graph_access(
        principal_type,
        principal,
        repo,
        AuthorizationService.KNOWLEDGE_GRAPH_READ,
        db,
    )

    subgraph = knowledge_graph_service.get_subgraph(
        db,
        node_id,
    )

    if not subgraph:
        raise HTTPException(
            status_code=404,
            detail="Node not found",
        )

    if (
        subgraph["node"].repository_id
        != repo.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Node belongs to different repository",
        )

    return SubgraphResponse(
        node=_format_node(
            subgraph["node"]
        ),
        outgoing_edges=[
            EdgeResponse(
                id=edge.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                relationship_type=edge.relationship_type,
            )
            for edge in subgraph[
                "outgoing_edges"
            ]
        ],
        incoming_edges=[
            EdgeResponse(
                id=edge.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                relationship_type=edge.relationship_type,
            )
            for edge in subgraph[
                "incoming_edges"
            ]
        ],
        neighbors={
            node_id: _format_node(node)
            for node_id, node in subgraph[
                "neighbors"
            ].items()
        },
    )


@router.post(
    "/index",
    status_code=status.HTTP_200_OK,
)
def index_repository_graph(
    owner_name: str,
    repo_name: str,
    principal: tuple[str, Union[User, Agent]] = Depends(
        get_graph_principal,
    ),
    db: Session = Depends(get_db),
):
    """
    Explicitly indexes repository source files into KnowledgeNodes and KnowledgeEdges.
    """
    repo = resolve_authorized_repository(
        owner_name=owner_name,
        repo_name=repo_name,
        principal=principal,
        db=db,
    )

    indexed_count = knowledge_graph_service.index_repository_files(
        db=db,
        repository=repo,
        commit_sha=repo.default_branch or "HEAD",
    )
    db.commit()

    return {
        "status": "indexed",
        "repository_id": repo.id,
        "indexed_nodes_count": indexed_count,
    }