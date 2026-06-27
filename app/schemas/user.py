from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

#what we expectwhen someone signs up
class UserCreate(BaseModel):
    name: str 
    email: str 
    password: str 
    
    referral_code: Optional[str] = None
    username:Optional[str] = None

# Wha we send back after signup or login - never include password
class UserResponse(BaseModel):
    id: int 
    name: str 
    email: str
    username: Optional[str] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    is_pro: bool 
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

#what we expect when someone logs in
class UserLogin(BaseModel):
    email:str 
    password: str 


#The JWT token we send back after login
class Token(BaseModel):
    access_token: str
    token_type: str
    
    
#Wha's inside the token
class TokenData(BaseModel):
    email: Optional[str] = None

#Onboarding Answers
class OnboardingUpdate(BaseModel):
    fitness_level: Optional[str] = None
    goal: Optional[str] = None
    days_per_week: Optional[str] = None
    training_days: Optional[str] = None
    workout_duration: Optional[str] = None
    equipment: Optional[str] = None
    food_preferences: Optional[str] = None
    location: Optional[str] = None
    injuries: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    goal_weight: Optional[float] = None 


