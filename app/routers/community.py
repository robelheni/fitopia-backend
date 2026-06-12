from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.community import CommunityPost, CommunityComment, PostLike
from app.models.user import User
from app.routers.auth import get_user_by_email
from jose import JWTError, jwt
import os
from pydantic import BaseModel

class PostCreate(BaseModel):
    text: str
    tag: str = "progress"

router = APIRouter(prefix="/community", tags=["Community"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

def get_user_from_token(token: str, db:Session):
    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithm = [ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail= "Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail = "Invalid token")
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail = "user nort found")
    return user 

#return all pots on reverse chronological order 
#also tells the frintend whether the crrent user has liked each posts
@router.get("/posts")
def get_posts(token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token,db)

    posts = db.query(CommunityPost).order_by(CommunityPost.created_at.desc()).all()

    # fro eaxh post , we need to know if this user has liked it
    result = []
    for post in posts:
        liked = db.query(PostLike).filter(
            PostLike.post_id ==post.id,
            PostLike.user_id ==user.id
        ).first() is not None

        author = db.query(User).filter(User.id == post.user_id).first()

        result.append({
            "id": post.id,
            "user_id": post.user_id,
            "name": author.name if author else "Unknown",
            "text": post.text,
            "tag": post.tag,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "created_at": post.created_at.isoformat(),
            "liked_by_me": liked,
        })

    return result

@router.post("/posts")
def create_post(token: str, payload: dict, db: Session = Depends(get_db)):
    text = body.text
    tag = body.tag

    user = get_user_from_token(token, db)

    #Basic validation - dont save empty posts
    if not text.strip():
        raise HTTPException(status_code=400, detail = "Post text cannot be empty")

    #validate the tag is one of the three allowed values
    allowed_tags = ["progress","questions", "challenges"]
    if tag not in allowed_tags:
        raise HTTPException(status_code=400, detail=f"Tag must be one of {allowed_tags}")

    # Create the new post object -this doesnt save it yet
    new_post=CommunityPost(
        user_id=user.id,
        text=text.strip(),
        tag = tag,
        like_count=0,
        comment_count=0,
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
        "like_count": 0,
        "comment_count": 0,
        "created_at": new_post.created_at.isoformat(),
        "liked_by_me":False,
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

    db.commit()
    db.refresh(new_comment)

    return{
        "id": new_comment.id,
        "user_id": new_comment.user_id,
        "name": user.name,
        "text": new_comment.text,
        "created_at":new_comment.created_at.isoformat(),
    }
