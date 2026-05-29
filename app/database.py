from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

#run enviroment variables form .env files
load_dotenv()

#get the database URL from .env 
DATABASE_URL = os.getenv("DATABASE_URL")
print(f"DATABASE_URL: {DATABASE_URL}")

#creating an engine- this is the connection to postgresql
engine = create_engine(DATABASE_URL)

#each request to teh api gets its own databse session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Base class that all our database models will inherit from
Base = declarative_base()

#dependecy - give each API endpoint a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

