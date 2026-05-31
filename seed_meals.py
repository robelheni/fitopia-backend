import psycopg2
import json
from dotenv import load_dotenv
import os


load_dotenv()

#connect to database

conn = psycopg2.connect(os.getenv("DATABASE_URL"))

cur = conn.cursor()

#clear all existing meals
cur.execute("DELETE FROM meals")

#load meals from JSON file
with open('data/meals.json', 'r') as f:
    meals = json.load(f)

# Insert all meals
for meal in meals:
    cur.execute("""
        INSERT INTO meals (
            name, meal_type, description, prep_time,
            calories, protein, carbs, fats,
            is_ethiopian, is_meat, is_vegetarian, is_fasting_friendly,
            why, best_time, ingredients, steps,
            swap_group, swap_reason, tag, tag_color, tag_bg
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """, (
        meal["name"],
        meal["meal_type"],
        meal["description"],
        meal["prep_time"],
        meal["calories"],
        meal["protein"],
        meal["carbs"],
        meal["fats"],
        meal["is_ethiopian"],
        meal["is_meat"],
        meal["is_vegetarian"],
        meal["is_fasting_friendly"],
        meal["why"],
        meal["best_time"],
        json.dumps(meal["ingredients"]),
        json.dumps(meal["steps"]),
        meal["swap_group"],
        meal["swap_reason"],
        meal["tag"],
        meal["tag_color"],
        meal["tag_bg"]
    ))
conn.commit()
cur.close()
conn.close()

print(f"Successfully inserted {len(meals)} meals into the database")