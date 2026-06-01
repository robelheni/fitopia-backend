# app/meal_selector.py
# ─────────────────────────────────────────────
# Fitopia Meal Selector
# Selects and scales meals for each user
# based on their nutrition targets and preferences
# ─────────────────────────────────────────────

import json
import math
from sqlalchemy.orm import Session
from app.nutrition import get_meal_calorie_category_for_goal

FASTING_PROTEIN_BOOSTS = [
    {
        "id": "boost_edamame",
        "name": "Edamame",
        "description": "Steamed edamame — two large handfuls",
        "protein": 22,
        "calories": 240,
        "how_to": "Steam or boil frozen edamame for 5 minutes. Sprinkle with sea salt.",
        "amount": "2 cupped handfuls"
    },
    {
        "id": "boost_tofu",
        "name": "Plain Tofu",
        "description": "A palm sized block of firm tofu",
        "protein": 16,
        "calories": 150,
        "how_to": "Slice firm tofu and pan fry in a little oil with soy sauce for 3 minutes each side.",
        "amount": "A palm sized block"
    },
    {
        "id": "boost_lentils",
        "name": "Boiled Green Lentils",
        "description": "A cupped handful of boiled green lentils",
        "protein": 14,
        "calories": 174,
        "how_to": "Boil green lentils for 20 minutes until tender. Season with lemon and salt.",
        "amount": "A cupped handful cooked"
    },
    {
        "id": "boost_chickpeas",
        "name": "Roasted Chickpeas",
        "description": "A full can of roasted spiced chickpeas",
        "protein": 14,
        "calories": 260,
        "how_to": "Drain and dry a full can of chickpeas. Roast at 200C for 25 minutes with oil and berbere.",
        "amount": "1 full can roasted"
    },
    {
        "id": "boost_protein_shake",
        "name": "Plant Protein Shake",
        "description": "1 scoop of plant protein powder with water or oat milk",
        "protein": 20,
        "calories": 120,
        "how_to": "Mix 1 scoop of plant based protein powder with 250ml of water or oat milk. Shake well and drink alongside your meal.",
        "amount": "1 scoop in 250ml water or oat milk"
    },
]

def get_protein_boosts(meal, target_protein, is_fasting):
    """
    Returns protein boost options when a fasting meal
    is low in protein
    """
    if not is_fasting:
        return None

    protein_gap = target_protein - meal.get('protein', 0)

    # Only show boosts if gap is significant
    if protein_gap < 10:
        return None

    return {
        "protein_gap": round(protein_gap),
        "banner": (
            "Hitting your protein target during fasting season "
            "is challenging — but absolutely possible. Add one "
            "of these alongside your meal to stay on track."
        ),
        "options": FASTING_PROTEIN_BOOSTS
    }


def get_protein_boosts(meal, target_protein, is_fasting):
    """
    Returns protein boost options when a fasting meal
    is low in protein
    """
    if not is_fasting:
        return None

    protein_gap = target_protein - meal.get('protein', 0)

    # Only show boosts if gap is significant
    if protein_gap < 10:
        return None

    return {
        "protein_gap": round(protein_gap),
        "banner": (
            "Hitting your protein target during fasting season "
            "is challenging — but absolutely possible. Add one "
            "of these alongside your meal to stay on track."
        ),
        "options": FASTING_PROTEIN_BOOSTS
    }
def get_user_preferences(user):
    """
    Returns a dict of what the user can and cannot eat
    """
    food_prefs = user.food_preferences.split(',') if user.food_preferences else []

    return {
        'wants_ethiopian': 'ethiopian' in food_prefs or len(food_prefs) == 0,
        'is_vegetarian': 'vegetarian' in food_prefs,
        'is_fasting': 'fasting' in food_prefs,
        'eats_meat': 'meat' in food_prefs or len(food_prefs) == 0,
        'ethiopian_only': food_prefs == ['ethiopian'],
    }


