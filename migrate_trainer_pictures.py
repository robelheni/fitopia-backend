"""
Adds profile_picture and transformation_pictures columns to trainer_applications.

Run once in Railway console:
    python migrate_trainer_pictures.py
"""
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    for col, typ in [
        ("profile_picture",         "VARCHAR"),
        ("transformation_pictures", "TEXT"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE trainer_applications ADD COLUMN {col} {typ};"
            ))
            conn.commit()
            print(f"✓ Added {col}")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print(f"  {col} already exists — skipping")
            else:
                raise
