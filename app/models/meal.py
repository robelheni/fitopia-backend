# app/models/meal.py
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base

class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    meal_type = Column(String, nullable=False)
    description = Column(Text)
    prep_time = Column(String)
    calories = Column(Integer, nullable=False)
    protein = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)
    fats = Column(Float, nullable=False)
    fibre = Column(Float, default=0)
    calorie_category = Column(String)
    is_ethiopian = Column(Boolean, default=False)
    is_meat = Column(Boolean, default=False)
    is_vegetarian = Column(Boolean, default=False)
    is_fasting_friendly = Column(Boolean, default=False)
    why = Column(Text)
    best_time = Column(Text)
    ingredients = Column(JSONB)
    steps = Column(JSONB)
    swap_group = Column(String)
    swap_reason = Column(Text)
    tag = Column(String)
    tag_color = Column(String)
    tag_bg = Column(String)
    min_servings = Column(Float, default=0.75)
    max_servings = Column(Float, default=1.5)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())