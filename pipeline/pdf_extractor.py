"""
pdf_extractor.py
----------------
Responsibility:
- Parse a Madservice Roskilde menu PDF into structured meal dicts (via menu_parser)
- Enrich each meal with ingredient data from dish_ingredients.json
- Match ingredient names to Frida via frida_matcher.py (fuzzy matching)
- Look up nutrient values for each enriched meal via nutrient_lookup.py
- Return fully enriched meal dicts ready for scoring.py
 
Pipeline flow:
    PDF → menu_parser → dish_ingredients.json → frida_matcher → nutrient_lookup → scoring
 
Input:  Path to a menu PDF (e.g. sample_data/menuplan-marts-2026.pdf)
Output: List of fully enriched meal dicts, one per day, with keys:
            - day_number, day_name, main, sides, dessert, vegetarian
            - main_ingredients, main_amounts_g
            - dessert_ingredients, dessert_amounts_g
            - nutrients (dict)        aggregated from nutrient_lookup.py
            - matched (list)          ingredients matched in Frida
            - unmatched (list)        ingredients not matched
            - flagged (list)          low-confidence matches for review
            - coverage_pct (int)      % of ingredients matched
 
Usage:
    from pipeline.pdf_extractor import extract_meals
    meals = extract_meals("sample_data/menuplan-marts-2026.pdf")
 
Run directly to test:
    python -m pipeline.pdf_extractor sample_data/menuplan-marts-2026.pdf
"""
 
import json
import sys
from pathlib import Path
 
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
FRIDA_PATH = PROJECT_ROOT / "data" / "Frida_5.5_Dataset.xlsx"
 
# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------
 
