from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.routers.auth import get_user_by_email
from jose import JWTError, jwt
import os

router = APIRouter(prefix="/notifications", tags=["Notifications"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM")


def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def create_notification(db: Session, *, user_id: int, actor_id: int = None,
                        type: str, title: str, body: str = None, post_id: int = None):
    """Helper called by other routers to insert a notification row."""
    # Never notify yourself
    if actor_id and actor_id == user_id:
        return
    notif = Notification(
        user_id=user_id,
        actor_id=actor_id,
        type=type,
        title=title,
        body=body,
        post_id=post_id,
    )
    db.add(notif)
    # Caller is responsible for db.commit()


# ── GET /notifications ────────────────────────────────────────────────────────
@router.get("")
def get_notifications(token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )

    result = []
    for n in notifs:
        actor = db.query(User).filter(User.id == n.actor_id).first() if n.actor_id else None
        result.append({
            "id":         n.id,
            "type":       n.type,
            "title":      n.title,
            "body":       n.body,
            "is_read":    n.is_read,
            "post_id":    n.post_id,
            "actor_id":   n.actor_id,
            "actor_name": actor.name if actor else None,
            "actor_avatar": actor.profile_picture if actor else None,
            "created_at": n.created_at.isoformat(),
        })
    return result


# ── GET /notifications/unread-count ──────────────────────────────────────────
@router.get("/unread-count")
def get_unread_count(token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read == False)
        .count()
    )
    return {"count": count}


# ── POST /notifications/read-all ─────────────────────────────────────────────
@router.post("/read-all")
def mark_all_read(token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ── POST /notifications/{notification_id}/read ────────────────────────────────
@router.post("/{notification_id}/read")
def mark_one_read(notification_id: int, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"ok": True}
