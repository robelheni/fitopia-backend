from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from app.database import Base

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)

    # e.g. "15 Pull-Ups", "50 Push-Ups Challenge"
    name = Column(String, nullable=False)

    # Longer explanation shown at the top of the challenge page
    description = Column(Text, nullable=True)

    # Who created it — always an admin for now, but storing this
    # keeps the door open for user-created challenges later
    created_by = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)