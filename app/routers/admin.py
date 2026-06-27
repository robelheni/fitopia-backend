from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.workout_log import WorkoutLog
from app.models.community import CommunityPost, CommunityComment
from app.models.follow import Follow
from app.routers.workouts import get_user_from_token

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(token: str, db: Session):
    """
    Checks that the requesting user is an admin. Raises 403 if not.
    Every endpoint in this file calls this first — it's the single
    gate that protects all admin functionality.
    """
    user = get_user_from_token(token, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/overview")
def get_admin_overview(token: str, db: Session = Depends(get_db)):
    """
    Returns high-level stats for the admin dashboard — total users,
    workouts logged, posts, follows, and recent signup activity.
    All numbers come from simple counts on existing tables, since
    we don't have a dedicated analytics system yet.
    """
    require_admin(token, db)

    total_users = db.query(User).count()
    total_pro_users = db.query(User).filter(User.is_pro == True).count()
    total_workouts_logged = db.query(WorkoutLog).count()
    total_posts = db.query(CommunityPost).count()
    total_comments = db.query(CommunityComment).count()
    total_follows = db.query(Follow).count()

    return {
        "total_users": total_users,
        "total_pro_users": total_pro_users,
        "total_workouts_logged": total_workouts_logged,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_follows": total_follows,
    }


@router.get("/users")
def get_all_users(token: str, db: Session = Depends(get_db)):
    """
    Returns a list of all users for the admin user management screen.
    Includes basic info needed for search/filter and quick actions.
    """
    require_admin(token, db)

    users = db.query(User).order_by(User.created_at.desc()).all()

    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "username": u.username,
            "is_pro": u.is_pro,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}/toggle-pro")
def toggle_user_pro(user_id: int, token: str, db: Session = Depends(get_db)):
    """
    Toggles a user's Pro status. Useful for granting free access to
    testers, fixing payment issues, or comping accounts manually.
    """
    require_admin(token, db)

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.is_pro = not target_user.is_pro
    db.commit()

    return {"id": target_user.id, "is_pro": target_user.is_pro}