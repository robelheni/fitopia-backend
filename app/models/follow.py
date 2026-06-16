from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime
from app.database import Base

class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)

    # The user who is doing the following — "I follow you"
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # The user being followed — "you are followed by me"
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # When the follow happened
    followed_at = Column(DateTime, default=datetime.utcnow)