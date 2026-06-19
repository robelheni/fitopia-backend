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

@router.get("/year-stats")
def get_year_stats(token: str, year: int, db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    logs = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == user.id,
    ).all()

    completed = [
        {
            "date": log.date.isoformat(),
            "workout_name": log.workout_name,
        }
        for log in logs
        if log.date.year == year
    ]

    training_days = []
    if user.training_days:
        training_days = [d.strip() for d in user.training_days.split(",")]
        
    return {
        "year": year,
        "completed_dates": year_dates,
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
    equipment_list: str = None,
    difficulty: str = None,
    movement_pattern: str = None,
    db: Session = Depends(get_db)
):
    # Base query — exclude warmups, finishers and bad muscle group values
    query = db.query(Exercise).filter(
        ~Exercise.muscle_group.in_(["warmup", "finisher", "beginner", "compound"])
    )

    # muscle_group accepts comma-separated list e.g. "chest,shoulders,triceps"
    if muscle_group:
        groups = [g.strip() for g in muscle_group.split(",")]
        query = query.filter(Exercise.muscle_group.in_(groups))

    # equipment_list accepts multiple e.g. "bodyweight,dumbbells"
    if equipment_list:
        equip = [e.strip() for e in equipment_list.split(",")]
        query = query.filter(Exercise.equipment.in_(equip))
    elif equipment:
        query = query.filter(Exercise.equipment == equipment)

    # difficulty filter e.g. "beginner" for fasting workouts
    if difficulty:
        query = query.filter(Exercise.difficulty == difficulty)

    # movement_pattern accepts comma-separated list
    if movement_pattern:
        patterns = [p.strip() for p in movement_pattern.split(",")]
        query = query.filter(Exercise.movement_pattern.in_(patterns))

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
            "difficulty": ex.difficulty,
            "sets_range": ex.sets_range,
            "reps_range": ex.reps_range,
            "is_timed": ex.is_timed,
            "seconds_range": ex.seconds_range,
            "description": ex.description,
            "instructions": ex.instructions,
            "video_url": ex.video_url,
        }
        for ex in exercises
    ]
    
@router.get("/category-plan")
def get_category_plan(
    token: str,
    category: str,
    db: Session = Depends(get_db)
):
    user = get_user_from_token(token, db)
    fitness_level = user.fitness_level or "intermediate"

    difficulty_map = {
        "beginner":     ["beginner"],
        "intermediate": ["beginner", "intermediate"],
        "advanced":     ["beginner", "intermediate", "advanced"],
    }
    allowed_difficulties = difficulty_map.get(fitness_level, ["beginner", "intermediate"])

    # ── LIGHT FULL BODY — special logic ───────────────────
    # Picks exactly 1 exercise per muscle group, bodyweight only, beginner only
    # This gives a structured full body workout, not a random list
    if category == "light-full-body":
        target_muscles = ["chest", "back", "shoulders", "biceps", "triceps", "core"]
        result = []

        for muscle in target_muscles:
            # Pick the best (priority=1) beginner bodyweight exercise for this muscle
            exercise = db.query(Exercise).filter(
                Exercise.muscle_group == muscle,
                Exercise.equipment == "bodyweight",
                Exercise.difficulty == "beginner",
            ).order_by(Exercise.priority).first()

            # If no bodyweight found, try bands
            if not exercise:
                exercise = db.query(Exercise).filter(
                    Exercise.muscle_group == muscle,
                    Exercise.equipment == "bands",
                    Exercise.difficulty == "beginner",
                ).order_by(Exercise.priority).first()

            if exercise:
                # Light full body uses reduced sets — 2 instead of normal 3-4
                sets = 2
                reps = exercise.reps_range[0] if exercise.reps_range else 10
                seconds = exercise.seconds_range[0] if exercise.seconds_range else 30

                result.append({
                    "id": exercise.id,
                    "name": exercise.name,
                    "muscle_group": exercise.muscle_group,
                    "equipment": exercise.equipment,
                    "difficulty": exercise.difficulty,
                    "sets": sets,
                    "reps": reps if not exercise.is_timed else None,
                    "seconds": seconds if exercise.is_timed else None,
                    "is_timed": exercise.is_timed,
                    "instructions": exercise.instructions or [],
                    "coaching_cues": exercise.coaching_cues or [],
                    "video_url": exercise.video_url or "",
                    "movement_pattern": exercise.movement_pattern,
                })

        return {"category": category, "fitness_level": fitness_level, "exercises": result}

    # ── ALL OTHER CATEGORIES ───────────────────────────────
    category_config = {
        # HOME
        "full-body-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["chest", "back", "legs", "shoulders", "triceps", "biceps", "core"],
            "limit": 8,
        },
        "upper-body-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["chest", "back", "shoulders", "biceps", "triceps"],
            "limit": 8,
        },
        "lower-body-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["legs", "glutes", "hamstrings", "calves"],
            "limit": 8,
        },
        "core-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["core"],
            "limit": 6,
        },
        "biceps-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["biceps"],
            "limit": 6,
        },
        "triceps-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["triceps"],
            "limit": 6,
        },
        "cardio-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["cardio"],
            "limit": 6,
            "patterns":  ["low_impact", "low_impact_cardio", "steady_state"],
        },
        "intense-cardio-home": {
            "equipment": ["bodyweight", "dumbbells", "bands"],
            "muscles":   ["cardio"],
            "limit": 6,
            "patterns":  ["full_body_cardio", "intervals", "conditioning", "core_cardio"],
        },

        # GYM
        "chest-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["chest"],
            "limit": 6,
        },
        "back-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["back"],
            "limit": 6,
        },
        "shoulders-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["shoulders"],
            "limit": 6,
        },
        "triceps-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["triceps"],
            "limit": 6,
        },
        "biceps-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["biceps"],
            "limit": 6,
        },
        "legs-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["legs", "glutes", "hamstrings", "calves"],
            "limit": 8,
        },
        "core-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["core"],
            "limit": 6,
            # No difficulty filter for gym core — show all levels
            "ignore_difficulty": True,
        },
        "cardio-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["cardio"],
            "limit": 6,
            "patterns":  ["low_impact", "low_impact_cardio", "steady_state"],
        },
        "intense-cardio-gym": {
            "equipment": ["gym", "bodyweight"],
            "muscles":   ["cardio"],
            "limit": 6,
            "patterns":  ["full_body_cardio", "intervals", "conditioning", "core_cardio"],
        },
    }

    config = category_config.get(category)
    if not config:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")

    # ignore_difficulty means show all difficulty levels — used for gym core
    # so we don't block advanced exercises from showing
    difficulties = allowed_difficulties if not config.get("ignore_difficulty") else ["beginner", "intermediate", "advanced"]

    query = db.query(Exercise).filter(
        Exercise.muscle_group.in_(config["muscles"]),
        Exercise.equipment.in_(config["equipment"]),
        Exercise.difficulty.in_(difficulties),
    )

    # Apply movement pattern filter for cardio categories
    if "patterns" in config:
        query = query.filter(Exercise.movement_pattern.in_(config["patterns"]))

    exercises = query.order_by(
        Exercise.priority,
        Exercise.muscle_group,
    ).limit(config["limit"]).all()

    result = []
    for ex in exercises:
        sets = ex.sets_range[0] if ex.sets_range else 3
        reps = ex.reps_range[0] if ex.reps_range else 10
        seconds = ex.seconds_range[0] if ex.seconds_range else 30

        result.append({
            "id": ex.id,
            "name": ex.name,
            "muscle_group": ex.muscle_group,
            "equipment": ex.equipment,
            "difficulty": ex.difficulty,
            "sets": sets,
            "reps": reps if not ex.is_timed else None,
            "seconds": seconds if ex.is_timed else None,
            "is_timed": ex.is_timed,
            "instructions": ex.instructions or [],
            "coaching_cues": ex.coaching_cues or [],
            "video_url": ex.video_url or "",
            "movement_pattern": ex.movement_pattern,
        })

    return {"category": category, "fitness_level": fitness_level, "exercises": result}

