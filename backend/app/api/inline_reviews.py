from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.inline_review_service import InlineReviewService


router = APIRouter(tags=["inline-reviews"])


class InlineCommentCreateRequest(BaseModel):
    body: str
    path: str | None = None
    diff_side: str | None = None
    line_number: int | None = None
    commit_sha: str | None = None
    parent_id: str | None = None


class InlineCommentReplyRequest(BaseModel):
    body: str


@router.get("/v1/pull-requests/{pull_request_id}/comments")
def get_inline_comments(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = InlineReviewService(db)
    try:
        result = svc.get_comments_for_pull_request(
            pull_request_id=pull_request_id,
            user_id=current_user.id,
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")
        
        pr, comments = result
        return {"comments": comments}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/v1/pull-requests/{pull_request_id}/comments", status_code=status.HTTP_201_CREATED)
def create_inline_comment(
    pull_request_id: str,
    payload: InlineCommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = InlineReviewService(db)
    try:
        comment = svc.create_comment(
            pull_request_id=pull_request_id,
            author_id=current_user.id,
            body=payload.body,
            path=payload.path,
            diff_side=payload.diff_side,
            line_number=payload.line_number,
            commit_sha=payload.commit_sha,
            parent_id=payload.parent_id,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/v1/pull-requests/{pull_request_id}/comments/{comment_id}/reply", status_code=status.HTTP_201_CREATED)
def reply_to_inline_comment(
    pull_request_id: str,
    comment_id: str,
    payload: InlineCommentReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = InlineReviewService(db)
    try:
        comment = svc.create_comment(
            pull_request_id=pull_request_id,
            author_id=current_user.id,
            body=payload.body,
            parent_id=comment_id,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/v1/pull-requests/{pull_request_id}/comments/{comment_id}/resolve")
def resolve_inline_comment(
    pull_request_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = InlineReviewService(db)
    try:
        comment = svc.resolve_thread(
            comment_id=comment_id,
            user_id=current_user.id,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/v1/pull-requests/{pull_request_id}/comments/{comment_id}/reopen")
def reopen_inline_comment(
    pull_request_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = InlineReviewService(db)
    try:
        comment = svc.reopen_thread(
            comment_id=comment_id,
            user_id=current_user.id,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.get("/v1/pull-requests/{pull_request_id}/diff")
def get_pull_request_diff(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.pull_request_service import PullRequestService
    svc = PullRequestService(db)
    result = svc.get_pull_request_diff(pull_request_id, current_user.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")
    
    pr, diff = result
    return diff


@router.get("/v1/pull-requests/{pull_request_id}/files")
def get_pull_request_files(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.pull_request_service import PullRequestService
    svc = PullRequestService(db)
    result = svc.get_pull_request_files(pull_request_id, current_user.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pull Request not found")
    
    pr, files = result
    return {"files": files}
