"""
scoring.py
----------
Responsibility:
- Take a fully enriched meal dict (from pdf_extractor.py) and a patient's conditions
- Look up nutrients via the meal's already-computed nutrient dict
- Apply condition-specific multipliers (NNR 2023 + Institutionskost 2025)
- Return a detailed score: letter grade A-E, flags, per-nutrient breakdown
 
Nutrient thresholds are based on:
    Nordic Nutrition Recommendations 2023 (NNR 2023)
    Anbefalinger for den danske institutionskost 2025
 
Per-meal targets assume 3 main meals/day for an elderly person (~1800-2200 kcal/day):
    Energy:    600-750 kcal
    Protein:   20-30 g     (NNR: 1.2-1.4 g/kg/day for elderly)
    Fibre:     6-8 g       (NNR: 25 g/day total)
    Calcium:   250-350 mg  (NNR: 800-1000 mg/day)
    Sodium:    <600 mg     (NNR: <5 g salt/day = <2000 mg sodium)
    Sat fat:   <8 g        (NNR: <10% of energy from saturated fat)
 
Note on sodium: nutrient_lookup.py stores sodium in mg (as Frida does).
All sodium thresholds in this module are therefore in mg.
 
Usage:
    from pipeline.scoring import score_meal, score_week
 
    result = score_meal(enriched_meal, conditions=["Hypertension", "Osteoporosis"])
    weekly = score_week(list_of_results)
 
Run directly to test:
    python pipeline/scoring.py
"""
 
from typing import Dict, List
 
 
# ---------------------------------------------------------------------------
# Per-meal nutrient targets (NNR 2023 + Institutionskost 2025)
# min:    below this is a deficiency penalty
# target: reaching this gives a full reward
# max:    above this is an excess penalty
# ---------------------------------------------------------------------------
 
TARGETS = {
    "energy_kcal": {"min": 500,   "target": 700,  "max": 1000,  "unit": "kcal"},
    "protein_g":   {"min": 20,    "target": 25,   "max": None,  "unit": "g"},
    "fiber_g":     {"min": 5,     "target": 8,    "max": None,  "unit": "g"},
    "calcium_mg":  {"min": 200,   "target": 300,  "max": None,  "unit": "mg"},
    "sodium_mg":   {"min": None,  "target": 500,  "max": 750,   "unit": "mg"},
    "fat_sat_g":   {"min": None,  "target": 8.0,  "max": 12.0,  "unit": "g"},
    "sugar_g":     {"min": None,  "target": 12,   "max": 25,    "unit": "g"},
    "potassium_mg": {"min": 800, "target": 1100, "max": None, "unit": "mg"},
}
 
# ---------------------------------------------------------------------------
# Condition multipliers
# Format: condition -> {nutrient: (direction, multiplier)}
#   direction:   "penalty" = bad nutrient gets penalised harder
#                "reward"  = good nutrient gets rewarded more
#   multiplier:  stacks multiplicatively across multiple conditions
# ---------------------------------------------------------------------------
 
CONDITION_MULTIPLIERS = {
    "Hypertension": {
        "sodium_mg":  ("penalty", 2.5),
        "fat_sat_g":  ("penalty", 1.3),
        "fiber_g":    ("reward",  1.2),
    },
    "Type 2 Diabetes": {
        "sugar_g":    ("penalty", 2.5),
        "fiber_g":    ("reward",  1.5),
        "energy_kcal": ("penalty", 1.3),
    },
    "Osteoporosis": {
        "calcium_mg": ("reward",  2.0),
        "protein_g":  ("reward",  1.3),
    },
    "Malnutrition Risk": {
        "protein_g":  ("reward",  2.0),
        "energy_kcal": ("reward", 0.5),   # gentler energy penalty for low appetite
    },
    "High Cholesterol": {
        "fat_sat_g":  ("penalty", 2.0),
        "fiber_g":    ("reward",  1.5),
    },
}
 
# ---------------------------------------------------------------------------
# Grade thresholds  (lower score = better)
# ---------------------------------------------------------------------------
 
GRADE_THRESHOLDS = [
    ("A", float("-inf"), -2,   "Excellent nutritional balance"),
    ("B", -2,             2,   "Good — minor improvements possible"),
    ("C",  2,             7,   "Adequate — improvements recommended"),
    ("D",  7,             13,  "Poor — action recommended"),
    ("E",  13, float("inf"),   "Critical — immediate review needed"),
]
 
 
# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
 
def _get_multipliers(nutrient: str, conditions: List[str]):
    """Returns combined penalty and reward multipliers for a nutrient."""
    penalty_mult = 1.0
    reward_mult  = 1.0
    for cond in conditions:
        effect = CONDITION_MULTIPLIERS.get(cond, {}).get(nutrient)
        if effect:
            direction, mult = effect
            if direction == "penalty":
                penalty_mult *= mult
            else:
                reward_mult *= mult
    return penalty_mult, reward_mult
 
 
