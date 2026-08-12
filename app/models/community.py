from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from datetime import datetime
from app.database import Base

class CommunityPost(Base):
    __tablename__="community_posts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    text = Column(String(500), nullable=False)

    tag = Column(String(20), nullable=False, default='progress')

    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=True)

    image_url = Column(String, nullable=True)

    is_private = Column(Boolean, default=False, nullable=False)
    comments_disabled = Column(Boolean, default=False, nullable=False)

    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id = Column(Integer, primary_key=True, index=True)

    #points to the posts like which post does this commnet belong to
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=False)

    #points to users - who wrote this comment
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    text = Column(String(300), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PostLike(Base):
    __tablename__ = "post_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=False)
    user_id = Column (Integer, ForeignKey("users.id"), nullable=False)
    liked_at = Column(DateTime, default=datetime.utcnow)
