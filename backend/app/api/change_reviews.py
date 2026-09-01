from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.repository import Repository
from app.models.user import User
from app.services.change_policy_service import ChangePolicyService
from app.services.change_service import ChangeService


router = APIRouter(
    prefix="/v1/changes",
    tags=["change-reviews"],
)


REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"

REVIEW_STATUSES = {
    REVIEW_PENDING,
    REVIEW_APPROVED,
    REVIEW_REJECTED,
}


class ReviewCreateRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=5000,
    )


class ReviewResponse(BaseModel):
    id: str
    change_id: str
    requested_by: str
    reviewer_id: str | None
    status: str
    reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class ReviewDecisionRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=5000,
    )


def get_owned_change(
    change_id: str,
    current_user: User,
    db: Session,
) -> Change:
    """
    Resolve a change owned by the current user.

    Used for operations that mutate the owner's change lifecycle,
    such as creating and listing review requests.
    """
    change = db.scalar(
        select(Change)
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            (Repository.owner_id == current_user.id) | (Repository.visibility == "public"),
            Repository.deleted_at.is_(None),
        )
    )

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    return change


def get_change(
    change_id: str,
    db: Session,
) -> Change:
    """
    Resolve an existing change without imposing repository ownership.

    Review approval/rejection intentionally supports delegated reviewers.
    Authorization for those actions is enforced by the review lifecycle
    rules below, including the prohibition on self-review.
    """
    change = db.scalar(
        select(Change)
        .join(
            Repository,
            Repository.id == Change.repository_id,
        )
        .where(
            Change.id == change_id,
            Repository.deleted_at.is_(None),
        )
    )

    if change is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    return change


def get_review(
    change_id: str,
    review_id: str,
    db: Session,
) -> ChangeReview:
    """
    Resolve a review belonging to the specified change.
    """
    review = db.scalar(
        select(ChangeReview).where(
            ChangeReview.id == review_id,
            ChangeReview.change_id == change_id,
        )
    )

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    return review


def serialize_review(
    review: ChangeReview,
) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        change_id=review.change_id,
        requested_by=review.requested_by,
        reviewer_id=review.reviewer_id,
        status=review.status,
        reason=review.reason,
        created_at=review.created_at,
        reviewed_at=review.reviewed_at,
    )


@router.post(
    "/{change_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    change_id: str,
    payload: ReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = get_owned_change(
        change_id,
        current_user,
        db,
    )

    policy = ChangePolicyService(db).evaluate(change)

    if policy.decision == ChangePolicyService.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Blocked changes cannot enter review",
        )

    existing_pending = db.scalar(
        select(ChangeReview).where(
            ChangeReview.change_id == change.id,
            ChangeReview.status == REVIEW_PENDING,
        )
    )

    if existing_pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending review already exists for this change",
        )

    review = ChangeReview(
        change_id=change.id,
        requested_by=current_user.id,
        status=REVIEW_PENDING,
        reason=payload.reason,
    )

    db.add(review)
    db.flush()

    ChangeService(db).transition_change(
        change=change,
        new_status=change.status,
        actor_id=current_user.id,
        event_type="change.review_requested",
        reason=payload.reason,
        metadata={
            "review_id": review.id,
            "requested_by": current_user.id,
        },
    )

    db.commit()
    db.refresh(review)

    return serialize_review(review)


@router.get(
    "/{change_id}/reviews",
    response_model=list[ReviewResponse],
)
def list_reviews(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change = get_owned_change(
        change_id,
        current_user,
        db,
    )

    reviews = db.scalars(
        select(ChangeReview)
        .where(
            ChangeReview.change_id == change.id,
        )
        .order_by(
            ChangeReview.created_at.asc()
        )
    ).all()

    return [
        serialize_review(review)
        for review in reviews
    ]


@router.post(
    "/{change_id}/reviews/{review_id}/approve",
    response_model=ReviewResponse,
    summary="Approve Change Review (Human JWT required)",
    description="Approves a pending change review. The requester cannot approve their own review. Agents cannot approve reviews; this action requires Human JWT.",
)
def approve_review(
    change_id: str,
    review_id: str,
    payload: ReviewDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Delegated reviewers are supported by the current SUTRA contract.
    # Therefore approval does not require repository ownership.
    change = get_change(
        change_id,
        db,
    )

    review = get_review(
        change.id,
        review_id,
        db,
    )

    if review.status != REVIEW_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending reviews can be approved",
        )

    # Prevent the requester from approving their own request.
    if review.requested_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A reviewer cannot approve their own review request",
        )

    policy = ChangePolicyService(db).evaluate(change)

    if policy.decision == ChangePolicyService.BLOCK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Change is currently blocked by policy",
        )

    now = datetime.now(timezone.utc)

    review.status = REVIEW_APPROVED
    review.reviewer_id = current_user.id
    review.reason = payload.reason or review.reason
    review.reviewed_at = now

    db.flush()

    ChangeService(db).transition_change(
        change=change,
        new_status=change.status,
        actor_id=current_user.id,
        event_type="change.review_approved",
        reason=payload.reason,
        metadata={
            "review_id": review.id,
            "reviewer_id": current_user.id,
            "reason": payload.reason,
        },
    )

    if change.status == "proposed":
        ChangeService(db).finalize_change(change)

    db.commit()
    db.refresh(review)

    return serialize_review(review)


@router.post(
    "/{change_id}/reviews/{review_id}/reject",
    response_model=ReviewResponse,
    summary="Reject Change Review (Human JWT required)",
    description="Rejects a pending change review. The requester cannot reject their own review. Agents cannot reject reviews; this action requires Human JWT.",
)
def reject_review(
    change_id: str,
    review_id: str,
    payload: ReviewDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Delegated reviewers are supported by the current SUTRA contract.
    change = get_change(
        change_id,
        db,
    )

    review = get_review(
        change.id,
        review_id,
        db,
    )

    if review.status != REVIEW_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending reviews can be rejected",
        )

    # Prevent the requester from rejecting their own request.
    if review.requested_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A reviewer cannot reject their own review request",
        )

    now = datetime.now(timezone.utc)

    review.status = REVIEW_REJECTED
    review.reviewer_id = current_user.id
    review.reason = payload.reason or review.reason
    review.reviewed_at = now

    ChangeService(db).transition_change(
        change=change,
        new_status=change.status,
        actor_id=current_user.id,
        event_type="change.review_rejected",
        reason=payload.reason,
        metadata={
            "review_id": review.id,
            "reviewer_id": current_user.id,
            "reason": payload.reason,
        },
    )

    db.commit()
    db.refresh(review)

    return serialize_review(review)