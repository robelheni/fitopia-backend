from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.follow import Follow
from app.models.community import CommunityPost
from app.routers.auth import get_user_by_email
from jose import JWTError, jwt
import os

router = APIRouter(prefix="/users", tags=["Users"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")


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





# Returns up to 20 matches — enough for a search result list
@router.get("/search")
def search_users(q: str, token: str, db: Session = Depends(get_db)):
    current_user = get_user_from_token(token, db)

    # Don't search if the query is too short — avoids returning
    if len(q.strip()) < 2:
        return []

    # Build the search pattern — %q% means "contains q anywhere"
    pattern = f"%{q.strip()}%"

    # Search both name and username columns
    # .ilike() is case-insensitive LIKE — so "heni" matches "Heni"
    # | is the OR operator in SQLAlchemy filters
    results = db.query(User).filter(
        (User.name.ilike(pattern)) | (User.username.ilike(pattern)),
        # Exclude the current user from results — no point finding yourself
        User.id != current_user.id,
    ).limit(20).all()

    return [
        {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "gender": user.gender,
            "bio": user.bio,
        }
        for user in results
    ]

# GET /users/{user_id}/profile
# Returns everything needed to render a user's profile screen:
# their name, username, post count, follower count, following count,
# whether the current user follows them, and their recent posts
@router.get("/{user_id}/profile")
def get_profile(user_id: int, token: str, db: Session = Depends(get_db)):
    # Who is logged in and viewing this profile
    current_user = get_user_from_token(token, db)

    # The user whose profile we are viewing
    profile_user = db.query(User).filter(User.id == user_id).first()
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count how many people follow this user
    # db.query(Follow).filter(...).count() returns an integer directly
    follower_count = db.query(Follow).filter(
        Follow.following_id == user_id
    ).count()

    # Count how many people this user follows
    following_count = db.query(Follow).filter(
        Follow.follower_id == user_id
    ).count()

    # Count their posts
    post_count = db.query(CommunityPost).filter(
        CommunityPost.user_id == user_id
    ).count()

    # Does the current user already follow this profile?
    # We need this so the frontend shows "Follow" or "Following" correctly
    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first() is not None

    # Get their posts, newest first — same pattern as community feed
    posts = db.query(CommunityPost).filter(
        CommunityPost.user_id == user_id
    ).order_by(CommunityPost.created_at.desc()).all()

    # Build the posts list with the same shape as the community feed
    # so the frontend can reuse the same post card component
    posts_data = []
    for post in posts:
        posts_data.append({
            "id": post.id,
            "text": post.text,
            "tag": post.tag,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "created_at": post.created_at.isoformat(),
        })

    return {
        "id": profile_user.id,
        "name": profile_user.name,
        "username": profile_user.username,
        "gender": profile_user.gender,
        "follower_count": follower_count,
        "following_count": following_count,
        "post_count": post_count,
        "is_following": is_following,
        "is_own_profile": current_user.id == user_id,
        "posts": posts_data,
    }


# POST /users/{user_id}/follow
# Toggles follow — if already following, unfollows. If not, follows.
# Same toggle pattern we used for post likes and exercise likes
@router.post("/{user_id}/follow")
def toggle_follow(user_id: int, token: str, db: Session = Depends(get_db)):
    current_user = get_user_from_token(token, db)

    # You can't follow yourself — this is a business rule we enforce here
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")

    # Check the target user exists
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already following
    existing = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()

    if existing:
        # Already following — unfollow by deleting the row
        db.delete(existing)
        db.commit()
        return {"following": False}
    else:
        # Not following — create a new Follow row
        new_follow = Follow(
            follower_id=current_user.id,
            following_id=user_id
        )
        db.add(new_follow)
        db.commit()
        return {"following": True}