def filter_meals(meals, preferences, meal_type, is_fasting_day=False):
    """
    Filters meals based on user preferences and meal type
    """
    filtered = []

    for meal in meals:
        # Must match meal type
        if meal.meal_type != meal_type:
            continue

        # Fasting day — only fasting friendly meals
        if is_fasting_day and not meal.is_fasting_friendly:
            continue

        # Vegetarian — no meat meals
        if preferences['is_vegetarian'] and meal.is_meat:
            continue

        # Ethiopian only — only Ethiopian meals
        if preferences['ethiopian_only'] and not meal.is_ethiopian:
            continue

        filtered.append(meal)

    return filtered


def score_meal(meal, target_calories, target_protein, preferences, user_goal):
    """
    Scores a meal based on how well it matches the user
    Higher score = better match

    Weights:
    40% protein match
    30% calorie match
    15% fibre (higher for weight loss)
    15% preference match
    """

    # Protein match score
    protein_ratio = meal.protein / target_protein if target_protein > 0 else 0
    protein_score = 1 - abs(protein_ratio - 1)
    protein_score = max(0, protein_score)

    # Calorie match score
    # Use scaled calories for scoring — not base calories
    max_possible_calories = meal.calories * getattr(meal, 'max_servings', 1.5)
    min_possible_calories = meal.calories * getattr(meal, 'min_servings', 0.75)

    # Check if target is reachable within scaling range
    if min_possible_calories <= target_calories <= max_possible_calories:
        calorie_score = 1.0  # perfect — can hit the target exactly
    else:
    # How far outside the range
        if target_calories > max_possible_calories:
            diff = target_calories - max_possible_calories
        else:
            diff = min_possible_calories - target_calories
        calorie_score = max(0, 1 - (diff / target_calories))

    # Fibre score
    if user_goal == 'lose_weight':
        fibre_score = min(meal.fibre / 10.0, 1.0) if meal.fibre else 0
    else:
        fibre_score = min(meal.fibre / 6.0, 1.0) if meal.fibre else 0

    # Preference score
    preference_score = 0.5  # neutral
    if preferences['wants_ethiopian'] and meal.is_ethiopian:
        preference_score = 1.0
    elif not preferences['wants_ethiopian'] and not meal.is_ethiopian:
        preference_score = 1.0
    elif meal.is_ethiopian:
        preference_score = 0.7  # Ethiopian is always acceptable

    priority_bonus = 0.3 if getattr(meal, 'priority', 1) == 2 else 0

    # Final weighted score
    final_score = (
        protein_score * 0.35 +
        calorie_score * 0.25 +
        fibre_score * 0.10 +
        preference_score * 0.10 +
        priority_bonus
)

    return final_score


def scale_meal(meal, target_calories):
    """
    Scales meal ingredients to hit the target calories
    Only scales ingredients marked as scalable
    """
    if meal.calories == 0:
        return meal

    scale_factor = target_calories / meal.calories
    scale_factor = max(0.75, min(scale_factor, 1.5))

    # Parse ingredients from JSON
    ingredients = meal.ingredients
    if isinstance(ingredients, str):
        ingredients = json.loads(ingredients)

    scaled_ingredients = []
    for ingredient in ingredients:
        if ingredient.get('scalable', False):
            base_qty = ingredient.get('base_quantity', 1)
            min_qty = ingredient.get('min_quantity', base_qty * 0.5)
            max_qty = ingredient.get('max_quantity', base_qty * 2)
            unit = ingredient.get('unit', 'whole')

            # Scale the quantity
            scaled_qty = base_qty * scale_factor
            scaled_qty = max(min_qty, min(scaled_qty, max_qty))

            # Round properly based on unit
            scaled_qty = round_quantity(scaled_qty, unit)

            # Format the amount text
            scaled_amount = format_amount(scaled_qty, unit, ingredient['item'])

            scaled_ingredients.append({
                **ingredient,
                'amount': scaled_amount,
                'scaled_quantity': scaled_qty
            })
        else:
            scaled_ingredients.append(ingredient)

    # Calculate scaled nutrition
    scaled_calories = round(meal.calories * scale_factor)
    scaled_protein = round(meal.protein * scale_factor)
    scaled_carbs = round(meal.carbs * scale_factor)
    scaled_fats = round(meal.fats * scale_factor)
    scaled_fibre = round((meal.fibre or 0) * scale_factor)

    return {
        "id": meal.id,
        "name": meal.name,
        "meal_type": meal.meal_type,
        "description": meal.description,
        "prep_time": meal.prep_time,
        "calories": scaled_calories,
        "protein": scaled_protein,
        "carbs": scaled_carbs,
        "fats": scaled_fats,
        "fibre": scaled_fibre,
        "is_ethiopian": meal.is_ethiopian,
        "is_fasting_friendly": meal.is_fasting_friendly,
        "why": meal.why,
        "best_time": meal.best_time,
        "ingredients": scaled_ingredients,
        "steps": meal.steps if isinstance(meal.steps, list) else json.loads(meal.steps),
        "tag": meal.tag,
        "tag_color": meal.tag_color,
        "tag_bg": meal.tag_bg,
        "swap_group": meal.swap_group,
        "swap_reason": meal.swap_reason,
        "scale_factor": round(scale_factor, 2),
    }


