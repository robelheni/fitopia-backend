from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.database import get_db
from app.models.workout_log import WorkoutLog
from jose import JWTError, jwt
from app.routers.auth import get_user_by_email
import os
import openai
import json
from app.workout_generator import generate_weekly_plan
from app.models.exercise import Exercise
from app.models.liked_exercise import LikedExercise

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


@router.get("/swap/{exercise_id}")
def get_swap_options(
    exercise_id: str,
    token: str,
    # Comma separated list of exercise IDs already in the session

    session_exercises: str = "",
    db: Session = Depends(get_db)
):
    """
    Returns alternative exercises for a given exercise ID.
    Matches by movement pattern so the swap respects training intent.
    A chest press only swaps with another press.
    A back row only swaps with another row.
    """

    user = get_user_from_token(token, db)

    #step 1 - Get the exercise the user wants to swap
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code = 404, detail="Exercise not found")

    #step 2 - Get the movement pattern and muscle group
    movement_pattern = exercise.movement_pattern
    muscle_group = exercise.muscle_group

    #step 3 - Build the equipment filter from the user's profile
    equipment_filter = {
        "gym":        ["gym", "bodyweight"],
        "dumbbells":  ["dumbbells", "bodyweight"],
        "bodyweight": ["bodyweight"],
        "both":       ["gym", "dumbbells", "bodyweight"],
    }
    allowed_equipment = equipment_filter.get(user.equipment, ["gym"])

    #exclude the exercise that are already in the workout so we do not want to suggest them
    exclude_ids = []
    if session_exercises:
        exclude_ids = [e.strip() for e in session_exercises.split(",")]

    #Always exclude the exercise being swapped itself
    exclude_ids.append(exercise_id)
    #Query alternatives maching the same movement pattern
    alternatives = db.query(Exercise).filter(
        Exercise.movement_pattern == movement_pattern,
        Exercise.muscle_group == muscle_group,
        Exercise.equipment.in_(allowed_equipment),
        
        ~Exercise.id.in_(exclude_ids)

    ).order_by(Exercise.priority).limit(5).all()

    #If no alternatives found the sme pattern
    if not alternatives:
        alternatives = db.query(Exercise).filter(
            Exercise.muscle_group == muscle_group,
            Exercise.equipment.in_(allowed_equipment),
            
            ~Exercise.id.in_(exclude_ids)
        ).order_by(Exercise.priority).limit(5).all()

    return [
        {
            "id": ex.id,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "movement_pattern": ex.movement_pattern,
            "equipment": ex.equipment,
            "sets_range": ex.sets_range,
            "reps_range": ex.reps_range,
            "is_timed": ex.is_timed,
            "seconds_range": ex.seconds_range,
            "description": ex.description,
            "instructions": ex.instructions,
            "coaching_cues": ex.coaching_cues,
            "video_url": ex.video_url,

        }
        for ex in alternatives
    ]





