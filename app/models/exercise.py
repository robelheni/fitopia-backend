from sqlalchemy import Column, String, Boolean, Integer, JSON
from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    muscle_group = Column(String, nullable=False)
    secondary_muscles = Column(JSON, nullable=True)
    equipment = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    injury_flags = Column(JSON, nullable=True)
    goal_tags = Column(JSON, nullable=True)
    # Priority 1 = best exercises, 2 = secondary, 3 = accessories
    priority = Column(Integer, nullable=True)
    # Movement pattern prevents duplicate movements in the same session
    movement_pattern = Column(String, nullable=True)
    duration_weight = Column(Integer, nullable=True)
    sets_range = Column(JSON, nullable=True)
    reps_range = Column(JSON, nullable=True)
    is_timed = Column(Boolean, default=False)
    seconds_range = Column(JSON, nullable=True)
    video_url = Column(String, nullable=True)
    description = Column(String, nullable=True)
    instructions = Column(JSON, nullable=True)
    coaching_cues = Column(JSON, nullable=True)
