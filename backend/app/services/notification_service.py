from sqlalchemy.orm import Session
from app.models.notification import Notification

class NotificationService:
    @staticmethod
    def create_notification(db: Session, user_id: str, title: str, message: str, type: str, link: str = None, commit: bool = True):
        from app.models.actor import Actor
        from app.models.user import User

        target_user_id = user_id
        user_row = db.get(User, user_id)
        if not user_row:
            actor_row = db.get(Actor, user_id)
            if actor_row and actor_row.owner_id:
                target_user_id = actor_row.owner_id

        notif = Notification(
            user_id=target_user_id,
            title=title,
            message=message,
            type=type,
            link=link
        )
        db.add(notif)
        if commit:
            db.commit()
            db.refresh(notif)
        else:
            db.flush()
        return notif
