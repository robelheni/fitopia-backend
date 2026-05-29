from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt 
from passlib.context import CryptContext
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token, TokenData 
from dotenv import load_dotenv
import os 
import random
import string

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

def get_user_by_email(db: Session, email:str):
    """Find a user by their email"""
    return db.query(User).filter(User.email == email).first()


# ─── Endpoints ──────────────────────────────────────────────────────

@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db:Session = Depends(get_db)):

    #check if email already exists
    existing_user = get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail = "An account with email already exists"
        )

    hashed= hash_password(user.password)

    referral = generate_referral_code(user.name)

    #create the user
    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hashed,
        referral_code=referral,
        referred_by=user.referral_code
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post("/login", response_model = Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):

    user = get_user_by_email(db, credentials.email)

    #check user exists and password is correct
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers = {"WWW-Authenticate": "Bearer"},
        )

    #create JWT token
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
