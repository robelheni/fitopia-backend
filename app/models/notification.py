from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from datetime import datetime
from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)   # recipient
    actor_id   = Column(Integer, ForeignKey("users.id"), nullable=True)    # who triggered it
    type       = Column(String(50), nullable=False)                        # follow/like/comment/announcement/…
    title      = Column(String(200), nullable=False)
    body       = Column(String(500), nullable=True)
    post_id    = Column(Integer, ForeignKey("community_posts.id"), nullable=True)
    is_read    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
