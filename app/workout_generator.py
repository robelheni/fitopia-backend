import random
from sqlalchemy.orm import Session
from app.models.exercise import Exercise

# For muscles that get two exercises
# this forces the second pick to be a specific pattern
# so we never get two of the same movement type
second_pick_pattern = {
    "chest":      "fly",
    "back":       "hinge",
    "legs":       "lunge",
    "glutes":     "kickback",
    "triceps":    "extension",
    "biceps":     "isolation_curl",
    "shoulders":  "lateral_raise",
}

def get_weekly_split(days_per_week: int) -> list:
    splits = {
        2: ["full_body", "full_body"],
        3: ["push", "pull", "legs"],
        4: ["upper", "lower", "upper", "lower"],
        5: ["push", "pull", "legs", "upper", "lower"],
        6: ["push", "pull", "legs", "push", "pull", "legs"],
    }
    return splits.get(days_per_week, ["full_body"])


def get_cardio_circuit(
    db: Session,
    goal: str,
    equipment: str,
    fitness_level: str,
    used_cardio: list = []
) -> dict:
    """
    Builds a dedicated cardio circuit for lose_weight, improve_fitness
    and stay_active users. Returns a structured circuit with exercises,
    rounds and timing. Gym users get machine based cardio.
    Home users get intense bodyweight circuit.
    """

    # Cardio patterns by goal
    cardio_patterns_by_goal = {
        "lose_weight":     ["full_body_cardio", "intervals", "conditioning", "core_cardio"],
        "improve_fitness": ["full_body_cardio", "intervals", "conditioning", "core_cardio", "low_impact_cardio"],
        "stay_active":     ["low_impact_cardio", "steady_state", "full_body_cardio"],
        "build_muscle":    ["full_body_cardio", "low_impact_cardio"],
    }

    # Circuit intensity by goal
    circuit_config = {
        "lose_weight":     {"rounds": 5, "work_seconds": 40, "rest_seconds": 15},
        "improve_fitness": {"rounds": 4, "work_seconds": 35, "rest_seconds": 20},
        "stay_active":     {"rounds": 3, "work_seconds": 30, "rest_seconds": 30},
        "build_muscle":    {"rounds": 3, "work_seconds": 30, "rest_seconds": 30},
    }

    equipment_filter = {
        "gym":        ["gym", "bodyweight"],
        "dumbbells":  ["dumbbells", "bodyweight"],
        "bodyweight": ["bodyweight"],
        "both":       ["gym", "dumbbells", "bodyweight"],
    }
    allowed_equipment = equipment_filter.get(equipment, ["bodyweight"])

    difficulty_map = {
        "beginner":     ["beginner"],
        "intermediate": ["beginner", "intermediate"],
        "advanced":     ["beginner", "intermediate", "advanced"],
    }
    allowed_difficulties = difficulty_map.get(fitness_level, ["beginner"])

    preferred_patterns = cardio_patterns_by_goal.get(goal, ["full_body_cardio"])

    # Query cardio exercises matching filters
    candidates = db.query(Exercise).filter(
        Exercise.muscle_group == "cardio",
        Exercise.equipment.in_(allowed_equipment),
        Exercise.difficulty.in_(allowed_difficulties),
        Exercise.movement_pattern.in_(preferred_patterns)
    ).all()

    # Remove cardio already used this week for variety
    # If all used this week allow repeats — start from beginning
    if used_cardio:
        fresh = [ex for ex in candidates if ex.id not in used_cardio]
        if fresh:
            candidates = fresh
        # If all cardio exhausted — reset and use full list again

    # Shuffle for variety
    random.shuffle(candidates)

    # Pick 3 to 4 exercises for the circuit
    # Home users get 4 exercises — more variety needed for bodyweight
    # Gym users get 3 — machines are longer duration
    circuit_size = 4 if equipment in ["bodyweight", "dumbbells"] else 3
    circuit_exercises = candidates[:circuit_size]

    config = circuit_config.get(goal, {"rounds": 4, "work_seconds": 40, "rest_seconds": 20})

    return {
        "exercises": [ex.id for ex in circuit_exercises],
        "rounds": config["rounds"],
        "work_seconds": config["work_seconds"],
        "rest_seconds": config["rest_seconds"],
    }


