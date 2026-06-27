from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.workout_log import WorkoutLog
from app.models.community import CommunityPost, CommunityComment
from app.models.follow import Follow
from app.routers.workouts import get_user_from_token
from app.models.challenge import Challenge
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func

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


class ChallengeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#2563EB"  # defaults to blue if not specified


@router.post("/challenges")
def create_challenge(
    challenge_data: ChallengeCreate,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Creates a new challenge. Admin-only.
    """
    admin_user = require_admin(token, db)

    # Give the new challenge a display_order one higher than the current
    # maximum, so it lands at the bottom of the list with a distinct
    # value — not 0 like every other challenge, which made reordering
    # a no-op since swapping identical numbers does nothing
    max_order = db.query(func.max(Challenge.display_order)).scalar() or 0

    new_challenge = Challenge(
        name=challenge_data.name,
        description=challenge_data.description,
        color=challenge_data.color,
        display_order=max_order + 1,
        created_by=admin_user.id,
    )
    db.add(new_challenge)
    db.commit()
    db.refresh(new_challenge)

    return {
        "id": new_challenge.id,
        "name": new_challenge.name,
        "description": new_challenge.description,
        "color": new_challenge.color,
    }

@router.get("/challenges")
def get_admin_challenges(token: str, db: Session = Depends(get_db)):
    """
    Returns every challenge with its post count, ordered by display_order,
    for the admin management screen. Unlike the public endpoint, this
    always shows everything regardless of popularity — admins need to
    see and manage challenges even before they get any posts.
    """
    require_admin(token, db)

    from app.models.community import CommunityPost

    challenges = db.query(Challenge).order_by(Challenge.display_order.asc()).all()

    result = []
    for challenge in challenges:
        post_count = db.query(CommunityPost).filter(
            CommunityPost.challenge_id == challenge.id
        ).count()
        result.append({
            "id": challenge.id,
            "name": challenge.name,
            "description": challenge.description,
            "color": challenge.color,
            "display_order": challenge.display_order,
            "post_count": post_count,
        })

    return result


@router.put("/challenges/{challenge_id}/reorder")
def reorder_challenge(
    challenge_id: int,
    token: str,
    direction: str,  # "up" or "down"
    db: Session = Depends(get_db)
):
    """
    Moves a challenge up or down in display order by swapping its
    display_order value with the adjacent challenge. This is simpler
    than full drag-and-drop reordering and works well for a list
    that's only a handful of items long.
    """
    require_admin(token, db)

    challenges = db.query(Challenge).order_by(Challenge.display_order.asc()).all()

    # Find the index of the challenge we're moving
    index = next((i for i, c in enumerate(challenges) if c.id == challenge_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    if direction == "up" and index > 0:
        # Swap display_order with the one above it
        challenges[index].display_order, challenges[index - 1].display_order = \
            challenges[index - 1].display_order, challenges[index].display_order
    elif direction == "down" and index < len(challenges) - 1:
        # Swap display_order with the one below it
        challenges[index].display_order, challenges[index + 1].display_order = \
            challenges[index + 1].display_order, challenges[index].display_order

    db.commit()

    return {"message": "Reordered"}


@router.delete("/challenges/{challenge_id}")
def delete_challenge(challenge_id: int, token: str, db: Session = Depends(get_db)):
    """
    Deletes a challenge. Posts that were tagged to it keep their
    challenge_id pointing at a now-deleted challenge — we don't
    cascade-delete posts, since the posts themselves still have value
    as regular community content even if their challenge is removed.
    """
    require_admin(token, db)

    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    db.delete(challenge)
    db.commit()

    return {"message": "Challenge deleted"}


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