def _score_nutrient(nutrient: str, value: float, conditions: List[str]):
    """
    Calculates the score contribution for one nutrient.
 
    Returns:
        contribution (float): negative = good (reward), positive = bad (penalty)
        flags (list[str]):    clinical alert messages for this nutrient
    """
    t = TARGETS[nutrient]
    penalty_mult, reward_mult = _get_multipliers(nutrient, conditions)
    contribution = 0.0
    flags = []
 
    # --- Excess penalty (value above max) ---
    if t["max"] is not None and value >= t["max"]:
        overage = max(value - t["target"], 0)
        base = (overage / t["max"]) * 5
        contribution += min(base * penalty_mult, 8.0)  # cap so no single nutrient dominates
 
        if nutrient == "sodium_mg":
            flags.append(
                f"⚠ Sodium {value:.0f} mg exceeds limit ({t['max']} mg). "
                "Review sodium-rich components."
            )
        elif nutrient == "fat_sat_g":
            flags.append(
                f"⚠ Saturated fat {value:.1f} g exceeds limit ({t['max']} g). "
                "Consider lower-fat alternatives."
            )
        elif nutrient == "sugar_g":
            flags.append(
                f"⚠ Sugar {value:.1f} g exceeds limit ({t['max']} g). "
                "Review dessert and sweetened components."
            )
        elif nutrient == "energy_kcal":
            flags.append(
                f"⚠ Energy {value:.0f} kcal exceeds recommended range ({t['max']} kcal). "
                "Review portion sizes."
            )
        
    # --- Graduated penalty for target→max zone (penalty-only nutrients) ---
    if t["min"] is None and t["max"] is not None and t["target"] < value < t["max"]:
        zone_ratio = (value - t["target"]) / max(t["max"] - t["target"], 0.001)
        partial = zone_ratio * 2.0 * penalty_mult
        contribution += partial

 
    # --- Deficiency penalty (value below min) ---
    if t["min"] is not None and value < t["min"]:
        shortfall = t["min"] - value
        base = (shortfall / t["min"]) * 3
        contribution += base * penalty_mult
 
        if nutrient == "protein_g":
            flags.append(
                f"⚠ Protein {value:.1f} g below minimum ({t['min']} g). "
                "Risk of muscle loss in elderly patients."
            )
        elif nutrient == "fiber_g":
            flags.append(
                f"⚠ Fibre {value:.1f} g below minimum ({t['min']} g). "
                "Consider adding whole grains or vegetables."
            )
        elif nutrient == "calcium_mg":
            flags.append(
                f"⚠ Calcium {value:.0f} mg below minimum ({t['min']} mg). "
                "Below recommended level for bone health."
            )
        elif nutrient == "energy_kcal":
            flags.append(
                f"⚠ Energy {value:.0f} kcal below minimum ({t['min']} kcal). "
                "May indicate insufficient portion size."
            )
 
    # --- Reward (value meets or approaches target) ---
    if t["min"] is not None and value >= t["min"]:
        if value >= t["target"]:
            base = 2.0
        else:
            ratio = (value - t["min"]) / max(t["target"] - t["min"], 0.001)
            base = 1.0 * ratio
        contribution -= base * reward_mult
 
    return round(contribution, 3), flags
 
 
def _score_to_grade(score: float):
    """Maps a numeric score to a letter grade and description."""
    for grade, low, high, desc in GRADE_THRESHOLDS:
        if low <= score < high:
            return grade, desc
    return "E", "Critical — immediate review needed"
 
 
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
 
def score_meal(meal_or_nutrients, conditions: List[str]) -> Dict:
    """
    Scores a meal for a patient with the given health conditions.
 
    Args:
        meal_or_nutrients:
            Either a fully enriched meal dict (from pdf_extractor.extract_meals)
            which has a "nutrients" key, or a plain nutrients dict directly.
        conditions:
            List of condition name strings, e.g. ["Hypertension", "Osteoporosis"].
            Must match keys in CONDITION_MULTIPLIERS.
 
    Returns dict with:
        score (float):           raw numeric score — lower is better
        grade (str):             letter grade A-E
        grade_description (str): human-readable explanation
        flags (list[str]):       clinical alert messages
        nutrient_scores (dict):  per-nutrient score contributions
        condition_effects (list): which conditions affected which nutrients
        nutrients (dict):        the input nutrient values
        conditions (list):       the input conditions
    """
    # Accept either an enriched meal dict or a plain nutrients dict
    if "nutrients" in meal_or_nutrients:
        nutrients = meal_or_nutrients["nutrients"]
    else:
        nutrients = meal_or_nutrients
 
    total_score = 0.0
    all_flags = []
    nutrient_scores = {}
 
    for nutrient in TARGETS:
        value = float(nutrients.get(nutrient, 0.0))
        contribution, flags = _score_nutrient(nutrient, value, conditions)
        total_score += contribution
        nutrient_scores[nutrient] = contribution
        all_flags.extend(flags)
 
    grade, grade_description = _score_to_grade(total_score)
 
    # Record which conditions affected which nutrients
    condition_effects = []
    for cond in conditions:
        if cond in CONDITION_MULTIPLIERS:
            condition_effects.append({
                "condition": cond,
                "affects":   list(CONDITION_MULTIPLIERS[cond].keys()),
            })
 
    return {
        "score":             round(total_score, 2),
        "grade":             grade,
        "grade_description": grade_description,
        "flags":             all_flags,
        "nutrient_scores":   nutrient_scores,
        "condition_effects": condition_effects,
        "nutrients":         nutrients,
        "conditions":        conditions,
    }
 
 