@router.get("/quote")
def get_motivational_quote(
    token: str,
    workout_name: str = "workout",
    db: Session = Depends(get_db)
):
    """
    Generates a powerful personalised post-workout quote using OpenAI.
    
    The quote is written specifically for this moment — after this workout,
    for this goal. It should feel earned, not generic.
    
    Design decision: We use OpenAI to generate original quotes rather than
    pulling from a hardcoded list. This means every completion feels unique
    and personal. The quote is attributed to Fitopia so we never misrepresent
    real people.
    
    Falls back to a default quote if OpenAI is unavailable.
    """
    import random

    user = get_user_from_token(token, db)

    openai_key = os.getenv("OPENAI_API_KEY")

    # If no API key is configured return a solid default rather than crashing
    if not openai_key:
        return {
            "text": "You didn't come this far to only come this far. Every set you completed today is proof of who you are becoming.",
            "author": "Fitopia"
        }

    try:
        client = openai.OpenAI(api_key=openai_key)

        # Map internal goal keys to natural English phrases for the prompt
        # This makes the generated quote feel relevant to what the user is working towards
        goal_labels = {
            "build_muscle": "build muscle and get stronger",
            "lose_weight": "lose weight and burn fat",
            "improve_fitness": "improve their overall fitness",
            "stay_active": "stay active and healthy",
        }
        goal = goal_labels.get(user.goal, "reach their fitness goals")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    # We tell OpenAI to act as a coach who truly understands
                    # the emotional high of finishing a hard workout.
                    # The quote should feel like it was written for THIS person
                    # at THIS exact moment — not a generic motivational poster.
                    # We attribute it to Fitopia so we never fake real people's words.
                    "content": """You are a world-class fitness coach and motivational writer.
Your job is to write a single powerful post-workout quote that makes someone feel incredible after finishing their session.

The quote must:
- Feel personal and earned — like it was written specifically for this moment
- Be emotionally powerful and inspiring
- Relate directly to the effort of completing a workout
- Be 1-3 sentences maximum
- Sound like something a great coach would say to you after a hard session
- NOT be generic or cliche
- NOT reference specific exercises or equipment

Always attribute the quote to "Fitopia".

Return JSON only: { "text": "...", "author": "Fitopia" }"""
                },
                {
                    "role": "user",
                    # Pass the specific workout and goal context so the quote
                    # feels tailored to what this person just accomplished
                    "content": f"Write a post-workout quote for someone who just completed a {workout_name} session. Their goal is to {goal}. Make it feel powerful and earned. Return JSON only."
                }
            ],
            max_tokens=150,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return {
            "text": result.get("text", "You showed up. You did the work. That is what separates you."),
            "author": result.get("author", "Fitopia")
        }

    except Exception as e:
        # Log the error in Railway so we can debug if needed
        print(f"OpenAI quote error: {e}")
        # Return a strong default so the completion screen never looks broken
        fallbacks = [
            "You didn't come this far to only come this far. Every set today is proof of who you are becoming.",
            "You showed up. You did the work. That is what separates you.",
            "The person you are becoming is worth every rep, every drop of sweat, every hard day.",
            "Today you chose discipline over comfort. That choice compounds every single day.",
            "Your body heard you today. It got stronger. So did your mind.",
        ]
        return {
            "text": random.choice(fallbacks),
            "author": "Fitopia"
        }