def get_exercises_for_session(
    db: Session,
    session_type: str,
    equipment: str,
    fitness_level: str,
    goal: str,
    duration: int,
    previous_exercises: list = [],
) -> list:
    """
    Returns strength exercises for a session.
    Cardio is handled separately by get_cardio_circuit.
    Injuries removed — handled via disclaimer on frontend.
    """

    # Clean session muscle map — same for all goals
    # Core added to pull to fill out bodyweight pull sessions
    session_muscle_map = {
        "push":      ["chest", "chest", "shoulders", "shoulders", "triceps", "triceps"],
        "pull":      ["back", "back", "back", "biceps", "biceps", "core"],
        "legs":      ["legs", "legs", "hamstrings", "glutes", "calves", "core"],
        "upper":     ["chest", "chest", "back", "back", "shoulders", "triceps", "biceps"],
        "lower":     ["legs", "legs", "hamstrings", "glutes", "calves", "core"],
        "full_body": ["chest", "back", "legs", "shoulders", "triceps", "biceps", "core"],
    }

    target_muscles = session_muscle_map.get(session_type, ["chest"])

    equipment_filter = {
        "gym":        ["gym", "bodyweight"],
        "dumbbells":  ["dumbbells", "bodyweight"],
        "bodyweight": ["bodyweight"],
        "both":       ["gym", "dumbbells", "bodyweight"],
    }
    allowed_equipment = equipment_filter.get(equipment, ["gym"])

    difficulty_map = {
        "beginner":     ["beginner"],
        "intermediate": ["beginner", "intermediate"],
        "advanced":     ["beginner", "intermediate", "advanced"],
    }
    allowed_difficulties = difficulty_map.get(fitness_level, ["beginner"])

    # Exercises per session based on fitness level and duration
    # Beginners get fewer exercises regardless of equipment
    if fitness_level == "beginner":
        if duration <= 30:
            exercises_per_session = 4
        elif duration <= 45:
            exercises_per_session = 5
        elif duration <= 60:
            exercises_per_session = 6
        else:
            exercises_per_session = 7
    elif equipment == "bodyweight":
        # Bodyweight intermediate and advanced get more — shorter rest periods
        if duration <= 30:
            exercises_per_session = 6
        elif duration <= 45:
            exercises_per_session = 7
        elif duration <= 60:
            exercises_per_session = 8
        else:
            exercises_per_session = 10
    else:
        if duration <= 30:
            exercises_per_session = 4
        elif duration <= 45:
            exercises_per_session = 5
        elif duration <= 60:
            exercises_per_session = 7
        else:
            exercises_per_session = 8

    selected_exercises = []
    used_patterns = []
    muscle_count = {}

    for muscle in target_muscles:

        if len(selected_exercises) >= exercises_per_session:
            break

        # Track how many times this muscle has been picked
        muscle_count[muscle] = muscle_count.get(muscle, 0) + 1
        is_second_pick = muscle_count[muscle] == 2

        # Query exercises matching all filters
        candidates = db.query(Exercise).filter(
            Exercise.muscle_group == muscle,
            Exercise.equipment.in_(allowed_equipment),
            Exercise.difficulty.in_(allowed_difficulties),
        ).all()

        # Skip this muscle if no candidates
        if not candidates:
            continue

        # Remove exercises used in the previous session of same type
        # If all exercises used — reset and allow repeats
        if previous_exercises:
            filtered = [
                ex for ex in candidates
                if ex.id not in previous_exercises
            ]
            # If filtered list is not empty use it
            # Otherwise reset — start from the beginning again
            if filtered:
                candidates = filtered

        # Second pick logic — force a different movement pattern
        # Only for gym and dumbbell users — bodyweight skips this
        if is_second_pick and equipment != "bodyweight":
            forced_pattern = second_pick_pattern.get(muscle)
            if forced_pattern:
                forced_candidates = [
                    ex for ex in candidates
                    if ex.movement_pattern == forced_pattern
                    and ex not in selected_exercises
                ]
                if forced_candidates:
                    chosen = select_by_pattern(forced_candidates, [], selected_exercises)
                else:
                    chosen = select_by_pattern(candidates, used_patterns, selected_exercises)
            else:
                chosen = select_by_pattern(candidates, used_patterns, selected_exercises)
        else:
            if equipment == "bodyweight":
                # Bodyweight ignores pattern tracking — not enough variety
                chosen = select_by_pattern(candidates, [], selected_exercises)
            else:
                chosen = select_by_pattern(candidates, used_patterns, selected_exercises)

        if chosen and chosen not in selected_exercises:
            selected_exercises.append(chosen)
            # Only track patterns for gym and dumbbell users
            if equipment != "bodyweight":
                used_patterns.append(chosen.movement_pattern)

    return selected_exercises


