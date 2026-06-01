# test_nutrition.py
from app.nutrition import calculate_nutrition, calculate_ideal_weight

# Create a mock user object
class MockUser:
    def __init__(self):
        self.gender = 'male'
        self.weight = 85
        self.height = 170
        self.age = 30
        self.goal = 'lose_weight'
        self.goal_weight = 70
        self.training_days = 'mon,wed,fri'

user = MockUser()
result = calculate_nutrition(user)

print("=== NUTRITION RESULTS ===")
print(f"BMR: {result['bmr']} calories")
print(f"TDEE: {result['tdee']} calories")
print(f"Daily calories: {result['calories']}")
print(f"Protein: {result['protein']}g")
print(f"Carbs: {result['carbs']}g")
print(f"Fats: {result['fats']}g")
print(f"Water: {result['water']}L")
print(f"Breakfast target: {result['breakfast_target']} cal")
print(f"Lunch target: {result['lunch_target']} cal")
print(f"Snack target: {result['snack_target']} cal")
print(f"Dinner target: {result['dinner_target']} cal")
print(f"Weeks to goal: {result['weeks_to_goal']}")
print(f"\nExplanation: {result['explanation']}")

print("\n=== IDEAL WEIGHT ===")
ideal = calculate_ideal_weight(170, 85, 'male', 'lose_weight')
print(f"Ideal weight: {ideal}kg")

# Test muscle gain
user.goal = 'build_muscle'
user.weight = 56
user.goal_weight = 73
result2 = calculate_nutrition(user)
print("\n=== MUSCLE GAIN (56kg) ===")
print(f"Daily calories: {result2['calories']}")
print(f"Protein: {result2['protein']}g")
print(f"Explanation: {result2['explanation']}")


print("\n=== TESTING MEAL CATEGORIES ===")
from app.nutrition import get_meal_calorie_category_for_goal
print(f"Lose weight prefers: {get_meal_calorie_category_for_goal('lose_weight')}")
print(f"Build muscle prefers: {get_meal_calorie_category_for_goal('build_muscle')}")
print(f"Stay active prefers: {get_meal_calorie_category_for_goal('stay_active')}")