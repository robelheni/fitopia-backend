import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

cur.execute("ALTER TABLE community_posts ADD COLUMN IF NOT EXISTS image_url VARCHAR;")
print("Migration complete: image_url column added to community_posts")

cur.close()
conn.close()