def select_by_pattern(candidates: list, used_patterns: list, exclude_exercises: list = []):
    """
    Pick the highest priority exercise that uses a movement pattern
    not already in this session. Priority 1 beats 2 beats 3.
    """
    candidates_sorted = sorted(candidates, key=lambda x: x.priority or 99)

    for exercise in candidates_sorted:
        # Skip if already selected in this session
        if exercise in exclude_exercises:
            continue
        # Skip if movement pattern already used this session
        if exercise.movement_pattern in used_patterns:
            continue
        return exercise

    return None


def generate_weekly_plan(
    db: Session,
    goal: str,
    fitness_level: str,
    equipment: str,
    training_days: str,
    workout_duration: str,
) -> dict:
    """
    Takes the full user profile from onboarding and returns
    a complete weekly workout plan. Each day has a strength
    block and optionally a cardio circuit depending on goal.
    Injuries removed — handled via disclaimer on frontend.
    """

    # Convert training days string to list
    days_list = [d.strip() for d in training_days.split(",") if d.strip()]

    # Convert duration to integer
    duration = int(workout_duration) if workout_duration else 45

    days_count = len(days_list)
    split = get_weekly_split(days_count)

    weekly_plan = {}

    # Track exercises used per session type for variety
    previous_session_exercises = {}

    # Track cardio exercises used across all sessions this week
    used_cardio_this_week = []

    for i, day in enumerate(days_list):

        session_type = split[i]
        previous = previous_session_exercises.get(session_type, [])

        # Get strength exercises for this session
        exercises = get_exercises_for_session(
            db=db,
            session_type=session_type,
            equipment=equipment,
            fitness_level=fitness_level,
            goal=goal,
            duration=duration,
            previous_exercises=previous,
        )

        # Save exercises for variety on next same session type
        previous_session_exercises[session_type] = [ex.id for ex in exercises]

        # Rotate warmup based on day index
        warmups = db.query(Exercise).filter(
            Exercise.muscle_group == "warmup"
        ).all()
        warmup = warmups[i % len(warmups)] if warmups else None

        # Build cardio circuit for lose_weight improve_fitness and stay_active
        # Build muscle skips the circuit
        cardio_circuit = None
        if goal in ["lose_weight", "improve_fitness", "stay_active"]:
            cardio_circuit = get_cardio_circuit(
                db=db,
                goal=goal,
                equipment=equipment,
                fitness_level=fitness_level,
                used_cardio=used_cardio_this_week,
            )
            # Track cardio used this week for variety
            if cardio_circuit:
                for ex_id in cardio_circuit["exercises"]:
                    if ex_id not in used_cardio_this_week:
                        used_cardio_this_week.append(ex_id)

        # Pick finisher based on goal
        if goal == "lose_weight":
            finisher = db.query(Exercise).filter(
                Exercise.muscle_group == "finisher",
                Exercise.movement_pattern == "full_body_cardio"
            ).first()
        elif goal == "improve_fitness":
            # Alternate between cardio and stability finishers
            if i % 2 == 0:
                finisher = db.query(Exercise).filter(
                    Exercise.muscle_group == "finisher",
                    Exercise.movement_pattern == "full_body_cardio"
                ).first()
            else:
                finisher = db.query(Exercise).filter(
                    Exercise.muscle_group == "finisher",
                    Exercise.movement_pattern == "stability"
                ).first()
        else:
            # Build muscle and stay active — stability finisher
            finisher = db.query(Exercise).filter(
                Exercise.muscle_group == "finisher",
                Exercise.movement_pattern == "stability"
            ).first()

        weekly_plan[day] = {
            "session_type": session_type,
            "warmup": warmup.id if warmup else None,
            "exercises": [ex.id for ex in exercises],
            "cardio_circuit": cardio_circuit,
            "finisher": finisher.id if finisher else None,
        }

    return weekly_plan