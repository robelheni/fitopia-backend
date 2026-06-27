from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.database import Base

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True)

    # Controls manual ordering on the community page — lower numbers
    # show first. Defaults to 0 for new challenges; admin can reorder
    # by adjusting this value via the reorder endpoint.
    display_order = Column(Integer, default=0)

    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)