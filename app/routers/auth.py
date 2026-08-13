from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt 
from passlib.context import CryptContext
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token, TokenData 
from pydantic import BaseModel
from dotenv import load_dotenv
import os 
import random
import string
from app.schemas.user import OnboardingUpdate
from typing import Optional

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None

load_dotenv()


router = APIRouter(
    prefix = "/auth",
    tags=["Authentication"]
)

#Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#JWT settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))


# ─── Helper functions ───────────────────────────────────────────────

def hash_password(password:str) -> str:
    """Turn a plain password into hash"""
    return pwd_context.hash(password)

def verify_password(plain_password:str, hashed_password:str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def generate_referral_code(name:str) -> str:
    suffix=''.join(random.choices(string.digits, k=4))
    return f"{name.upper()[:4]}{suffix}"

def create_access_token(data:dict) -> str:
    """create a JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email.lower().strip()).first()

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username.lower().strip()).first()


# ─── Endpoints ──────────────────────────────────────────────────────

@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db:Session = Depends(get_db)):
    print(f"Signup received - name: {user.name}, email: {user.email}, username: {user.username}")

    #check if email already exists
    existing_user = get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail = "An account with email already exists"
        )

    # Check if username already taken
    if user.username:
        existing_username = db.query(User).filter(User.username == user.username.lower().strip()).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This username is already taken"
            )


    hashed= hash_password(user.password)

    referral = generate_referral_code(user.name)

    #create the user
    new_user = User(
        name=user.name,
        email=user.email.lower().strip(),
        username=user.username.lower().strip() if user.username else None,
        hashed_password=hashed,
        referral_code=referral,
        referred_by=user.referral_code
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    
    # Detect if the user typed an email or username
    # Emails always contain @ — usernames never do
    if '@' in credentials.email:
        user = get_user_by_email(db, credentials.email.lower().strip())
    else:
        user = get_user_by_username(db, credentials.email.lower().strip())

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email, username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account has been suspended. Please contact support.",
        )

    access_token = create_access_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "token_type": "Bearer"
    }
@router.get("/me", response_model=UserResponse)
def get_current_user(token:str, db:Session = Depends(get_db)):
    """get currently logged in user from their token"""
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        #decode the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email:str = payload.get("sub")
        if email is None:
            raise credential_exception
    except JWTError:
        raise credential_exception

    #find the user
    user = get_user_by_email(db, email)
    if user is None:
        raise credential_exception

    return user


@router.put("/onboarding", response_model = UserResponse)
def save_onboarding(
    answers: OnboardingUpdate,
    token: str,
    db: Session = Depends(get_db)
):

    """save onboarding answers for the logged in user"""

    #decode to get the user
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail = "COULD NOT VALIDATE CREDENTIALS",
    )



    try: 
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email)

    if user is None:
        raise credentials_exception

    #update only the fields that were provided
    if answers.fitness_level is not None:
        user.fitness_level = answers.fitness_level
    if answers.goal is not None:
        user.goal = answers.goal
    if answers.days_per_week is not None:
        user.days_per_week = answers.days_per_week
    if answers.training_days is not None:
        user.training_days = ','.join(answers.training_days) if isinstance(answers.training_days, list) else answers.training_days
    if answers.workout_duration is not None:
        user.workout_duration = answers.workout_duration
    if answers.equipment is not None:
        user.equipment = answers.equipment
    if answers.food_preferences is not None:
        user.food_preferences = ','.join(answers.food_preferences) if isinstance(answers.food_preferences, list) else answers.food_preferences
    if answers.location is not None:
        user.location = answers.location
    if answers.injuries is not None:
        user.injuries = answers.injuries
    if answers.gender is not None:
        user.gender = answers.gender
    if answers.age is not None:
        user.age = answers.age
    if answers.height is not None:
        user.height = answers.height
    if answers.weight is not None:
        user.weight = answers.weight
    if answers.goal_weight is not None:
        user.goal_weight = answers.goal_weight


    if not user.starting_weight:
        user.starting_weight = user.weight


    #save to database
    db.commit()
    db.refresh(user)

    return user

@router.put("/update-profile")
def update_profile(
    updates: ProfileUpdate,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Lets the user update their name, username, and bio.
    Only updates fields that were actually provided — 
    if you only send bio, name and username stay the same.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception

    # Only update fields that were actually sent
    # This is called a "partial update" — we don't overwrite 
    # everything, just what the user explicitly changed
    if updates.name is not None and updates.name.strip():
        user.name = updates.name.strip()

    if updates.username is not None:
        # Check the new username isn't already taken by someone else
        # We exclude the current user from this check — otherwise
        # saving without changing username would fail
        existing = db.query(User).filter(
            User.username == updates.username.lower().strip(),
            User.id != user.id  # not the current user
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="This username is already taken"
            )
        user.username = updates.username.lower().strip()

    if updates.bio is not None:
        # Strip whitespace but allow empty string to clear the bio
        user.bio = updates.bio.strip()

    db.commit()
    db.refresh(user)
    return user

