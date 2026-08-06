import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture VARCHAR;")
conn.commit()
cur.close()
conn.close()
print("Migration complete: profile_picture column added.")
