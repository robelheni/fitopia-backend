from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from app.database import Base

class PostReport(Base):
    __tablename__ = "post_reports"

    id = Column(Integer, primary_key=True, index=True)

    # Which post is being reported
    post_id = Column(Integer, ForeignKey("community_posts.id"), nullable=False)

    # Who reported it
    reported_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Why — keeps this simple with a short reason string rather than
    # a separate enum table, since report categories rarely change
    reason = Column(String, nullable=True)

    reported_at = Column(DateTime, default=datetime.utcnow)