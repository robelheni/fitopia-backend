from app.database import SessionLocal
from app.workout_generator import generate_weekly_plan

db = SessionLocal()

test_cases = [
    {
        "label": "6 days — gym — build muscle — advanced",
        "goal": "build_muscle",
        "fitness_level": "advanced",
        "equipment": "gym",
        "training_days": "mon,tue,wed,thu,fri,sat",
        "workout_duration": "80",
    },
    {
        "label": "4 days — bodyweight — lose weight — beginner",
        "goal": "lose_weight",
        "fitness_level": "beginner",
        "equipment": "bodyweight",
        "training_days": "mon,wed,fri,sat",
        "workout_duration": "30",
    },
    {
        "label": "3 days — gym — improve fitness — intermediate",
        "goal": "improve_fitness",
        "fitness_level": "intermediate",
        "equipment": "gym",
        "training_days": "tue,thu,sat",
        "workout_duration": "60",
    },
    {
        "label": "5 days — dumbbells — lose weight — intermediate",
        "goal": "lose_weight",
        "fitness_level": "intermediate",
        "equipment": "dumbbells",
        "training_days": "mon,tue,thu,fri,sat",
        "workout_duration": "45",
    },
    {
        "label": "2 days — bodyweight — stay active — beginner",
        "goal": "stay_active",
        "fitness_level": "beginner",
        "equipment": "bodyweight",
        "training_days": "sat,sun",
        "workout_duration": "30",
    },
    {
        "label": "4 days — both — build muscle — intermediate",
        "goal": "build_muscle",
        "fitness_level": "intermediate",
        "equipment": "both",
        "training_days": "mon,wed,fri,sun",
        "workout_duration": "60",
    },
]

for test in test_cases:
    print(f"\n{'='*60}")
    print(f"TEST: {test['label']}")
    print('='*60)

    plan = generate_weekly_plan(
        db=db,
        goal=test["goal"],
        fitness_level=test["fitness_level"],
        equipment=test["equipment"],
        training_days=test["training_days"],
        workout_duration=test["workout_duration"],
    )

    for day, session in plan.items():
        print(f"\n{day.upper()} — {session['session_type']}")
        print(f"  Warmup: {session['warmup']}")
        print(f"  Exercises: {session['exercises']}")
        if session.get('cardio_circuit'):
            circuit = session['cardio_circuit']
            print(f"  Cardio Circuit: {circuit['exercises']}")
            print(f"  Rounds: {circuit['rounds']} | Work: {circuit['work_seconds']}s | Rest: {circuit['rest_seconds']}s")
        print(f"  Finisher: {session['finisher']}")

db.close()