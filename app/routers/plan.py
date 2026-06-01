# app/routers/plan.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.database import get_db
from app.models.user import User
from app.nutrition import calculate_nutrition, calculate_ideal_weight
from app.meal_selector import select_daily_meals, get_swap_options, generate_weekly_plan
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter(
    prefix="/plan",
    tags=["Plan"]
)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")


def get_current_user_from_token(token: str, db: Session):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


@router.get("/nutrition")
def get_nutrition(token: str, db: Session = Depends(get_db)):
    user = get_current_user_from_token(token, db)

    if not user.weight or not user.height or not user.age:
        raise HTTPException(status_code=400, detail="Please complete onboarding first")

    if not user.goal_weight and user.goal:
        user.goal_weight = calculate_ideal_weight(
            user.height, user.weight, user.gender, user.goal
        )

    nutrition = calculate_nutrition(user)

    return {
        "user": {
            "name": user.name,
            "gender": user.gender,
            "age": user.age,
            "height": user.height,
            "weight": user.weight,
            "goal_weight": user.goal_weight,
            "goal": user.goal,
            "training_days": user.training_days,
            "food_preferences": user.food_preferences,
        },
        "nutrition": nutrition
    }


@router.get("/meals/weekly")
def get_weekly_meals(
    token: str,
    is_fasting: bool = False,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(token, db)

    if not user.weight or not user.height or not user.age:
        raise HTTPException(status_code=400, detail="Please complete onboarding first")

    nutrition = calculate_nutrition(user)
    weekly = generate_weekly_plan(db, user, nutrition, is_fasting)

    return {
        "week": weekly,
        "nutrition_targets": nutrition
    }


@router.get("/meals/swaps")
def get_meal_swaps(
    token: str,
    meal_id: int,
    swap_group: str,
    target_calories: int,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(token, db)
    swaps = get_swap_options(db, meal_id, swap_group, user, target_calories)
    return {"swaps": swaps, "count": len(swaps)}


@router.get("/meals/{meal_id}")
def get_meal_by_id(
    meal_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    from app.models.meal import Meal
    from app.meal_selector import get_protein_boosts, get_user_preferences

    user = get_current_user_from_token(token, db)
    meal = db.query(Meal).filter(Meal.id == meal_id).first()

    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    preferences = get_user_preferences(user)
    is_fasting = preferences['is_fasting']

    from app.nutrition import calculate_nutrition
    nutrition = calculate_nutrition(user)

    protein_targets = {
        'breakfast': nutrition['protein'] * 0.25,
        'lunch': nutrition['protein'] * 0.35,
        'dinner': nutrition['protein'] * 0.35,
        'snack': nutrition['protein'] * 0.05,
    }

    meal_protein_target = protein_targets.get(meal.meal_type, 0)

    return {
        "id": meal.id,
        "name": meal.name,
        "meal_type": meal.meal_type,
        "description": meal.description,
        "prep_time": meal.prep_time,
        "calories": meal.calories,
        "protein": meal.protein,
        "carbs": meal.carbs,
        "fats": meal.fats,
        "fibre": meal.fibre,
        "is_ethiopian": meal.is_ethiopian,
        "is_fasting_friendly": meal.is_fasting_friendly,
        "why": meal.why,
        "best_time": meal.best_time,
        "ingredients": meal.ingredients,
        "steps": meal.steps,
        "tag": meal.tag,
        "tag_color": meal.tag_color,
        "tag_bg": meal.tag_bg,
        "swap_group": meal.swap_group,
        "swap_reason": meal.swap_reason,
        "protein_boosts": get_protein_boosts(
            {"protein": meal.protein},
            meal_protein_target,
            is_fasting
        )
    }