@router.post("/like/{exercise_id}")
def toggle_like_exercise(
    exercise_id: str,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Toggles the like status of an exercise for the current user.
    If the exercise is not liked — likes it.
    If the exercise is already liked — unlikes it.
    This way one endpoint handles both actions.
    """

    user = get_user_from_token(token, db)

    # check id the exercise exists
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    #check if already liked
    existing = db.query(LikedExercise).filter(
        LikedExercise.user_id ==user.id,
        LikedExercise.exercise_id == exercise_id
    ).first()

    if existing:
        #Already liked - remove it
        db.delete(existing)
        db.commit()
        return {"liked": False, "message": f"{exercise.name} removed from favourites"}
    else:
        #Not liked yet - add it
        like = LikedExercise(
            user_id = user.id,
            exercise_id=exercise_id
        )
        db.add(like)
        db.commit()
        return {"liked": True, "message": f"{exercise.name} added to favourites"}


@router.get("/liked")
def get_liked_exercises(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Returns all exercises the user has liked.
    Used to populate the favourites screen on the frontend.
    """
    user = get_user_from_token(token, db)

    #get all liked exercises IDs for this user
    liked = db.query(LikedExercise).filter(
        LikedExercise.user_id == user.id
    ).order_by(LikedExercise.liked_at.desc()).all()

    result =[]
    for like in liked:
        exercise = db.query(Exercise).filter(
            Exercise.id ==like.exercise_id
        ).first()
        if exercise:
            result.append({
                "id": exercise.id,
                "name": exercise.name,
                "muscle_group": exercise.muscle_group,
                "equipment": exercise.equipment,
                "movement_pattern": exercise.movement_pattern,
                "sets_range": exercise.sets_range,
                "reps_range": exercise.reps_range,
                "is_timed": exercise.is_timed,
                "seconds_range": exercise.seconds_range,
                "description": exercise.description,
                "instructions": exercise.instructions,
                "coaching_cues": exercise.coaching_cues,
                "video_url": exercise.video_url,
                "liked_at": like.liked_at,
            })
    return result


@router.get("/like/{exercise_id}/status")
def get_like_status(
    exercise_id: str,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Returns whether the current user has liked a specific exercise.
    Called when the exercise detail screen loads so the frontend
    knows whether to show a filled or empty heart icon.
    """
    user = get_user_from_token(token, db)

    # Check if this exercise is liked by the current user
    existing = db.query(LikedExercise).filter(
        LikedExercise.user_id == user.id,
        LikedExercise.exercise_id == exercise_id
    ).first()

    return {"liked": existing is not None}


@router.get("/exercise/{exercise_id}")
def get_exercise(
    exercise_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns full details for a single exercise by ID.
    Called when a user taps an exercise to see the detail screen.
    Video, instructions, coaching cues, sets and reps all returned here.
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    return {
        "id": exercise.id,
        "name": exercise.name,
        "muscle_group": exercise.muscle_group,
        "equipment": exercise.equipment,
        "movement_pattern": exercise.movement_pattern,
        "priority": exercise.priority,
        "sets_range": exercise.sets_range,
        "reps_range": exercise.reps_range,
        "is_timed": exercise.is_timed,
        "seconds_range": exercise.seconds_range,
        "description": exercise.description,
        "instructions": exercise.instructions,
        "coaching_cues": exercise.coaching_cues,
        "video_url": exercise.video_url,
    }


@router.get("/exercises")
def get_all_exercises(
    muscle_group: str = None,
    equipment: str = None,
    db: Session = Depends(get_db)
):
    """
    Returns exercises from the database with optional filters.
    Warmups and finishers are excluded — those are internal only.
    Used for the workout library browser on the frontend.

    Examples:
    /workouts/exercises — all exercises
    /workouts/exercises?muscle_group=chest — chest only
    /workouts/exercises?muscle_group=chest&equipment=gym — gym chest only
    """

    # Base query — exclude warmups and finishers
    query = db.query(Exercise).filter(
        ~Exercise.muscle_group.in_(["warmup", "finisher"])
    )

    # Apply muscle group filter if provided
    if muscle_group:
        query = query.filter(Exercise.muscle_group == muscle_group)

    # Apply equipment filter if provided
    if equipment:
        query = query.filter(Exercise.equipment == equipment)

    # Order by muscle group then priority — best exercises first
    exercises = query.order_by(
        Exercise.muscle_group,
        Exercise.priority
    ).all()

    return [
        {
            "id": ex.id,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "equipment": ex.equipment,
            "movement_pattern": ex.movement_pattern,
            "sets_range": ex.sets_range,
            "reps_range": ex.reps_range,
            "is_timed": ex.is_timed,
            "seconds_range": ex.seconds_range,
            "description": ex.description,
            "video_url": ex.video_url,
        }
        for ex in exercises
    ]


@router.get("/quote")
def get_motivational_quote(
    token: str,
    workout_name: str = "workout",
    db: Session = Depends(get_db)
):
    """
    Calls OpenAI to generate a fresh motivational quote after workout completion.
    The quote is drawn from real Ethiopian and Eritrean figures and proverbs.
    Falls back to a default quote if OpenAI is unavailable.
    """
    user = get_user_from_token(token, db)

    openai_key = os.getenv("OPENAI_API_KEY")

    # If no API key is set, return a default quote rather than crashing
    if not openai_key:
        return {"text": "The work never lies. Every rep counts.", "author": "Fitopia"}

    try:
        client = openai.OpenAI(api_key=openai_key)

        # Map internal goal keys to readable English for the prompt
        goal_labels = {
            "build_muscle": "build muscle",
            "lose_weight": "lose weight",
            "improve_fitness": "improve fitness",
            "stay_active": "stay active",
        }
        goal = goal_labels.get(user.goal, "get fit")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    # We ask OpenAI to only return REAL documented quotes.
                    # This keeps the app honest — real quotes feel more powerful
                    # than invented ones. If OpenAI is unsure a quote is real
                    # it should fall back to a proverb which is always safe.
                    "content": """You are a quote retrieval assistant.

Return only authentic, historically documented quotations from the listed Ethiopian and Eritrean figures or from well-known Ethiopian or Eritrean proverbs.

Do NOT create, rewrite, paraphrase, modernize, summarize, or invent quotes.
Do NOT generate quotes inspired by these figures.
If you are not confident that a quote is authentic and publicly attributed to the selected figure, choose another figure or proverb instead.

Prefer short motivational quotes that relate to discipline, perseverance, leadership, excellence, resilience, or achievement.

Possible sources include:
Haile Gebrselassie, Abebe Bikila, Tirunesh Dibaba, Kenenisa Bekele,
Emperor Haile Selassie, Emperor Menelik II, Taytu Betul,
Alula Aba Nega, Afewerk Tekle, Tsegaye Gabre-Medhin,
Bewketu Seyoum, Haddis Alemayehu, Birhanu Zerihun,
Sahle-Work Zewde, Ethiopian Proverbs, and Eritrean Proverbs.

Return JSON only: { "text": "...", "author": "..." }"""
                },
                {
                    "role": "user",
                    # Pass workout context so the quote feels relevant to what was just completed
                    "content": f"Return an authentic quote relevant to someone who completed a {workout_name} session with the goal to {goal}. Use only a real documented quotation or proverb. Return JSON only."
                }
            ],
            max_tokens=150,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "text": result.get("text", "Keep pushing. Every session counts."),
            "author": result.get("author", "Fitopia")
        }

    except Exception as e:
        # Log the error so we can debug it in Railway logs
        print(f"OpenAI error: {e}")
        return {
            "text": "The work never lies. Every rep counts.",
            "author": "Fitopia"
        }
