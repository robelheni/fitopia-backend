from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app.models.workout_log import WorkoutLog
from jose import JWTError, jwt
from app.routers.auth import get_user_by_email
import os

router = APIRouter(prefix="/workouts", tags=["Workouts"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/complete")
def complete_workout(
    token: str,
    workout_name: str = "Today's workout",
    db: Session = Depends(get_db)
):
    user = get_user_from_token(token, db)
    today = date.today()

    # Day key
    day_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
    day_key = day_map[today.weekday()]

    # Check not already logged today
    existing = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == user.id,
        WorkoutLog.date == today
    ).first()

    if existing:
        return {"message": "Already completed today", "already_done": True}

    log = WorkoutLog(
        user_id=user.id,
        date=today,
        day_key=day_key,
        workout_name=workout_name
    )
    db.add(log)
    db.commit()

    return {"message": "Workout completed", "already_done": False}

@router.get("/streak")
def get_streak(token: str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    today = date.today()

    # Get all logs ordered by date descending
    logs = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == user.id
    ).order_by(WorkoutLog.date.desc()).all()

    # Calculate streak — consecutive days with a workout
    streak = 0
    check_date = today
    log_dates = {log.date for log in logs}

    # If no workout today check from yesterday
    if today not in log_dates:
        check_date = today - timedelta(days=1)

    while check_date in log_dates:
        streak += 1
        check_date -= timedelta(days=1)

    # Get completed days this week (Mon-Sun)
    week_start = today - timedelta(days=today.weekday())
    week_logs = [
        log for log in logs
        if log.date >= week_start and log.date <= today
    ]
    completed_days = [log.day_key for log in week_logs]

    return {
        "streak": streak,
        "completed_days": completed_days,
        "total_workouts": len(logs)
    }