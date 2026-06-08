from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app.models.workout_log import WorkoutLog
from jose import JWTError, jwt
from app.routers.auth import get_user_by_email
import os
from app.workout_generator import generate_weekly_plan
from app.models.exercise import Exercise

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

    # Get all workout logs for this user
    logs = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == user.id
    ).order_by(WorkoutLog.date.desc()).all()

    log_dates = {log.date for log in logs}

    # Get the user's scheduled training days
    # e.g. "mon,wed,fri" becomes ["mon", "wed", "fri"]
    scheduled_days = []
    if user.training_days:
        scheduled_days = [d.strip() for d in user.training_days.split(",")]

    # Day name map — Python weekday() returns 0 for Monday
    day_map = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}

    # Calculate streak going backwards from today
    # Skip rest days — only break on missed scheduled days
    streak = 0
    check_date = today

    while True:
        day_name = day_map[check_date.weekday()]

        if day_name in scheduled_days:
            # This is a scheduled training day
            if check_date in log_dates:
                # Workout completed — keep streak going
                streak += 1
            elif check_date == today:
                # Today is a training day but not yet done — do not break streak
                # User might still do it today
                pass
            else:
                # Missed a scheduled training day — streak broken
                break
        # If it is a rest day — skip it and keep going back

        check_date -= timedelta(days=1)

        # Stop going back more than 365 days
        if (today - check_date).days > 365:
            break

    # Get completed days this week Mon to Sun
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

@router.get("/plan")
def get_workout_plan(token:str, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    # Make sure the user has completed onboarding
    if not user.goal or not user.fitness_level or not user.equipment or not user.training_days:
        raise HTTPException(
            status_code = 400,
            detail = "Please complete onboardng before generating a workout plan"
        )

    #clean up workout duration
    duration = user.workout_duration or "45"
    duration = duration.replace("+", "").strip()

    # Generate the weekly plan using the user's profile
    plan = generate_weekly_plan(
        db=db,
        goal = user.goal,
        fitness_level=user.fitness_level,
        equipment=user.equipment,
        training_days=user.training_days,
        workout_duration=duration,
    )

    # The paln return return exercise  IDs - we need to enrich them
    #with ful exercise details so the fronend can diplay them
    enriched_plan = {}

    for day, session in plan.items():

        #get full detail for each strength exercise
        exercises = []
        for ex_id in session["exercises"]:
            exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
            if exercise:
                exercises.append({
                    "id": exercise.id,
                    "name": exercise.name,
                    "muscle_group": exercise.muscle_group,
                    "equipment": exercise.equipment,
                    "sets_range": exercise.sets_range,
                    "reps_range": exercise.reps_range,
                    "is_timed": exercise.is_timed,
                    "seconds_range": exercise.seconds_range,
                    "video_url": exercise.video_url,
                    "description": exercise.description,
                    "instructions": exercise.instructions,
                    "coaching_cues": exercise.coaching_cues,
                })

        # get warmup details
        warmup = None
        if session["warmup"]:
            w = db.query(Exercise).filter(Exercise.id == session["warmup"]).first()
            if w:
                warmup = {
                    "id": w.id,
                    "name": w.name,
                    "is_timed": w.is_timed,
                    "seconds_range": w.seconds_range,
                    "instructions": w.instructions,
                }

        # Get finisher details
        finisher = None
        if session["finisher"]:
            f = db.query(Exercise).filter(Exercise.id == session["finisher"]).first()
            if f:
                finisher = {
                    "id": f.id,
                    "name": f.name,
                    "is_timed": f.is_timed,
                    "seconds_range": f.seconds_range,
                    "instructions": f.instructions,
                }

        # Get cardio circuit details if it exists
        cardio_circuit = None
        if session.get("cardio_circuit") and session["cardio_circuit"]["exercises"]:
            circuit_exercises = []
            for ex_id in session["cardio_circuit"]["exercises"]:
                exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
                if exercise:
                    circuit_exercises.append({
                        "id": exercise.id,
                        "name": exercise.name,
                        "is_timed": exercise.is_timed,
                        "seconds_range": exercise.seconds_range,
                        "instructions": exercise.instructions,
                    })
            cardio_circuit = {
                "exercises": circuit_exercises,
                "rounds": session["cardio_circuit"]["rounds"],
                "work_seconds": session["cardio_circuit"]["work_seconds"],
                "rest_seconds": session["cardio_circuit"]["rest_seconds"],
            }

        enriched_plan[day] = {
            "session_type": session["session_type"],
            "warmup": warmup,
            "exercises": exercises,
            "cardio_circuit": cardio_circuit,
            "finisher": finisher,
        }
    return enriched_plan


