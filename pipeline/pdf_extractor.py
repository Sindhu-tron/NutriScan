"""
pdf_extractor.py
----------------
Responsibility:
- Parse a Madservice Roskilde menu PDF into structured meal dicts (via menu_parser)
- Enrich each meal with ingredient data from dish_ingredients.json
- Look up nutrient values for each enriched meal via nutrient_lookup.py
- Return fully enriched meal dicts ready for scoring.py

This is the bridge between the raw PDF and the scoring pipeline.
menu_parser.py handles the low-level PDF parsing (column splitting, day detection).
This module handles the semantic enrichment: what ingredients are in this dish,
and what are the nutrients?

Input:  Path to a menu PDF (e.g. sample_data/menuplan-marts-2026.pdf)
Output: List of fully enriched meal dicts, one per day, with keys:
            - day_number (int)
            - day_name (str)
            - main (str)
            - sides (list of str)
            - dessert (str)
            - vegetarian (bool)
            - main_ingredients (list of str)       from dish_ingredients.json
            - main_amounts_g (list of float)        from dish_ingredients.json
            - dessert_ingredients (list of str)
            - dessert_amounts_g (list of float)
            - nutrients (dict)                      aggregated from nutrient_lookup.py
            - matched (list)                        ingredients found in Frida
            - unmatched (list)                      ingredients not found in Frida
            - coverage_pct (int)                    % of ingredients matched

Usage:
    from pipeline.pdf_extractor import extract_meals
    meals = extract_meals("sample_data/menuplan-marts-2026.pdf")

Run directly to test:
    python pipeline/pdf_extractor.py sample_data/menuplan-marts-2026.pdf
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Works whether run from project root or from inside pipeline/
try:
    from pipeline.menu_parser import parse_menu
    from pipeline.nutrient_lookup import nutrients_for_food, aggregate_nutrients
    from pipeline.frida_matcher import load_frida, match_ingredient
except ImportError:
    from menu_parser import parse_menu
    from nutrient_lookup import nutrients_for_food, aggregate_nutrients
    from frida_matcher import load_frida, match_ingredient

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DISH_INGREDIENTS_PATH = PROJECT_ROOT / "sample_data" / "dish_ingredients.json"

# ---------------------------------------------------------------------------
# dish_ingredients.json loader (cached)
# ---------------------------------------------------------------------------

_DISH_DB = None

# Cache for the Frida Food sheet (used by frida_matcher)
_FRIDA_FOOD_DF = None


def _get_frida_food_df():
    """
    Loads and caches the Frida Food sheet for use by frida_matcher.
    Loaded once on first call, then reused for all subsequent ingredient lookups.
    """
    global _FRIDA_FOOD_DF
    if _FRIDA_FOOD_DF is None:
        frida_path = PROJECT_ROOT / "data" / "Frida_5.5_Dataset.xlsx"
        _FRIDA_FOOD_DF = load_frida(str(frida_path))
    return _FRIDA_FOOD_DF


def _load_dish_db():
    """
    Loads dish_ingredients.json and returns a flat dict:
        dish_name (str) -> {"ingredients": [...], "amounts_g": [...], "kostform": str}

    Merges all categories (meat, fish, vegetarian, desserts) into one lookup.
    Cached after first load.
    """
    global _DISH_DB
    if _DISH_DB is not None:
        return _DISH_DB

    if not DISH_INGREDIENTS_PATH.exists():
        raise FileNotFoundError(
            f"dish_ingredients.json not found at: {DISH_INGREDIENTS_PATH}\n"
            "Make sure it is in sample_data/."
        )

    with open(DISH_INGREDIENTS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    merged = {}
    for category, dishes in raw.items():
        if category == "_metadata":
            continue
        if isinstance(dishes, dict):
            for dish_name, dish_data in dishes.items():
                merged[dish_name] = dish_data

    _DISH_DB = merged
    return merged


# ---------------------------------------------------------------------------
# Dish matching
# ---------------------------------------------------------------------------

def _find_dish(dish_name: str, dish_db):
    """
    Finds ingredient data for a dish name from dish_ingredients.json.

    Match order:
        1. Exact match
        2. Case-insensitive exact match
        3. Partial match (one contains the other)

    Returns None if no match found.
    """
    if not dish_name:
        return None

    # Exact
    if dish_name in dish_db:
        return dish_db[dish_name]

    # Case-insensitive exact
    lower = dish_name.strip().lower()
    for key, val in dish_db.items():
        if key.lower() == lower:
            return val

    # Partial — e.g. "Frikadeller (vegetarisk)" matches "Frikadeller"
    for key, val in dish_db.items():
        if key.lower() in lower or lower in key.lower():
            return val

    return None


# ---------------------------------------------------------------------------
# Nutrient lookup helpers
# ---------------------------------------------------------------------------

EMPTY_NUTRIENTS = {
    "energy_kcal": 0.0,
    "protein_g":   0.0,
    "fat_sat_g":   0.0,
    "fiber_g":     0.0,
    "sugar_g":     0.0,
    "sodium_mg":   0.0,
    "potassium_mg": 0.0,
    "calcium_mg":  0.0,
}


def _lookup_component(name: str, ingredients: list, amounts_g: list) -> dict:
    """
    Looks up nutrients for a list of ingredients using nutrient_lookup.py.

    Returns:
        nutrients (dict):   aggregated nutrient totals
        matched (list):     ingredients found in Frida
        unmatched (list):   ingredients not found in Frida
        coverage_pct (int): percentage of ingredients matched
    """
    frida_food_df = _get_frida_food_df()
    profiles = []
    matched = []
    unmatched = []

    for ingredient, amount in zip(ingredients, amounts_g):
        # Step 1: translate raw Danish ingredient name to exact Frida food name
        match_result = match_ingredient(ingredient, frida_food_df)
        frida_name = match_result["matched_name"]

        # Step 2: skip if frida_matcher flagged this as an uncertain match
        if match_result["flagged_for_review"]:
            unmatched.append(ingredient)
            continue

        # Step 3: look up nutrient values using the translated Frida name
        try:
            profile = nutrients_for_food(frida_name, amount)
            profiles.append(profile)
            matched.append({"ingredient": ingredient, "amount_g": amount})
        except KeyError:
            unmatched.append(ingredient)

    nutrients = aggregate_nutrients(profiles) if profiles else dict(EMPTY_NUTRIENTS)
    total = len(matched) + len(unmatched)
    coverage = round(len(matched) / total * 100) if total > 0 else 0

    return {
        "nutrients":    nutrients,
        "matched":      matched,
        "unmatched":    unmatched,
        "coverage_pct": coverage,
    }


# ---------------------------------------------------------------------------
# Meal enrichment
# ---------------------------------------------------------------------------

def _enrich_meal(meal: dict, dish_db: dict) -> dict:
    """
    Takes a raw meal dict from menu_parser and adds ingredients + nutrients.

    Combines nutrient contributions from main dish, sides, and dessert.
    """
    enriched = dict(meal)
    all_profiles = []
    all_matched = []
    all_unmatched = []

    # --- Main dish ---
    main_data = _find_dish(meal.get("main", ""), dish_db)
    if main_data:
        main_ingredients = main_data.get("ingredients", [])
        main_amounts = main_data.get("amounts_g", [100] * len(main_ingredients))
        result = _lookup_component(meal["main"], main_ingredients, main_amounts)
        all_profiles.append(result["nutrients"])
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])
        enriched["main_ingredients"]   = main_ingredients
        enriched["main_amounts_g"]     = main_amounts
        enriched["main_coverage_pct"]  = result["coverage_pct"]
    else:
        enriched["main_ingredients"]   = []
        enriched["main_amounts_g"]     = []
        enriched["main_coverage_pct"]  = 0

    # --- Sides (each side is a single ingredient, default 100g portion) ---
    sides = meal.get("sides", [])
    if sides:
        result = _lookup_component("sides", sides, [100] * len(sides))
        all_profiles.append(result["nutrients"])
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])

    # --- Dessert ---
    dessert_data = _find_dish(meal.get("dessert", ""), dish_db)
    if dessert_data:
        dessert_ingredients = dessert_data.get("ingredients", [])
        dessert_amounts = dessert_data.get("amounts_g", [100] * len(dessert_ingredients))
        result = _lookup_component(meal["dessert"], dessert_ingredients, dessert_amounts)
        all_profiles.append(result["nutrients"])
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])
        enriched["dessert_ingredients"]  = dessert_ingredients
        enriched["dessert_amounts_g"]    = dessert_amounts
        enriched["dessert_coverage_pct"] = result["coverage_pct"]
    else:
        enriched["dessert_ingredients"]  = []
        enriched["dessert_amounts_g"]    = []
        enriched["dessert_coverage_pct"] = 0

    # --- Aggregate full-meal nutrients ---
    enriched["nutrients"]    = aggregate_nutrients(all_profiles) if all_profiles else dict(EMPTY_NUTRIENTS)
    enriched["matched"]      = all_matched
    enriched["unmatched"]    = all_unmatched
    total = len(all_matched) + len(all_unmatched)
    enriched["coverage_pct"] = round(len(all_matched) / total * 100) if total > 0 else 0

    return enriched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_meals(pdf_path: str) -> List[Dict]:
    """
    Parses a menu PDF and returns fully enriched meal dicts ready for scoring.

    Args:
        pdf_path: Path to the Roskilde menu PDF

    Returns:
        List of enriched meal dicts, one per day.
    """
    raw_meals = parse_menu(pdf_path)
    dish_db   = _load_dish_db()
    return [_enrich_meal(meal, dish_db) for meal in raw_meals]


# ---------------------------------------------------------------------------
# Run directly to test
# Example: python pipeline/pdf_extractor.py sample_data/menuplan-marts-2026.pdf
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else str(
        PROJECT_ROOT / "sample_data" / "menuplan-marts-2026.pdf"
    )

    print(f"Extracting: {pdf_path}\n")
    meals = extract_meals(pdf_path)
    print(f"Found {len(meals)} meals\n")

    warnings = 0
    for meal in meals:
        veg = " [VEGETARISK]" if meal.get("vegetarian") else ""
        print(f"Day {meal['day_number']} {meal['day_name']}{veg}")
        print(f"  Main:     {meal['main']}  ({len(meal['main_ingredients'])} ingredients)")
        print(f"  Dessert:  {meal['dessert']}  ({len(meal['dessert_ingredients'])} ingredients)")
        print(f"  Sides:    {meal['sides']}")
        print(f"  Coverage: {meal['coverage_pct']}%")
        n = meal["nutrients"]
        print(f"  Nutrients: energy={n.get('energy_kcal',0):.0f} kcal  "
              f"protein={n.get('protein_g',0):.1f}g  "
              f"fibre={n.get('fiber_g',0):.1f}g  "
              f"calcium={n.get('calcium_mg',0):.0f}mg  "
              f"sodium={n.get('sodium_mg',0):.0f}mg")
        if meal["unmatched"]:
            print(f"  ⚠ Unmatched ingredients: {meal['unmatched']}")
            warnings += 1
        print()

    print(f"Done. {len(meals)} meals, {warnings} with unmatched ingredients.")
