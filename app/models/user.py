from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy.dialects.postgresql import JSONB

class User(Base):
    __tablename__ = "users"

    #Primary key - eveyr user gets a uniques ID
    id = Column(Integer, primary_key=True, index=True)

    #Basic info
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    username= Column(String, unique=True, nullable=True)

    # onboarding answers
    fitness_level= Column(String, nullable= True)
    goal = Column(String, nullable=True)
    days_per_week = Column(String, nullable=True)
    training_days = Column(String, nullable=True)
    workout_duration = Column(String, nullable=True)
    equipment = Column(String, nullable=True)
    food_preferences = Column(String, nullable=True)
    location = Column(String, nullable = True)
    injuries = Column(String, nullable = True)

    #personal stats

    gender = Column(String, nullable = True)
    age = Column(Integer, nullable = True)
    height = Column(Float, nullable = True)
    weight = Column(Float, nullable = True)
    goal_weight = Column(Float, nullable = True)


    #referral
    referral_code = Column(String, nullable = True)
    referred_by = Column(String, nullable = True)

    #Account
    is_active = Column(Boolean, default=True)
    is_pro = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    starting_weight = Column(Float, nullable=True)