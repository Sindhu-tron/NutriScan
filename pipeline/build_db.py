"""
build_db.py
-----------
Responsibility:
- Build the SQLite database (nutriscan.db) used by the NutriScan API and dashboard
- Orchestrates the pipeline modules to pre-compute and cache all matches and scores

The database contains six tables:
    patients            Synthetic resident profiles
    patient_conditions  One row per condition with status (primary / risk / inactive)
    dishes              One row per dish from dish_ingredients.json
    dish_ingredients    Ingredients and gram amounts for each dish
    ingredient_matches  Frida matcher output for every unique ingredient
    meal_scores         Grade and score from scoring.py for every patient-dish pair

A seventh table (score_history) is created at API startup by api/main.py
and populated at runtime when scoring events occur.

Run this file to (re)build the database from scratch:
    python pipeline/build_db.py

Note: re-running deletes and recreates nutriscan.db entirely, so any
score_history entries written at runtime will be lost.
"""
 
import json
import sqlite3
import sys
from pathlib import Path
 
 
# Paths to the input files and where the database should be saved
# build_db.py lives inside pipeline/, so we go one level up to reach the project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRIDA_FILE = PROJECT_ROOT / "data" / "Frida_5.5_Dataset.xlsx"
DISH_FILE  = PROJECT_ROOT / "sample_data" / "dish_ingredients.json"
DB_FILE    = PROJECT_ROOT / "pipeline" / "nutriscan.db"
 
 
# Make sure we can import from the pipeline folder
sys.path.insert(0, str(PROJECT_ROOT))
from pipeline.scoring       import score_meal
from pipeline.frida_matcher import load_frida, match_ingredient
# We import load_frida and match_ingredient from pipeline/frida_matcher.py rather
# than copying the logic here. That way the database always uses the same matching
# strategy as the rest of the system, including the manual overrides for ingredients
# like "aeg", "loeg", "oksekoed" etc. that WRatio consistently got wrong.
 
# Real nutrient lookup — uses the Frida Data_Table instead of synthetic baselines
from pipeline.nutrient_lookup import load_frida_dataset, nutrients_for_food, aggregate_nutrients
 
 
# The fake patients used by the dashboard, copied over so the database is self-contained.
# Each patient has an id, basic demographics, and a list of health conditions.
# Conditions are split into primary (active), risk (at risk), and inactive.
PATIENTS = [
    {
        "id": "XY-5217",
        "name": "Erik Andersen",
        "sex": "Male",
        "age": 82,
        "location": "Wing A, Room 3",
        "avatar": "EA",
        "conditions": {
            "primary": ["Hypertension", "Type 2 Diabetes"],
            "risk": ["Malnutrition Risk"],
            "inactive": []
        }
    },
    {
        "id": "XY-3891",
        "name": "Birthe Sorensen",
        "sex": "Female",
        "age": 79,
        "location": "Wing B, Room 7",
        "avatar": "BS",
        "conditions": {
            "primary": ["Osteoporosis"],
            "risk": ["Malnutrition Risk"],
            "inactive": ["Dementia"]
        }
    },
    {
        "id": "XY-4422",
        "name": "Kaj Nielsen",
        "sex": "Male",
        "age": 85,
        "location": "Wing C, Room 12",
        "avatar": "KN",
        "conditions": {
            "primary": ["High Cholesterol"],
            "risk": ["Hypertension"],
            "inactive": []
        }
    },
    {
        "id": "XY-6104",
        "name": "Grethe Larsen",
        "sex": "Female",
        "age": 76,
        "location": "Wing A, Room 9",
        "avatar": "GL",
        "conditions": {
            "primary": ["Malnutrition Risk"],
            "risk": [],
            "inactive": ["Type 2 Diabetes"]
        }
    },
    {
        "id": "XY-7733",
        "name": "Holger Christensen",
        "sex": "Male",
        "age": 88,
        "location": "Wing D, Room 2",
        "avatar": "HC",
        "conditions": {
            "primary": [],
            "risk": [],
            "inactive": []
        }
    }
]
 
 
# Only pass conditions that scoring.py has multipliers for.
# Anything else (e.g. Dementia) is dropped before scoring.
KNOWN_CONDITIONS = {
    "Hypertension",
    "Type 2 Diabetes",
    "Osteoporosis",
    "Malnutrition Risk",
    "High Cholesterol",
}
 
 
# Load the dishes from dish_ingredients.json and flatten them into simple lists
def load_dishes(filepath):
    raw = json.loads(Path(filepath).read_text(encoding="utf-8"))
 
    dishes = []             # (dish_name, category, kostform)
    dish_ings = []          # (dish_name, ingredient, grams) for dish_ingredients table
    unique_ingredients = set()
 
    # dish_data maps dish_name -> (ingredients list, amounts list) so
    # score_all_meals can pass the real ingredients to nutrients_for_dish
    dish_data = {}
 
    for category, bucket in raw.items():
        if category.startswith("_"):
            continue
 
        for dish_name, info in bucket.items():
            ingredients = info.get("ingredients", [])
            amounts     = info.get("amounts_g", [])
            kostform    = info.get("kostform", "")
 
            dishes.append((dish_name, category, kostform))
            dish_data[dish_name] = (ingredients, amounts)
 
            for ingredient, grams in zip(ingredients, amounts):
                dish_ings.append((dish_name, ingredient, float(grams)))
                unique_ingredients.add(ingredient)
 
    return dishes, dish_ings, unique_ingredients, dish_data
 
 
