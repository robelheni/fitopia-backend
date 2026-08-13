from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import get_db
from app.models.community import CommunityPost, CommunityComment, PostLike
from app.models.user import User
from app.models.follow import Follow
from app.routers.auth import get_user_by_email
from app.routers.notifications import create_notification
from jose import JWTError, jwt
import os
from pydantic import BaseModel
from app.models.post_report import PostReport
from app.models.challenge import Challenge
from app.models.trainer import Trainer
from app.models.trainer_application import TrainerApplication
from sqlalchemy import func
from typing import Optional


class PostCreate(BaseModel):
    text: str
    tag: str = "progress"
    challenge_id: Optional[int] = None
    image_url: Optional[str] = None

router = APIRouter(prefix="/community", tags=["Community"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

def get_user_from_token(token: str, db:Session):
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail= "Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail = "Invalid token")
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail = "user not found")
    return user 

# GET /community/posts/{post_id} — single post by ID
@router.get("/posts/{post_id}")
def get_post(post_id: int, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    author = db.query(User).filter(User.id == post.user_id).first()
    liked = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == user.id
    ).first() is not None
    return {
        "id": post.id,
        "user_id": post.user_id,
        "name": author.name if author else "Unknown",
        "profile_picture": author.profile_picture if author else None,
        "text": post.text,
        "tag": post.tag,
        "image_url": post.image_url,
        "is_private": post.is_private,
        "comments_disabled": post.comments_disabled,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "liked_by_me": liked,
        "created_at": post.created_at.replace(tzinfo=timezone.utc).isoformat(),
    }


# Returns ranked feed posts — score combines engagement, follow relationship, and recency.
@router.get("/posts")
def get_posts(token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    # Fetch all public posts — order doesn't matter here, we'll sort by score below
    posts = db.query(CommunityPost).all()

    # Build the set of user_ids this viewer follows in one query (O(1) lookup in the loop)
    followed_ids = {
        f.following_id for f in
        db.query(Follow).filter(Follow.follower_id == user.id).all()
    }

    now = datetime.now(timezone.utc)

    scored_posts = []
    for post in posts:
        # Private posts only appear on profile pages, never in the public feed
        if post.is_private:
            continue

        # Normalise naive UTC datetimes stored without tzinfo
        post_time = post.created_at
        if post_time.tzinfo is None:
            post_time = post_time.replace(tzinfo=timezone.utc)

        hours_old = (now - post_time).total_seconds() / 3600
        time_decay = hours_old + 2  # +2 so brand-new posts don't dominate and avoids div-by-zero

        follow_boost = 15 if post.user_id in followed_ids else 0
        score = (post.like_count + (post.comment_count * 2) + follow_boost) / time_decay

        liked = db.query(PostLike).filter(
            PostLike.post_id == post.id,
            PostLike.user_id == user.id
        ).first() is not None

        author = db.query(User).filter(User.id == post.user_id).first()

        scored_posts.append((score, {
            "id": post.id,
            "user_id": post.user_id,
            "name": author.name if author else "Unknown",
            "gender": author.gender if author else None,
            "profile_picture": author.profile_picture if author else None,
            "text": post.text,
            "tag": post.tag,
            "image_url": post.image_url,
            "is_private": post.is_private,
            "comments_disabled": post.comments_disabled,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "created_at": post.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "liked_by_me": liked,
            "score": round(score, 2),
        }))

    # Sort highest score first
    scored_posts.sort(key=lambda x: x[0], reverse=True)
    return [post for _, post in scored_posts]

@router.post("/posts")
def create_post(token: str, body: PostCreate, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    text = body.text
    tag = body.tag

    

    #Basic validation - dont save empty posts
    if not text.strip():
        raise HTTPException(status_code=400, detail = "Post text cannot be empty")

    #validate the tag is one of the three allowed values
    allowed_tags = ["progress","questions", "challenges", "general"]
    if tag not in allowed_tags:
        raise HTTPException(status_code=400, detail=f"Tag must be one of {allowed_tags}")

    # Create the new post object -this doesnt save it yet
    new_post=CommunityPost(
        user_id=user.id,
        text=text.strip(),
        tag = tag,
        like_count=0,
        comment_count=0,
        challenge_id=body.challenge_id,
        image_url=body.image_url,
    )


    #I want to save this
    db.add(new_post)

    #writes it to database, and saves it
    db.commit()

    #updates our local object with what the databse now has
    db.refresh(new_post)

    return {
        "id": new_post.id,
        "text": new_post.text,
        "tag": new_post.tag,
        "image_url": new_post.image_url,
        "like_count": 0,
        "comment_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "liked_by_me": False,
    }



@router.post("/posts/{post_id}/like")
def toggle_like(post_id: int, token:str, db: Session = Depends(get_db)):
    user = get_user_from_token(token,db)

    # frist check the post actually exists
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    #check if this use has already liked the post
    existing_like = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == user.id,
    ).first()

    if existing_like:
        #already liked - so we unlike it
        db.delete(existing_like)
        post.like_count = max(0, post.like_count-1)
        db.commit()
        return{"liked":False, "like_count": post.like_count}
    else:
        #not yet liked - so we like it

        #creating a row with a post id and and user id
        new_like = PostLike(post_id=post_id, user_id=user.id)
        #the add it
        db.add(new_like)

        #then we increase the count of the like
        post.like_count = post.like_count+1

        # Notify the post owner
        create_notification(
            db,
            user_id=post.user_id,
            actor_id=user.id,
            type="like",
            title=f"{user.name} liked your post",
            post_id=post_id,
        )

        db.commit()
        return{"liked":True, "like_count": post.like_count}

#Reutrns all comments for a specific post, oldest first

@router.get("/posts/{post_id}/comments")
def get_comments(post_id:int, token:str, db:Session = Depends(get_db)):
    user = get_user_from_token(token,db)

    #check the post exists
    post  = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=400, detail="Post not found")

    #Get all comments for this post, oldest first so the conversation reads top to bottom
    comments = db.query(CommunityComment).filter(
        CommunityComment.post_id == post_id
    ).order_by(CommunityComment.created_at.asc()).all()

    #For each comment we also need the author's name
    result = []
    for comment in comments:
        author = db.query(User).filter(User.id == comment.user_id).first()
        result.append({
            "id":comment.id,
            "user": comment.user_id,
            "name": author.name if author else "Unknown",
            "profile_picture": author.profile_picture if author else None,
            "text": comment.text,
            "created_at": comment.created_at.isoformat(),
        })
    return result

#saves a new comment on a post
@router.post("/posts/{post_id}/comments")
def create_comment(post_id:int, token: str, text: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token,db)

    #check the posts exists
    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()

    if not post:
        raise HTTPException(status_code=400, detail="Post not found")

    if post.comments_disabled:
        raise HTTPException(status_code=403, detail="Comments are disabled on this post")

    #dont save an empty comment
    if not text.strip():
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    #create and save the comment
    new_comment = CommunityComment(
        post_id=post_id,
        user_id=user.id,
        text=text.strip(),
    )

    db.add(new_comment)

    post.comment_count = post.comment_count+1

    # Notify the post owner
    create_notification(
        db,
        user_id=post.user_id,
        actor_id=user.id,
        type="comment",
        title=f"{user.name} commented on your post",
        body=text.strip()[:100],
        post_id=post_id,
    )

    db.commit()
    db.refresh(new_comment)

    return{
        "id": new_comment.id,
        "user_id": new_comment.user_id,
        "name": user.name,
        "profile_picture": user.profile_picture,
        "text": new_comment.text,
        "created_at":new_comment.created_at.isoformat(),
    }

@router.delete("/posts/{post_id}")
def delete_post(post_id: int, token: str, db: Session = Depends(get_db)):
    """
    Deletes a community post. Only the post's original author can delete it —
    this is a critical security check. Without verifying ownership, anyone
    with a post ID could delete anyone else's content.
    """
    user = get_user_from_token(token, db)

    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Ownership check — this is the security-critical line
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own posts")

    # Also clean up related likes and comments so we don't leave orphaned rows
    db.query(PostLike).filter(PostLike.post_id == post_id).delete()
    db.query(CommunityComment).filter(CommunityComment.post_id == post_id).delete()

    db.delete(post)
    db.commit()

    return {"message": "Post deleted"}



@router.post("/posts/{post_id}/toggle-privacy")
def toggle_privacy(post_id: int, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only modify your own posts")

    post.is_private = not post.is_private
    db.commit()
    return {"is_private": post.is_private}


@router.post("/posts/{post_id}/toggle-comments")
def toggle_comments(post_id: int, token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only modify your own posts")

    post.comments_disabled = not post.comments_disabled
    db.commit()
    return {"comments_disabled": post.comments_disabled}


@router.post("/posts/{post_id}/report")
def report_post(post_id: int, token: str, reason: str = "Not specified", db: Session = Depends(get_db)):
    """
    Logs a report against a post. We don't auto-delete or hide anything here —
    reports just get recorded so they can be reviewed later. This keeps the
    feature simple now while still giving you real signal on problem content
    as the community grows.
    """
    user = get_user_from_token(token, db)

    post = db.query(CommunityPost).filter(CommunityPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Prevent the same user from reporting the same post multiple times
    existing = db.query(PostReport).filter(
        PostReport.post_id == post_id,
        PostReport.reported_by == user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already reported this post")

    report = PostReport(
        post_id=post_id,
        reported_by=user.id,
        reason=reason
    )
    db.add(report)
    db.commit()

    return {"message": "Post reported"}




@router.get("/challenges")
def get_challenges(db: Session = Depends(get_db)):
    """
    Returns all challenges, ranked by how many posts are tagged to them —
    most popular challenges first. This drives the "trending" feel on
    the community page, where active challenges rise to the top.
    """
    challenges = db.query(Challenge).all()

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
            "post_count": post_count,
        })

    # Sort by post_count descending — most popular challenges first
    result.sort(key=lambda c: c["post_count"], reverse=True)

    return result


@router.get("/challenges/{challenge_id}")
def get_challenge_detail(challenge_id: int, token: str, db: Session = Depends(get_db)):
    """
    Returns a single challenge's details plus every post tagged to it,
    newest first. This powers the challenge detail page — description
    at the top, community posts about it below.
    """
    user = get_user_from_token(token, db)

    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    posts = db.query(CommunityPost).filter(
        CommunityPost.challenge_id == challenge_id
    ).order_by(CommunityPost.created_at.desc()).all()

    posts_data = []
    for post in posts:
        author = db.query(User).filter(User.id == post.user_id).first()
        liked = db.query(PostLike).filter(
            PostLike.post_id == post.id,
            PostLike.user_id == user.id
        ).first() is not None

        posts_data.append({
            "id": post.id,
            "user_id": post.user_id,
            "name": author.name if author else "Unknown",
            "gender": author.gender if author else None,
            "profile_picture": author.profile_picture if author else None,
            "text": post.text,
            "tag": post.tag,
            "image_url": post.image_url,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "liked_by_me": liked,
            "created_at": post.created_at.isoformat(),
        })

    return {
        "id": challenge.id,
        "name": challenge.name,
        "description": challenge.description,
        "color": challenge.color,
        "post_count": len(posts_data),
        "posts": posts_data,
    }


# ── PUBLIC TRAINER ENDPOINTS ─────────────────────────────────────

@router.get("/trainers")
def get_trainers(db: Session = Depends(get_db)):
    """Returns all verified, active trainers for the public trainers page."""
    trainers = db.query(Trainer).filter(
        Trainer.is_verified == True,
        Trainer.is_active == True,
    ).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "bio": t.bio,
            "speciality": t.speciality,
            "location": t.location,
            "languages": t.languages,
            "years_experience": t.years_experience,
            "clients_trained": t.clients_trained,
            "certifications": t.certifications,
            "hourly_rate": t.hourly_rate,
            "profile_picture": t.profile_picture,
            "instagram": t.instagram,
            "contact_email": t.contact_email,
        }
        for t in trainers
    ]


@router.get("/trainers/{trainer_id}")
def get_trainer(trainer_id: int, db: Session = Depends(get_db)):
    """Returns a single trainer's full profile by ID."""
    t = db.query(Trainer).filter(
        Trainer.id == trainer_id,
        Trainer.is_verified == True,
        Trainer.is_active == True,
    ).first()
    if not t:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return {
        "id": t.id,
        "name": t.name,
        "bio": t.bio,
        "speciality": t.speciality,
        "location": t.location,
        "languages": t.languages,
        "years_experience": t.years_experience,
        "clients_trained": t.clients_trained,
        "certifications": t.certifications,
        "hourly_rate": t.hourly_rate,
        "profile_picture": t.profile_picture,
        "instagram": t.instagram,
        "contact_email": t.contact_email,
    }


class TrainerApplicationCreate(BaseModel):
    full_name: str
    email: str
    bio: Optional[str] = None
    speciality: Optional[str] = None
    location: Optional[str] = None
    languages: Optional[str] = None
    years_experience: Optional[int] = None
    certifications: Optional[str] = None
    hourly_rate: Optional[float] = None
    instagram: Optional[str] = None
    whatsapp: Optional[str] = None


@router.post("/trainer-applications")
def submit_trainer_application(
    data: TrainerApplicationCreate,
    token: str,
    db: Session = Depends(get_db)
):
    """Any logged-in user can submit a trainer application for admin review."""
    user = get_user_from_token(token, db)

    application = TrainerApplication(
        user_id=user.id,
        full_name=data.full_name,
        email=data.email,
        bio=data.bio,
        speciality=data.speciality,
        location=data.location,
        languages=data.languages,
        years_experience=data.years_experience,
        certifications=data.certifications,
        hourly_rate=data.hourly_rate,
        instagram=data.instagram,
        whatsapp=data.whatsapp,
        status="pending",
    )
    db.add(application)
    db.commit()
    return {"message": "Application submitted successfully"}