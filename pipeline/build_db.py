# This script builds the SQLite database (nutriscan.db) used by the NutriScan project.
# It collects everything we need into one file so we can query patients, dishes,
# Frida matches and meal scores from one place.
#
# The database contains six tables:
#   patients            - the fake patients from dashboard.py
#   patient_conditions  - one row per condition with status (primary/risk/inactive)
#   dishes              - one row per dish from dish_ingredients.json
#   dish_ingredients    - the ingredients in each dish, with grams
#   ingredient_matches  - the output from the Frida matcher
#   meal_scores         - the score and grade from scoring.py for every patient and dish
#
# Run this file directly to (re)build the database:
#     python build_db.py

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import process, fuzz


# If the match score is below this number, we flag it so someone can check it manually
THRESHOLD = 80


# Paths to the input files and where the database should be saved
PROJECT_ROOT = Path(__file__).resolve().parent
FRIDA_FILE = PROJECT_ROOT / "data" / "Frida_5.5_Dataset.xlsx"
DISH_FILE = PROJECT_ROOT / "sample_data" / "dish_ingredients.json"
DB_FILE = PROJECT_ROOT / "nutriscan.db"


# Make sure we can import scoring.py from the pipeline folder
sys.path.insert(0, str(PROJECT_ROOT))
from pipeline.scoring import score_meal


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
            "risk": ["Malnutrition"],
            "inactive": []
        }
    },
    {
        "id": "XY-3891",
        "name": "Birthe Sørensen",
        "sex": "Female",
        "age": 79,
        "location": "Wing B, Room 7",
        "avatar": "BS",
        "conditions": {
            "primary": ["Osteoporosis"],
            "risk": ["Malnutrition"],
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


# When a patient has a condition we don't have rules for, we drop it before scoring.
# "Malnutrition" is treated the same as "Malnutrition Risk" in scoring.py.
KNOWN_CONDITIONS = {
    "Hypertension",
    "Type 2 Diabetes",
    "Osteoporosis",
    "Malnutrition Risk",
    "High Cholesterol",
}


# Average nutrient values per category, used as a baseline for each dish.
# Numbers are based on typical Danish institution meals (Institutionskost 2025).
CATEGORY_BASELINE = {
    "meat": {
        "energy_kcal": 720, "protein_g": 38, "fiber_g": 4,
        "calcium_mg": 180, "sodium_mg": 780, "fat_sat_g": 8.5, "sugar_g": 4
    },
    "fish": {
        "energy_kcal": 560, "protein_g": 34, "fiber_g": 4,
        "calcium_mg": 200, "sodium_mg": 520, "fat_sat_g": 4.5, "sugar_g": 3
    },
    "vegetarian": {
        "energy_kcal": 600, "protein_g": 22, "fiber_g": 8,
        "calcium_mg": 240, "sodium_mg": 460, "fat_sat_g": 5.0, "sugar_g": 6
    },
    "desserts": {
        "energy_kcal": 380, "protein_g": 6, "fiber_g": 2,
        "calcium_mg": 120, "sodium_mg": 160, "fat_sat_g": 7.0, "sugar_g": 22
    }
}


# Load the food names and IDs from the Frida Excel file
def load_frida(filepath):
    # Read the "Food" sheet from the Excel file
    df = pd.read_excel(filepath, sheet_name="Food")

    # Only keep the columns we need
    df = df[["FødevareNavn", "FoodID"]]

    # Remove rows where the food name is missing
    df = df.dropna()

    return df


# This function takes one ingredient name and finds the best match in Frida
def match_ingredient(ingredient, frida_df):
    # Get all the Danish food names as a list
    food_names = frida_df["FødevareNavn"].tolist()

    # Use rapidfuzz to find the best match
    best_match, score, index = process.extractOne(ingredient, food_names, scorer=fuzz.WRatio)

    # Get the ID of the matched food
    frida_id = frida_df.iloc[index]["FoodID"]

    # Round the score to 1 decimal place so it is easier to read
    score = round(score, 1)

    # If the score is too low, flag it for manual review
    if score < THRESHOLD:
        flagged = True
    else:
        flagged = False

    # Put the results in a dictionary and return it
    result = {
        "query": ingredient,
        "matched_name": best_match,
        "frida_id": frida_id,
        "confidence": score,
        "flagged_for_review": flagged
    }

    return result


# Load the dishes from dish_ingredients.json and flatten them into simple lists
def load_dishes(filepath):
    # Read the JSON file
    raw = json.loads(Path(filepath).read_text(encoding="utf-8"))

    # Lists we will fill in
    dishes = []
    dish_ings = []
    unique_ingredients = set()

    # Loop through each category (meat, fish, vegetarian, desserts)
    for category, bucket in raw.items():

        # Skip the metadata block at the top of the JSON
        if category.startswith("_"):
            continue

        # Loop through each dish in the category
        for dish_name, info in bucket.items():
            ingredients = info.get("ingredients", [])
            amounts = info.get("amounts_g", [])
            kostform = info.get("kostform", "")

            dishes.append((dish_name, category, kostform))

            # Pair each ingredient with its amount in grams
            for ingredient, grams in zip(ingredients, amounts):
                dish_ings.append((dish_name, ingredient, float(grams)))
                unique_ingredients.add(ingredient)

    return dishes, dish_ings, unique_ingredients


# Build a synthetic nutrient profile for a single dish
def nutrients_for_dish(dish_name, category):
    # Start from the category baseline so meat, fish and dessert look different
    nutrients = CATEGORY_BASELINE.get(category, CATEGORY_BASELINE["meat"]).copy()

    # Add a small dish-specific variation so dishes in the same category aren't identical
    name_hash = sum(ord(c) for c in dish_name)
    nutrients["sodium_mg"] = nutrients["sodium_mg"] + (name_hash % 7) * 25
    nutrients["sugar_g"] = nutrients["sugar_g"] + (name_hash % 5)
    nutrients["fiber_g"] = nutrients["fiber_g"] + (name_hash % 3)

    return nutrients


# Take a patient's conditions and keep only the ones scoring.py knows about
def conditions_for_scoring(patient):
    primary = patient["conditions"]["primary"]
    risk = patient["conditions"]["risk"]

    # We treat both primary and risk conditions as active when scoring
    active = list(primary) + list(risk)

    # scoring.py uses "Malnutrition Risk", but the patient data uses "Malnutrition"
    cleaned = []
    for condition in active:
        if condition == "Malnutrition":
            cleaned.append("Malnutrition Risk")
        else:
            cleaned.append(condition)

    # Drop any conditions that scoring.py doesn't have rules for
    return [c for c in cleaned if c in KNOWN_CONDITIONS]


# Score every patient against every dish and return rows for the meal_scores table
def score_all_meals(dishes, patients):
    rows = []

    for patient in patients:
        conditions = conditions_for_scoring(patient)

        for dish_name, category, kostform in dishes:
            nutrients = nutrients_for_dish(dish_name, category)
            result = score_meal(nutrients, conditions)

            rows.append({
                "patient_id": patient["id"],
                "dish_name": dish_name,
                "category": category,
                "conditions": ", ".join(conditions),
                "score": result["score"],
                "grade": result["grade"],
                "grade_description": result["grade_description"],
                "flag_count": len(result["flags"]),
                "energy_kcal": nutrients["energy_kcal"],
                "protein_g": nutrients["protein_g"],
                "fiber_g": nutrients["fiber_g"],
                "calcium_mg": nutrients["calcium_mg"],
                "sodium_mg": nutrients["sodium_mg"],
                "fat_sat_g": nutrients["fat_sat_g"],
                "sugar_g": nutrients["sugar_g"],
            })

    return rows


# Create the empty tables in the SQLite database
def create_tables(connection):
    cursor = connection.cursor()

    # Each CREATE TABLE statement defines one table in the database
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

        # Insert one row per condition with its status
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
    # Step 1: load the Frida database
    print("Loading Frida database...")
    frida_df = load_frida(FRIDA_FILE)
    print("Loaded " + str(len(frida_df)) + " foods from Frida")

    # Step 2: load all dishes and their ingredients
    print("Loading dishes...")
    dishes, dish_ings, unique_ingredients = load_dishes(DISH_FILE)
    print("Loaded " + str(len(dishes)) + " dishes with " + str(len(unique_ingredients)) + " unique ingredients")

    # Step 3: match every unique ingredient against Frida
    print("Matching ingredients to Frida...")
    matches = {}
    for ingredient in sorted(unique_ingredients):
        matches[ingredient] = match_ingredient(ingredient, frida_df)

    flagged_count = 0
    for match in matches.values():
        if match["flagged_for_review"]:
            flagged_count = flagged_count + 1
    print("Matched " + str(len(matches)) + " ingredients (" + str(flagged_count) + " flagged for review)")

    # Step 4: score every meal for every patient
    print("Scoring meals for each patient...")
    meal_score_rows = score_all_meals(dishes, PATIENTS)
    print("Computed " + str(len(meal_score_rows)) + " patient-meal scores")

    # Step 5: build the SQLite database
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

    print("Done. Database is ready.")