_DISH_DB = None
_FRIDA_DF = None
 
 
def _load_dish_db():
    global _DISH_DB
    if _DISH_DB is not None:
        return _DISH_DB
 
    if not DISH_INGREDIENTS_PATH.exists():
        raise FileNotFoundError(
            f"dish_ingredients.json not found at: {DISH_INGREDIENTS_PATH}"
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
 
 
def _load_frida_df():
    """Loads the Frida Food sheet for fuzzy matching (cached)."""
    global _FRIDA_DF
    if _FRIDA_DF is not None:
        return _FRIDA_DF
 
    if not FRIDA_PATH.exists():
        raise FileNotFoundError(
            f"Frida dataset not found at: {FRIDA_PATH}"
        )
 
    _FRIDA_DF = load_frida(str(FRIDA_PATH))
    return _FRIDA_DF
 
 
# ---------------------------------------------------------------------------
# Dish matching
# ---------------------------------------------------------------------------
 
def _find_dish(dish_name, dish_db):
    """Finds ingredient data for a dish from dish_ingredients.json."""
    if not dish_name:
        return None
 
    if dish_name in dish_db:
        return dish_db[dish_name]
 
    lower = dish_name.strip().lower()
    for key, val in dish_db.items():
        if key.lower() == lower:
            return val
 
    for key, val in dish_db.items():
        if key.lower() in lower or lower in key.lower():
            return val
 
    return None
 
 
# ---------------------------------------------------------------------------
# Nutrient lookup via frida_matcher
# ---------------------------------------------------------------------------
 
EMPTY_NUTRIENTS = {
    "energy_kcal":  0.0,
    "protein_g":    0.0,
    "fat_sat_g":    0.0,
    "fiber_g":      0.0,
    "sugar_g":      0.0,
    "sodium_mg":    0.0,
    "potassium_mg": 0.0,
    "calcium_mg":   0.0,
}
 
 
def _lookup_component(name, ingredients, amounts_g):
    """
    Matches each ingredient via frida_matcher, then looks up nutrients.
 
    Returns:
        nutrients (dict):    aggregated nutrient totals
        matched (list):      successfully looked up ingredients
        unmatched (list):    ingredients that failed nutrient lookup
        flagged (list):      low-confidence fuzzy matches needing review
        coverage_pct (int):  % of ingredients with nutrient data
    """
    frida_df = _load_frida_df()
 
    profiles = []
    matched = []
    unmatched = []
    flagged = []
 
    for ingredient, amount in zip(ingredients, amounts_g):
        # Step 1: fuzzy match ingredient name to a Frida food name
        match_result = match_ingredient(ingredient, frida_df)
        frida_name = match_result["matched_name"]
        confidence = match_result["confidence"]
 
        # Track low-confidence matches for reporting
        if match_result["flagged_for_review"]:
            flagged.append({
                "ingredient": ingredient,
                "matched_to": frida_name,
                "confidence": confidence,
            })
 
        # Step 2: look up nutrients using the matched Frida name
        try:
            profile = nutrients_for_food(frida_name, amount)
            profiles.append(profile)
            matched.append({
                "ingredient": ingredient,
                "frida_name": frida_name,
                "confidence": confidence,
                "amount_g":   amount,
            })
        except KeyError:
            unmatched.append(ingredient)
 
    nutrients = aggregate_nutrients(profiles) if profiles else dict(EMPTY_NUTRIENTS)
    total = len(matched) + len(unmatched)
    coverage = round(len(matched) / total * 100) if total > 0 else 0
 
    return {
        "nutrients":    nutrients,
        "matched":      matched,
        "unmatched":    unmatched,
        "flagged":      flagged,
        "coverage_pct": coverage,
    }
 
 
# ---------------------------------------------------------------------------
# Meal enrichment
# ---------------------------------------------------------------------------
 
def _enrich_meal(meal, dish_db):
    """Enriches a raw meal dict with ingredients and nutrients."""
    enriched = dict(meal)
    all_profiles = []
    all_matched = []
    all_unmatched = []
    all_flagged = []
 
    # --- Main dish ---
    main_data = _find_dish(meal.get("main", ""), dish_db)
    if main_data:
        main_ingredients = main_data.get("ingredients", [])
        main_amounts = main_data.get("amounts_g", [100] * len(main_ingredients))
        result = _lookup_component(meal["main"], main_ingredients, main_amounts)
        all_profiles.append(result["nutrients"])
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])
        all_flagged.extend(result["flagged"])
        enriched["main_ingredients"]  = main_ingredients
        enriched["main_amounts_g"]    = main_amounts
        enriched["main_coverage_pct"] = result["coverage_pct"]
    else:
        enriched["main_ingredients"]  = []
        enriched["main_amounts_g"]    = []
        enriched["main_coverage_pct"] = 0
 
    # --- Sides (each side is a single ingredient, default 100g) ---
    sides = meal.get("sides", [])
    if sides:
        # Specific portion overrides for sides where 100g is unrealistic.
        # Condiments, bread, and sauces are served in much smaller amounts.
        SIDE_PORTIONS = {
            "rugbrød":       60,
            "sennep":        15,
            "ketchup":       20,
            "citron":        20,
            "cremefraiche":  30,
            "rødkål":        60,
            "asier":         40,
            "drueagurker":   40,
            "syltetøj":      20,
            "ribsgele":      20,
            "tyttebær":      30,
            "agurkesalat":   60,
            "waldorfsalat":  80,
            "rødkålssalat":  60,
            "hvidkålssalat": 60,
            "gulerodssalat": 60,
            "gulerodsråkost":60,
            "råkost":        60,
            "dild":          5,
            "persille":      5,
            }
        side_amounts = [SIDE_PORTIONS.get(s.strip().lower(), 80) for s in sides]
        result = _lookup_component("sides", sides, side_amounts)
        all_profiles.append(result["nutrients"])
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])
        all_flagged.extend(result["flagged"])
 
    # --- Dessert ---
    dessert_data = _find_dish(meal.get("dessert", ""), dish_db)
    if dessert_data:
        dessert_ingredients = dessert_data.get("ingredients", [])
        dessert_amounts = dessert_data.get("amounts_g", [100] * len(dessert_ingredients))
        result = _lookup_component(meal["dessert"], dessert_ingredients, dessert_amounts)
        all_profiles.append(result["nutrients"])
        all_matched.extend(result["matched"])
        all_unmatched.extend(result["unmatched"])
        all_flagged.extend(result["flagged"])
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
    enriched["flagged"]      = all_flagged
    total = len(all_matched) + len(all_unmatched)
    enriched["coverage_pct"] = round(len(all_matched) / total * 100) if total > 0 else 0
 
    return enriched
 
 
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
 
def extract_meals(pdf_path):
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
# python -m pipeline.pdf_extractor sample_data/menuplan-marts-2026.pdf
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
 
        if meal["flagged"]:
            print(f"  ⚠ Low-confidence matches:")
            for f in meal["flagged"]:
                print(f"      {f['ingredient']} → {f['frida_name']} ({f['confidence']}%)")
 
        if meal["unmatched"]:
            print(f"  ✗ Unmatched: {meal['unmatched']}")
            warnings += 1
        print()
 
    print(f"Done. {len(meals)} meals, {warnings} with unmatched ingredients.")
 
