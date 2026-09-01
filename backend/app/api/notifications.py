from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(
    prefix="/v1/notifications",
    tags=["notifications"],
)

class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str | None
    type: str
    link: str | None
    is_read: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=list[NotificationResponse])
def get_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()

@router.post("/{notification_id}/read")
def mark_as_read(notification_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id))
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"status": "ok"}

@router.post("/read-all")
def mark_all_as_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications = db.scalars(select(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False)).all()
    for n in notifications:
        n.is_read = True
    db.commit()
    return {"status": "ok"}