def score_week(meal_results: List[Dict]) -> Dict:
    """
    Calculates a weekly summary from a list of score_meal() results.
 
    Args:
        meal_results: list of dicts as returned by score_meal()
 
    Returns dict with:
        weekly_avg_score (float)
        weekly_grade (str)
        weekly_description (str)
        grade_counts (dict):     {"A": n, "B": n, ...}
        avg_nutrients (dict):    average nutrient values across all meals
        best_meal_index (int):   index of the best-scored meal
        worst_meal_index (int):  index of the worst-scored meal
        all_flags (list[str]):   deduplicated flags across all meals
        meal_count (int)
    """
    if not meal_results:
        return {}
 
    scores = [r["score"] for r in meal_results]
    avg_score = round(sum(scores) / len(scores), 2)
    grade, desc = _score_to_grade(avg_score)
 
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for r in meal_results:
        grade_counts[r["grade"]] += 1
 
    nutrient_keys = list(TARGETS.keys())
    avg_nutrients = {}
    for key in nutrient_keys:
        values = [float(r["nutrients"].get(key, 0)) for r in meal_results]
        avg_nutrients[key] = round(sum(values) / len(values), 2)
 
    # Deduplicated flags
    seen = set()
    all_flags = []
    for r in meal_results:
        for flag in r["flags"]:
            if flag not in seen:
                seen.add(flag)
                all_flags.append(flag)
 
    return {
        "weekly_avg_score":  avg_score,
        "weekly_grade":      grade,
        "weekly_description": desc,
        "grade_counts":      grade_counts,
        "avg_nutrients":     avg_nutrients,
        "best_meal_index":   scores.index(min(scores)),
        "worst_meal_index":  scores.index(max(scores)),
        "all_flags":         all_flags,
        "meal_count":        len(meal_results),
    }
 
 
# ---------------------------------------------------------------------------
# Run directly to test
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    print("Testing scoring.py")
    print("=" * 55)
 
    # These nutrient keys match what nutrient_lookup.py returns
    test_cases = [
        {
            "label": "Bøf stroganoff — Erik (Hypertension + Type 2 Diabetes)",
            "nutrients": {
                "energy_kcal": 680, "protein_g": 38,  "sugar_g": 6,
                "fiber_g": 4,       "fat_sat_g": 9.0,  "calcium_mg": 180,
                "sodium_mg": 820,   "potassium_mg": 600,
            },
            "conditions": ["Hypertension", "Type 2 Diabetes"],
        },
        {
            "label": "Frikadeller — Birthe (Osteoporosis)",
            "nutrients": {
                "energy_kcal": 620, "protein_g": 42,  "sugar_g": 3,
                "fiber_g": 6,       "fat_sat_g": 6.5,  "calcium_mg": 210,
                "sodium_mg": 540,   "potassium_mg": 580,
            },
            "conditions": ["Osteoporosis"],
        },
        {
            "label": "Fiskefrikadeller — Holger (no conditions)",
            "nutrients": {
                "energy_kcal": 520, "protein_g": 35,  "sugar_g": 4,
                "fiber_g": 5,       "fat_sat_g": 4.0,  "calcium_mg": 190,
                "sodium_mg": 480,   "potassium_mg": 500,
            },
            "conditions": [],
        },
    ]
 
    results = []
    for tc in test_cases:
        result = score_meal(tc["nutrients"], tc["conditions"])
        results.append(result)
        print(f"\n{tc['label']}")
        print(f"  Grade:  {result['grade']}  —  {result['grade_description']}")
        print(f"  Score:  {result['score']}")
        if result["flags"]:
            for flag in result["flags"]:
                print(f"  {flag}")
        else:
            print("  No flags.")
 
    print("\n" + "=" * 55)
    print("Weekly summary (all 3 meals)")
    weekly = score_week(results)
    print(f"  Weekly grade:  {weekly['weekly_grade']}  —  {weekly['weekly_description']}")
    print(f"  Avg score:     {weekly['weekly_avg_score']}")
    print(f"  Grade counts:  {weekly['grade_counts']}")
    print(f"  Best meal:     index {weekly['best_meal_index']}")
    print(f"  Worst meal:    index {weekly['worst_meal_index']}")
    print(f"  Unique flags:  {len(weekly['all_flags'])}")