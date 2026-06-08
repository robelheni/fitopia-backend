from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from datetime import datetime
from app.database import Base

class LikedExercise(Base):
    __tablename__ = "liked_exercises"

    # Auto incrementing ID for each like
    id = Column(Integer, primary_key=True, index=True)

    # The user who liked the exercise
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # The exercise that was liked
    exercise_id = Column(String, ForeignKey("exercises.id"), nullable=False)

    # When they liked it
    liked_at = Column(DateTime, default=datetime.utcnow)