# Look up real nutrient values for a dish by summing up each ingredient.
# Uses pipeline/frida_matcher.py to translate ingredient names to Frida entries,
# then pipeline/nutrient_lookup.py to get the actual numbers per 100g.
# Ingredients flagged as uncertain by the matcher are skipped.
def nutrients_for_dish(dish_ingredients, dish_amounts, frida_food_df):
    profiles = []
 
    for ingredient, grams in zip(dish_ingredients, dish_amounts):
        match_result = match_ingredient(ingredient, frida_food_df)
 
        if match_result["flagged_for_review"]:
            continue
 
        frida_name = match_result["matched_name"]
        try:
            profile = nutrients_for_food(frida_name, grams)
            profiles.append(profile)
        except KeyError:
            # Frida name exists in Food sheet but not in Data_Table -- skip
            pass
 
    return aggregate_nutrients(profiles) if profiles else {
        "energy_kcal": 0.0, "protein_g": 0.0, "fat_sat_g": 0.0,
        "fiber_g": 0.0, "sugar_g": 0.0, "sodium_mg": 0.0,
        "potassium_mg": 0.0, "calcium_mg": 0.0,
    }
 
 
# Take a patient's conditions and keep only the ones scoring.py knows about
def conditions_for_scoring(patient):
    active = list(patient["conditions"]["primary"]) + list(patient["conditions"]["risk"])
    return [c for c in active if c in KNOWN_CONDITIONS]
 
 
# Score every patient against every dish and return rows for the meal_scores table
def score_all_meals(dishes, dish_data, patients, frida_food_df):
    rows = []
 
    for patient in patients:
        conditions = conditions_for_scoring(patient)
 
        for dish_name, category, kostform in dishes:
            ingredients, amounts = dish_data.get(dish_name, ([], []))
            nutrients = nutrients_for_dish(ingredients, amounts, frida_food_df)
            result    = score_meal(nutrients, conditions)
 
            rows.append({
                "patient_id":        patient["id"],
                "dish_name":         dish_name,
                "category":          category,
                "conditions":        ", ".join(conditions),
                "score":             result["score"],
                "grade":             result["grade"],
                "grade_description": result["grade_description"],
                "flag_count":        len(result["flags"]),
                "energy_kcal":       nutrients["energy_kcal"],
                "protein_g":         nutrients["protein_g"],
                "fiber_g":           nutrients["fiber_g"],
                "calcium_mg":        nutrients["calcium_mg"],
                "sodium_mg":         nutrients["sodium_mg"],
                "fat_sat_g":         nutrients["fat_sat_g"],
                "sugar_g":           nutrients["sugar_g"],
            })
 
    return rows
 
 
# Create the empty tables in the SQLite database
def create_tables(connection):
    cursor = connection.cursor()
    cursor.executescript("""
        CREATE TABLE patients (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            sex         TEXT,
            age         INTEGER,
            location    TEXT,
            avatar      TEXT
        );
 
        CREATE TABLE patient_conditions (
            patient_id  TEXT NOT NULL,
            condition   TEXT NOT NULL,
            status      TEXT NOT NULL CHECK(status IN ('primary','risk','inactive')),
            PRIMARY KEY (patient_id, condition, status),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );
 
        CREATE TABLE dishes (
            name        TEXT PRIMARY KEY,
            category    TEXT,
            kostform    TEXT
        );
 
        CREATE TABLE dish_ingredients (
            dish_name   TEXT NOT NULL,
            ingredient  TEXT NOT NULL,
            grams       REAL NOT NULL,
            PRIMARY KEY (dish_name, ingredient),
            FOREIGN KEY (dish_name) REFERENCES dishes(name)
        );
 
        CREATE TABLE ingredient_matches (
            query               TEXT PRIMARY KEY,
            matched_name        TEXT,
            frida_id            INTEGER,
            confidence          REAL,
            flagged_for_review  INTEGER
        );
 
        CREATE TABLE meal_scores (
            patient_id          TEXT NOT NULL,
            dish_name           TEXT NOT NULL,
            category            TEXT,
            conditions          TEXT,
            score               REAL,
            grade               TEXT,
            grade_description   TEXT,
            flag_count          INTEGER,
            energy_kcal         REAL,
            protein_g           REAL,
            fiber_g             REAL,
            calcium_mg          REAL,
            sodium_mg           REAL,
            fat_sat_g           REAL,
            sugar_g             REAL,
            PRIMARY KEY (patient_id, dish_name),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (dish_name)  REFERENCES dishes(name)
        );
    """)
 
 
