from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth 
from app.routers import auth, plan
from app.routers import auth, plan, workouts, exercise





#Create all database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Fitopia API",
    desciption = "The backend for Fitopia",
    version = "1.0.0"
    
)


# CORS — allows your React Native app to talk to this server(Fatsapi backend)
#without this the server would block outside requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#reigster routers
app.include_router(auth.router)
app.include_router(plan.router)
app.include_router(workouts.router)


#root endpoint - just to check the server is server is running
@app.get("/")
def root():
    return {
        "message":"Fitopia is running",
        "version": "1.0.0"
    }