from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.workout_log import WorkoutLog
from app.models.community import CommunityPost, CommunityComment
from app.models.follow import Follow
from app.routers.workouts import get_user_from_token
from app.models.challenge import Challenge
from app.models.trainer import Trainer
from app.models.trainer_application import TrainerApplication
from app.models.announcement import Announcement
from app.models.post_report import PostReport
from app.models.notification import Notification
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func
from datetime import datetime

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
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


class TrainerCreate(BaseModel):
    name: str
    bio: Optional[str] = None
    speciality: Optional[str] = None
    location: Optional[str] = None
    languages: Optional[str] = None
    years_experience: Optional[int] = None
    clients_trained: Optional[int] = None
    certifications: Optional[str] = None
    hourly_rate: Optional[float] = None
    profile_picture: Optional[str] = None
    instagram: Optional[str] = None
    contact_email: Optional[str] = None


class AnnouncementCreate(BaseModel):
    title: str
    message: str


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


# ── TRAINER MANAGEMENT ──────────────────────────────────────────

@router.post("/trainers")
def create_trainer(data: TrainerCreate, token: str, db: Session = Depends(get_db)):
    require_admin(token, db)
    new_trainer = Trainer(**data.dict())
    new_trainer.is_verified = True
    db.add(new_trainer)
    db.commit()
    db.refresh(new_trainer)
    return new_trainer

@router.get("/trainers")
def get_all_trainers(token: str, db: Session = Depends(get_db)):
    require_admin(token, db)
    return db.query(Trainer).order_by(Trainer.created_at.desc()).all()

@router.delete("/trainers/{trainer_id}")
def delete_trainer(trainer_id: int, token: str, db: Session = Depends(get_db)):
    require_admin(token, db)
    t = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trainer not found")
    db.delete(t)
    db.commit()
    return {"message": "Trainer deleted"}


# ── TRAINER APPLICATIONS ────────────────────────────────────────

@router.get("/trainer-applications")
def get_trainer_applications(token: str, db: Session = Depends(get_db)):
    require_admin(token, db)
    applications = db.query(TrainerApplication).order_by(
        TrainerApplication.created_at.desc()
    ).all()
    return [
        {
            "id": a.id,
            "full_name": a.full_name,
            "email": a.email,
            "speciality": a.speciality,
            "location": a.location,
            "years_experience": a.years_experience,
            "hourly_rate": a.hourly_rate,
            "instagram": a.instagram,
            "certifications": a.certifications,
            "bio": a.bio,
            "languages": a.languages,
            "status": a.status,
            "admin_notes": a.admin_notes,
            "created_at": a.created_at.isoformat(),
        }
        for a in applications
    ]

@router.put("/trainer-applications/{application_id}/approve")
def approve_trainer_application(
    application_id: int, token: str, db: Session = Depends(get_db)
):
    """Approves an application and auto-creates a verified Trainer record."""
    require_admin(token, db)

    app_record = db.query(TrainerApplication).filter(
        TrainerApplication.id == application_id
    ).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")

    new_trainer = Trainer(
        name=app_record.full_name,
        bio=app_record.bio,
        speciality=app_record.speciality,
        location=app_record.location,
        languages=app_record.languages,
        years_experience=app_record.years_experience,
        certifications=app_record.certifications,
        hourly_rate=app_record.hourly_rate,
        instagram=app_record.instagram,
        contact_email=app_record.email,
        is_verified=True,
    )
    db.add(new_trainer)

    app_record.status = "approved"
    app_record.reviewed_at = datetime.utcnow()
    db.commit()

    return {"message": "Application approved, trainer created"}

@router.put("/trainer-applications/{application_id}/reject")
def reject_trainer_application(
    application_id: int,
    token: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    require_admin(token, db)
    app_record = db.query(TrainerApplication).filter(
        TrainerApplication.id == application_id
    ).first()
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found")
    app_record.status = "rejected"
    app_record.admin_notes = notes
    app_record.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": "Application rejected"}


# ── ANNOUNCEMENTS ───────────────────────────────────────────────

@router.post("/announcements")
def create_announcement(
    data: AnnouncementCreate, token: str, db: Session = Depends(get_db)
):
    admin = require_admin(token, db)
    new_announcement = Announcement(
        title=data.title,
        message=data.message,
        created_by=admin.id,
    )
    db.add(new_announcement)
    db.flush()  # get the id before commit

    # Fan out a notification to every active user.
    # Use != False so users with is_active=NULL (pre-migration rows) are included.
    try:
        all_users = db.query(User).filter(User.is_active != False).all()
        for u in all_users:
            db.add(Notification(
                user_id=u.id,
                actor_id=admin.id,
                type="announcement",
                title=data.title,
                body=data.message,
            ))
    except Exception as e:
        # Don't fail the announcement creation if notification fan-out errors
        print(f"Announcement fan-out error: {e}")

    db.commit()
    db.refresh(new_announcement)
    return new_announcement

@router.get("/announcements")
def get_announcements(token: str, db: Session = Depends(get_db)):
    require_admin(token, db)
    return db.query(Announcement).order_by(Announcement.created_at.desc()).all()

@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: int, token: str, db: Session = Depends(get_db)
):
    require_admin(token, db)
    a = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(a)
    db.commit()
    return {"message": "Announcement deleted"}


# ── REPORTED POSTS ──────────────────────────────────────────────

@router.get("/reported-posts")
def get_reported_posts(token: str, db: Session = Depends(get_db)):
    require_admin(token, db)

    from app.models.community import CommunityPost, PostLike
    from app.models.user import User

    reports = db.query(PostReport).order_by(PostReport.reported_at.desc()).all()

    result = []
    for report in reports:
        post = db.query(CommunityPost).filter(
            CommunityPost.id == report.post_id
        ).first()
        reporter = db.query(User).filter(User.id == report.reported_by).first()
        author = db.query(User).filter(
            User.id == post.user_id
        ).first() if post else None

        result.append({
            "report_id": report.id,
            "reason": report.reason,
            "reported_at": report.reported_at.isoformat(),
            "reporter_name": reporter.name if reporter else "Unknown",
            "post_id": report.post_id,
            "post_text": post.text if post else "Post deleted",
            "post_author": author.name if author else "Unknown",
            "post_author_id": post.user_id if post else None,
        })

    return result

@router.delete("/posts/{post_id}")
def admin_delete_post(post_id: int, token: str, db: Session = Depends(get_db)):
    """Admin can delete any post regardless of who posted it."""
    require_admin(token, db)

    from app.models.community import CommunityPost, CommunityComment, PostLike

    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    db.query(PostLike).filter(PostLike.post_id == post_id).delete()
    db.query(CommunityComment).filter(CommunityComment.post_id == post_id).delete()
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


# ── MAKE / REMOVE ADMIN ─────────────────────────────────────────

@router.put("/users/{user_id}/toggle-admin")
def toggle_admin_status(user_id: int, token: str, db: Session = Depends(get_db)):
    current_admin = require_admin(token, db)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own admin access"
        )

    target.is_admin = not target.is_admin
    db.commit()
    return {"id": target.id, "is_admin": target.is_admin}


# ── BAN / UNBAN USER ────────────────────────────────────────────

@router.put("/users/{user_id}/toggle-ban")
def toggle_ban(user_id: int, token: str, db: Session = Depends(get_db)):
    """Bans or unbans a user by toggling is_active. Banned users cannot log in."""
    require_admin(token, db)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = not target.is_active
    db.commit()
    return {"id": target.id, "is_active": target.is_active}
