from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent, _extract_bearer_token, verify_password
from app.api.dependencies import get_current_user_optional
from app.db.session import get_db
from app.models.agent import Agent
from app.models.user import User
from app.services.agent_review_service import AgentReviewService


router = APIRouter(tags=["agent-reviews"])


class AgentCommentCreateRequest(BaseModel):
    body: str
    path: str | None = None
    diff_side: str | None = None
    line_number: int | None = None
    commit_sha: str | None = None
    parent_id: str | None = None


class AgentFindingCreateRequest(BaseModel):
    severity: str
    category: str
    message: str
    path: str | None = None
    line_number: int | None = None
    diff_side: str | None = None
    suggested_fix: str | None = None


@router.post(
    "/v1/pull-requests/{pull_request_id}/agent-reviews/comments",
    status_code=status.HTTP_201_CREATED,
)
def create_agent_comment(
    pull_request_id: str,
    payload: AgentCommentCreateRequest,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    svc = AgentReviewService(db)
    try:
        comment = svc.create_agent_comment(
            agent_id=agent.id,
            pull_request_id=pull_request_id,
            body=payload.body,
            path=payload.path,
            diff_side=payload.diff_side,
            line_number=payload.line_number,
            commit_sha=payload.commit_sha,
            parent_id=payload.parent_id,
        )
        db.commit()
        return comment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post(
    "/v1/pull-requests/{pull_request_id}/agent-reviews/findings",
    status_code=status.HTTP_201_CREATED,
)
def create_agent_finding(
    pull_request_id: str,
    payload: AgentFindingCreateRequest,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    svc = AgentReviewService(db)
    try:
        finding = svc.create_agent_finding(
            agent_id=agent.id,
            pull_request_id=pull_request_id,
            severity=payload.severity,
            category=payload.category,
            message=payload.message,
            path=payload.path,
            line_number=payload.line_number,
            diff_side=payload.diff_side,
            suggested_fix=payload.suggested_fix,
        )
        db.commit()
        return finding
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/v1/pull-requests/{pull_request_id}/agent-reviews")
def get_agent_review_summary(
    pull_request_id: str,
    user: User | None = Depends(get_current_user_optional),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    svc = AgentReviewService(db)
    
    # Try user first, if not try agent
    if user:
        requestor_id = user.id
        is_agent = False
    else:
        if not authorization:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
        from app.api.agent_dependencies import get_current_agent_session, get_current_agent
        try:
            session = get_current_agent_session(authorization, db)
            agent = get_current_agent(session, db)
            requestor_id = agent.id
            is_agent = True
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        summary = svc.get_agent_review_summary(
            pull_request_id=pull_request_id,
            requestor_id=requestor_id,
            is_agent=is_agent,
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