def round_quantity(qty, unit):
    """
    Rounds quantity based on unit type
    Never produces unrealistic numbers
    """
    if unit in ['whole', 'pieces', 'slices', 'can', 'sprigs', 'cloves']:
        # Always whole numbers
        return max(1, round(qty))

    elif unit in ['fraction']:
        # Half or one for injera — never more than 1
        if qty <= 0.6:
            return 0.5
        else:
            return 1.0

    elif unit in ['tablespoon', 'teaspoon', 'cup', 'handful', 'portion']:
        # Round to nearest half
        rounded = round(qty * 2) / 2
        return max(0.5, rounded)

    elif unit == 'pinch':
        return 1

    else:
        return round(qty, 1)


def format_amount(qty, unit, item_name):
    """
    Formats quantity into readable text
    """
    if unit == 'fraction':
        if qty == 0.5:
            return f"Half an {item_name.lower()}"
        elif qty == 1.0:
            return f"One {item_name.lower()}"
        else:
            return f"{qty} {item_name.lower()}"

    elif unit == 'whole':
        if qty == 1:
            return f"1 {item_name.lower()}"
        else:
            return f"{int(qty)} {item_name.lower()}s"

    elif unit == 'tablespoon':
        if qty == 1:
            return "1 tablespoon"
        elif qty == 0.5:
            return "Half a tablespoon"
        else:
            return f"{qty} tablespoons"

    elif unit == 'teaspoon':
        if qty == 1:
            return "1 teaspoon"
        elif qty == 0.5:
            return "Half a teaspoon"
        else:
            return f"{qty} teaspoons"

    elif unit == 'cup':
        if qty == 1:
            return "1 cup"
        elif qty == 0.5:
            return "Half a cup"
        else:
            return f"{qty} cups"

    elif unit == 'handful':
        if qty == 1:
            return "A handful"
        elif qty == 0.5:
            return "Half a handful"
        else:
            return f"{int(qty)} handfuls"

    elif unit == 'portion':
        if qty <= 0.75:
            return "A small palm sized portion"
        elif qty <= 1.0:
            return "A palm sized portion"
        else:
            return "A large palm sized portion"

    elif unit == 'pieces':
        return f"{int(qty)} pieces"

    else:
        return f"{qty} {unit}"