# Insert all the patients and their conditions
def insert_patients(connection, patients):
    cursor = connection.cursor()
    for patient in patients:
        cursor.execute(
            "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?)",
            (patient["id"], patient["name"], patient["sex"],
             patient["age"], patient["location"], patient["avatar"])
        )
        for status in ("primary", "risk", "inactive"):
            for condition in patient["conditions"][status]:
                cursor.execute(
                    "INSERT INTO patient_conditions VALUES (?, ?, ?)",
                    (patient["id"], condition, status)
                )
 
 
# Insert dishes and their ingredients
def insert_dishes(connection, dishes, dish_ings):
    cursor = connection.cursor()
    cursor.executemany("INSERT INTO dishes VALUES (?, ?, ?)", dishes)
    cursor.executemany("INSERT INTO dish_ingredients VALUES (?, ?, ?)", dish_ings)
 
 
# Insert the Frida matcher results
def insert_matches(connection, matches):
    cursor = connection.cursor()
    for match in matches.values():
        cursor.execute(
            "INSERT INTO ingredient_matches VALUES (?, ?, ?, ?, ?)",
            (match["query"], match["matched_name"], match["frida_id"],
             match["confidence"], int(match["flagged_for_review"]))
        )
 
 
# Insert the meal scores
def insert_meal_scores(connection, rows):
    cursor = connection.cursor()
    for row in rows:
        cursor.execute(
            """INSERT INTO meal_scores VALUES
               (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["patient_id"], row["dish_name"], row["category"], row["conditions"],
             row["score"], row["grade"], row["grade_description"], row["flag_count"],
             row["energy_kcal"], row["protein_g"], row["fiber_g"], row["calcium_mg"],
             row["sodium_mg"], row["fat_sat_g"], row["sugar_g"])
        )
 
 
# Main: run the whole build pipeline
if __name__ == "__main__":
    # Step 1: load the Frida Food sheet (used by frida_matcher for name matching)
    print("Loading Frida Food sheet...")
    frida_food_df = load_frida(str(FRIDA_FILE))
    print("Loaded " + str(len(frida_food_df)) + " foods from Frida")
 
    # Step 2: load the Frida Data_Table into the nutrient_lookup cache so it's
    # ready for nutrients_for_food() calls inside nutrients_for_dish()
    print("Loading Frida Data_Table for nutrient lookup...")
    load_frida_dataset()
    print("Data_Table loaded")
 
    # Step 3: load all dishes and their ingredients from dish_ingredients.json
    print("Loading dishes...")
    dishes, dish_ings, unique_ingredients, dish_data = load_dishes(DISH_FILE)
    print("Loaded " + str(len(dishes)) + " dishes with " + str(len(unique_ingredients)) + " unique ingredients")
 
    # Step 4: match every unique ingredient against Frida using the fixed matcher
    # (includes manual overrides for ingredients like aeg, loeg, oksekoed etc.)
    print("Matching ingredients to Frida...")
    matches = {}
    for ingredient in sorted(unique_ingredients):
        matches[ingredient] = match_ingredient(ingredient, frida_food_df)
 
    flagged_count = sum(1 for m in matches.values() if m["flagged_for_review"])
    print("Matched " + str(len(matches)) + " ingredients (" + str(flagged_count) + " flagged for review)")
 
    # Step 5: score every patient against every dish using real Frida nutrients
    print("Scoring meals for each patient...")
    meal_score_rows = score_all_meals(dishes, dish_data, PATIENTS, frida_food_df)
    print("Computed " + str(len(meal_score_rows)) + " patient-meal scores")
 
    # Step 6: write the SQLite database
    print("Writing database to " + str(DB_FILE) + " ...")
    if DB_FILE.exists():
        DB_FILE.unlink()
 
    connection = sqlite3.connect(DB_FILE)
    create_tables(connection)
    insert_patients(connection, PATIENTS)
    insert_dishes(connection, dishes, dish_ings)
    insert_matches(connection, matches)
    insert_meal_scores(connection, meal_score_rows)
    connection.commit()
    connection.close()
 
    print("Done. Database is ready at " + str(DB_FILE))