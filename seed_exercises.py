import json
import os
import sys 

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models.exercise import Exercise
from app.database import Base

Base.metadata.create_all(bind=engine)

def seed_exercises():
    db = SessionLocal()

    try:
        existing = db.query(Exercise).count()
        if existing > 0:
            print(f"Exercises already seeded — {existing} exercises in database")
            return

        with open("data/exercises.json" , "r") as f:
            data = json.load(f)

        exercises = data["exercises"]
        count = 0

        for ex in exercises:
            exercise = Exercise(
                id=ex["id"],
                name=ex["name"],
                muscle_group=ex["muscle_group"],
                secondary_muscles=ex.get("secondary_muscles", []),
                equipment=ex["equipment"],
                difficulty=ex["difficulty"],
                injury_flags=ex.get("injury_flags", []),
                goal_tags=ex.get("goal_tags", []),
                priority=ex.get("priority"),
                movement_pattern=ex.get("movement_pattern"),
                duration_weight=ex.get("duration_weight"),
                sets_range=ex.get("sets_range"),
                reps_range=ex.get("reps_range"),
                is_timed=ex.get("isTimed", False),
                seconds_range=ex.get("seconds_range"),
                video_url=ex.get("video_url", ""),
                description=ex.get("description", ""),
                instructions=ex.get("instructions", []),
                coaching_cues=ex.get("coaching_cues", [])
            )
            db.add(exercise)
            count +=1

        db.commit()
        print(f"Successfully seeded {count} exercises")

    except Exception as e:
        db.rollback()
        print(f"Error seeding exercises: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    seed_exercises()