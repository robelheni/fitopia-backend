# app/nutrition.py
# ─────────────────────────────────────────────
# Fitopia Nutrition Calculator
# Takes user profile and returns personalised
# calorie, macro and meal targets
# ─────────────────────────────────────────────

def calculate_nutrition(user):
    """
    Main function — takes a user object and returns
    their complete personalised nutrition plan
    """

    # ─── Step 1 — BMR (Mifflin St Jeor) ──────────
    # How many calories the body burns at complete rest
    if user.gender == 'male':
        bmr = 10 * user.weight + 6.25 * user.height - 5 * user.age + 5
    else:
        bmr = 10 * user.weight + 6.25 * user.height - 5 * user.age - 161


    # ─── Step 2 — TDEE ────────────────────────────
    # Total Daily Energy Expenditure
    # Based on actual training days from onboarding
    training_days = user.training_days.split(',') if user.training_days else []
    days = len(training_days)

    if days <= 2:
        multiplier = 1.375   # lightly active
    elif days <= 3:
        multiplier = 1.55    # moderately active
    elif days <= 4:
        multiplier = 1.725   # very active
    else:
        multiplier = 1.9     # extremely active

    tdee = bmr * multiplier


    # ─── Step 3 — Goal adjustment ─────────────────
    if user.goal == 'lose_weight':
        calories = tdee - 500    # safe deficit
    elif user.goal == 'build_muscle':
        calories = tdee + 300    # lean surplus
    else:
        calories = tdee          # maintenance

    # Never go below 1200 for females or 1500 for males
    # Safety floor
    if user.gender == 'female':
        calories = max(calories, 1200)
    else:
        calories = max(calories, 1500)


    # ─── Step 4 — Protein target ──────────────────
    # 2g per kg of bodyweight — always priority one
    protein = user.weight * 2


    # ─── Step 5 — Macro split ─────────────────────
    protein_calories = protein * 4
    fat_calories = calories * 0.25
    fats = fat_calories / 9
    carb_calories = calories - protein_calories - fat_calories
    carbs = carb_calories / 4

    # If carbs go negative protein is too high for calories
    # Reduce protein slightly to fix
    if carbs < 50:
        protein = (calories * 0.35) / 4
        protein_calories = protein * 4
        fat_calories = calories * 0.25
        fats = fat_calories / 9
        carb_calories = calories - protein_calories - fat_calories
        carbs = carb_calories / 4


    # ─── Step 6 — Water target ────────────────────
    # 35ml per kg of bodyweight
    water = round(user.weight * 0.035, 1)


    # ─── Step 7 — Meal targets ────────────────────
    breakfast_target = calories * 0.25
    lunch_target = calories * 0.35
    snack_target = calories * 0.05
    dinner_target = calories * 0.35


    # ─── Step 8 — Progress estimate ───────────────
    if user.goal == 'lose_weight' and user.goal_weight:
        weeks_to_goal = (user.weight - user.goal_weight) / 0.5
        weeks_to_goal = max(0, round(weeks_to_goal))
    elif user.goal == 'build_muscle' and user.goal_weight:
        weeks_to_goal = (user.goal_weight - user.weight) / 0.3
        weeks_to_goal = max(0, round(weeks_to_goal))
    else:
        weeks_to_goal = 0


    # ─── Step 9 — Goal explanation ────────────────
    # Simple plain language explanation for the app
    if user.goal == 'lose_weight':
        explanation = (
            f"To lose weight safely you need {round(calories)} calories daily. "
            f"This creates a 500 calorie deficit which leads to roughly 0.5kg "
            f"loss per week. Protein is kept high at {round(protein)}g to "
            f"preserve your muscle while losing fat."
        )
    elif user.goal == 'build_muscle':
        explanation = (
            f"To build muscle you need {round(calories)} calories daily. "
            f"This gives your body a 300 calorie surplus to build new muscle "
            f"tissue. Your protein target is {round(protein)}g — the building "
            f"block of every muscle in your body."
        )
    else:
        explanation = (
            f"To stay active and healthy you need {round(calories)} calories "
            f"daily. This matches exactly what your body burns. Protein target "
            f"is {round(protein)}g to maintain your current muscle mass."
        )


    # ─── Return everything ────────────────────────
    return {
        "calories": round(calories),
        "protein": round(protein),
        "carbs": round(carbs),
        "fats": round(fats),
        "water": water,
        "bmr": round(bmr),
        "tdee": round(tdee),
        "breakfast_target": round(breakfast_target),
        "lunch_target": round(lunch_target),
        "snack_target": round(snack_target),
        "dinner_target": round(dinner_target),
        "weeks_to_goal": weeks_to_goal,
        "explanation": explanation,
    }


def calculate_ideal_weight(height, weight, gender, goal):
    """
    Devine formula — same as the frontend step 7 calculation
    Used to suggest ideal weight if user did not set one
    """
    if gender == 'male':
        base = 50 + 2.3 * ((height - 152.4) / 2.54)
    else:
        base = 45.5 + 2.3 * ((height - 152.4) / 2.54)

    if goal == 'build_muscle':
        ideal = round(base + 7)
        if weight >= ideal:
            ideal = weight + 3
    elif goal == 'lose_weight':
        ideal = round(base)
        if weight <= base:
            ideal = weight
    else:
        ideal = round(base)

    return ideal


def get_calorie_category(calories):
    """
    Returns light medium or heavy based on calories
    Used for meal selection
    """
    if calories < 450:
        return 'light'
    elif calories <= 620:
        return 'medium'
    else:
        return 'heavy'


def get_meal_calorie_category_for_goal(goal):
    """
    Returns preferred calorie category based on user goal
    Used to filter meals during selection
    """
    if goal == 'lose_weight':
        return ['light', 'medium']
    elif goal == 'build_muscle':
        return ['medium', 'heavy']
    else:
        return ['medium']