def select_daily_meals(db, user, nutrition, is_fasting_day=False):
    from app.models.meal import Meal

    all_meals = db.query(Meal).all()
    preferences = get_user_preferences(user)

    if preferences['is_fasting']:
        is_fasting_day = True

    breakfast = select_best_meal(
        all_meals, 'breakfast',
        nutrition['breakfast_target'],
        nutrition['protein'] * 0.25,
        preferences, user.goal, is_fasting_day,
        force_international=True
    )

    lunch = select_best_meal(
        all_meals, 'lunch',
        nutrition['lunch_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=False
    )

    lunch_was_ethiopian = lunch and lunch.get('is_ethiopian', False)

    dinner = select_best_meal(
        all_meals, 'dinner',
        nutrition['dinner_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=lunch_was_ethiopian
    )

    snack = select_best_meal(
        all_meals, 'snack',
        nutrition['snack_target'],
        nutrition['protein'] * 0.05,
        preferences, user.goal, is_fasting_day,
        force_international=False
    )

    # Calculate total calories
    total_calories = (
        (breakfast['calories'] if breakfast else 0) +
        (lunch['calories'] if lunch else 0) +
        (snack['calories'] if snack else 0) +
        (dinner['calories'] if dinner else 0)
    )

    # Add second snack if still 400+ calories short
    snack2 = None
    calorie_gap = nutrition['calories'] - total_calories
    if calorie_gap >= 400:
        snack2 = select_best_meal(
            all_meals, 'snack',
            calorie_gap,
            nutrition['protein'] * 0.05,
            preferences, user.goal, is_fasting_day,
            force_international=False,
            exclude_ids=[snack['id']] if snack else []
        )
        if snack2:
            total_calories += snack2['calories']

    # Add protein boosts
    if is_fasting_day:
        lunch_protein_target = nutrition['protein'] * 0.35
        dinner_protein_target = nutrition['protein'] * 0.35

        if lunch:
            lunch['protein_boosts'] = get_protein_boosts(
                lunch, lunch_protein_target, is_fasting_day
            )
        if dinner:
            dinner['protein_boosts'] = get_protein_boosts(
                dinner, dinner_protein_target, is_fasting_day
            )

    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "snack": snack,
        "snack2": snack2,
        "dinner": dinner,
        "total_calories": total_calories,
        "calorie_target": nutrition['calories'],
        "calorie_gap": max(0, nutrition['calories'] - total_calories),
    }
def select_best_meal(meals, meal_type, target_calories,
                     target_protein, preferences,
                     goal, is_fasting_day,
                     force_international=False,
                     exclude_ids=None):

    if exclude_ids is None:
        exclude_ids = []

    # Remove None values from exclude_ids
    exclude_ids = [i for i in exclude_ids if i is not None]

    available = filter_meals(meals, preferences, meal_type, is_fasting_day)

    if force_international:
        available = [m for m in available if not m.is_ethiopian]

    # Exclude already used meals
    available = [m for m in available if m.id not in exclude_ids]

    if not available:
        available = filter_meals(meals, preferences, meal_type, is_fasting_day)
        available = [m for m in available if m.id not in exclude_ids]

    if not available:
        available = [m for m in meals if m.meal_type == meal_type and m.id not in exclude_ids]

    if not available:
        available = [m for m in meals if m.meal_type == meal_type]

    if not available:
        return None

    scored = []
    for meal in available:
        score = score_meal(meal, target_calories, target_protein, preferences, goal)
        scored.append((score, meal))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_meal = scored[0][1]

    return scale_meal(best_meal, target_calories)

    



def get_swap_options(db: Session, meal_id, swap_group,
                     user, target_calories):
    """
    Returns alternative meals from the same swap group
    Excludes the current meal
    """
    from app.models.meal import Meal

    preferences = get_user_preferences(user)

    swaps = db.query(Meal).filter(
        Meal.swap_group == swap_group,
        Meal.id != meal_id
    ).all()

    # Filter by preferences
    filtered_swaps = []
    for meal in swaps:
        if preferences['is_vegetarian'] and meal.is_meat:
            continue
        if preferences['ethiopian_only'] and not meal.is_ethiopian:
            continue
        filtered_swaps.append(meal)

    # Scale each swap option
    return [scale_meal(meal, target_calories) for meal in filtered_swaps]


def generate_weekly_plan(db, user, nutrition, is_fasting_day=False):
    from app.models.meal import Meal

    all_meals = db.query(Meal).all()
    preferences = get_user_preferences(user)

    if preferences['is_fasting']:
        is_fasting_day = True

    # Select 2 breakfast options
    breakfast_a = select_best_meal(
        all_meals, 'breakfast',
        nutrition['breakfast_target'],
        nutrition['protein'] * 0.25,
        preferences, user.goal, is_fasting_day,
        force_international=True,
        exclude_ids=[]
    )

    breakfast_b = select_best_meal(
        all_meals, 'breakfast',
        nutrition['breakfast_target'],
        nutrition['protein'] * 0.25,
        preferences, user.goal, is_fasting_day,
        force_international=True,
        exclude_ids=[breakfast_a['id']] if breakfast_a else []
    )

    # Select 3 lunch options
    lunch_a = select_best_meal(
        all_meals, 'lunch',
        nutrition['lunch_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=False,
        exclude_ids=[]
    )

    lunch_a_ethiopian = lunch_a and lunch_a.get('is_ethiopian', False)

    lunch_b = select_best_meal(
        all_meals, 'lunch',
        nutrition['lunch_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=False,
        exclude_ids=[lunch_a['id']] if lunch_a else []
    )

    lunch_b_ethiopian = lunch_b and lunch_b.get('is_ethiopian', False)

    lunch_c = select_best_meal(
        all_meals, 'lunch',
        nutrition['lunch_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=False,
        exclude_ids=[
            lunch_a['id'] if lunch_a else None,
            lunch_b['id'] if lunch_b else None
        ]
    )

    # Select 3 dinner options
    # Respect Ethiopian rotation — if lunch is Ethiopian dinner is not
    dinner_a = select_best_meal(
        all_meals, 'dinner',
        nutrition['dinner_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=lunch_a_ethiopian,
        exclude_ids=[]
    )

    dinner_b = select_best_meal(
        all_meals, 'dinner',
        nutrition['dinner_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=lunch_b_ethiopian,
        exclude_ids=[dinner_a['id']] if dinner_a else []
    )

    dinner_c = select_best_meal(
        all_meals, 'dinner',
        nutrition['dinner_target'],
        nutrition['protein'] * 0.35,
        preferences, user.goal, is_fasting_day,
        force_international=False,
        exclude_ids=[
            dinner_a['id'] if dinner_a else None,
            dinner_b['id'] if dinner_b else None
        ]
    )

    # Select 2 snack options
    snack_a = select_best_meal(
        all_meals, 'snack',
        nutrition['snack_target'],
        nutrition['protein'] * 0.05,
        preferences, user.goal, is_fasting_day,
        force_international=False,
        exclude_ids=[]
    )

    snack_b = select_best_meal(
        all_meals, 'snack',
        nutrition['snack_target'],
        nutrition['protein'] * 0.05,
        preferences, user.goal, is_fasting_day,
        force_international=False,
        exclude_ids=[snack_a['id']] if snack_a else []
    )

    # Build 7 day plan
    weekly = {
        'mon': {'breakfast': breakfast_a, 'lunch': lunch_a, 'snack': snack_a, 'dinner': dinner_a},
        'tue': {'breakfast': breakfast_b, 'lunch': lunch_b, 'snack': snack_b, 'dinner': dinner_b},
        'wed': {'breakfast': breakfast_a, 'lunch': lunch_c, 'snack': snack_a, 'dinner': dinner_c},
        'thu': {'breakfast': breakfast_b, 'lunch': lunch_a, 'snack': snack_b, 'dinner': dinner_a},
        'fri': {'breakfast': breakfast_a, 'lunch': lunch_b, 'snack': snack_a, 'dinner': dinner_b},
        'sat': {'breakfast': breakfast_b, 'lunch': lunch_c, 'snack': snack_b, 'dinner': dinner_c},
        'sun': {'breakfast': breakfast_a, 'lunch': lunch_a, 'snack': snack_a, 'dinner': dinner_a},
    }

    return weekly


def get_or_generate_weekly_plan(db, user, nutrition, is_fasting_day=False):
    from datetime import datetime, timedelta

    # Return cached plan if generated within last 7 days
    if user.weekly_plan and user.plan_generated_at:
        age = datetime.utcnow() - user.plan_generated_at
        if age < timedelta(days=7):
            return user.weekly_plan

    # Generate fresh plan
    plan = generate_weekly_plan(db, user, nutrition, is_fasting_day)

    # Save to database
    user.weekly_plan = plan
    user.plan_generated_at = datetime.utcnow()
    db.commit()

    return plan