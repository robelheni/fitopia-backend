"""
Adds whatsapp column to trainer_applications.

Run once in Railway console:
    python migrate_whatsapp_column.py
"""
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text(
            "ALTER TABLE trainer_applications ADD COLUMN whatsapp VARCHAR;"
        ))
        conn.commit()
        print("✓ Added whatsapp column to trainer_applications")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            print("Column already exists — nothing to do.")
        else:
            raise
