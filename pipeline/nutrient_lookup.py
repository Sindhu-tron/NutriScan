"""
nutrient_lookup.py

Responsibility:
- Load the Frida 5.5 food composition dataset
- Retrieve nutrient values per 100 g using Frida ParameterIDs
- Scale nutrients by ingredient amounts (grams)
- Aggregate nutrients across multiple ingredients

Design notes:
- Frida 5.5 stores nutrients as numeric ParameterIDs rather than stable
  textual column names. Nutrient lookup therefore uses these ParameterIDs
  directly for robustness and unambiguous access.
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd


# These values correspond to column headers when loading Data_Table with header=3.
NUTRIENT_COLUMNS = {
    "energy_kcal": "356",   # 356 → Energy (kcal)
    "protein_g": "218",     # 218 → Protein (g)
    "fat_sat_g": "248",     # 248 → Saturated fat (g)
    "fiber_g": "168",       # 168 → Fibre (g)
    "sugar_g": "245",       # 245 → Sugar (g)
    "sodium_mg": "201",     # 201 → Sodium (mg)
    "potassium_mg": "165",  # 165 → Potassium (mg)
    "calcium_mg": "108",    # 108 → Calcium (mg)
}


# --- INTERNAL DATASET CACHE ---
_FRIDA_DF = None


# --- DATASET LOADING ---
def load_frida_dataset():
    """
    Loads and normalizes the Frida 5.5 Data_Table.

    Resulting DataFrame:
    - index   → Frida food names (e.g. 'Banana, raw')
    - columns → Nutrient ParameterIDs (per 100 g)
    """
    global _FRIDA_DF

    if _FRIDA_DF is not None:
        return _FRIDA_DF

    project_root = Path(__file__).resolve().parents[1]
    frida_path = project_root / "sample_data" / "Frida_5.5_Dataset.xlsx"

    if not frida_path.exists():
        raise FileNotFoundError(f"Frida dataset not found: {frida_path}")

    # Load Frida using the real nutrient header row and food-name column
    df = pd.read_excel(
        frida_path,
        sheet_name="Data_Table",
        header=3,     # nutrient ParameterIDs
        index_col=0,  # food names
        engine="openpyxl",
    )

    # Normalize food names
    df.index = df.index.astype(str).str.strip()

    # Normalize column names (ParameterIDs as strings)
    df.columns = df.columns.astype(str).str.strip()

    _FRIDA_DF = df
    return df


# --- CORE NUTRIENT LOOKUP ---
def nutrients_for_food(food_name: str, grams: float) -> Dict[str, float]:
    """
    Returns scaled nutrient values for a single ingredient,
    identified by its canonical Frida food name.

    Args:
        food_name: Exact Frida food name (row index)
        grams: Amount consumed (grams)

    Returns:
        Dictionary of nutrient values scaled to the given amount,
        rounded to two decimals.
    """
    df = load_frida_dataset()

    if food_name not in df.index:
        raise KeyError(f"No Frida entry found for food name: {food_name}")

    row = df.loc[food_name]
    scale = grams / 100.0

    nutrients: Dict[str, float] = {}

    for nutrient, parameter_id in NUTRIENT_COLUMNS.items():
        if parameter_id not in df.columns:
            raise KeyError(
                f"Frida ParameterID not found in dataset: {parameter_id}"
            )

        value_per_100g = row[parameter_id]

        scaled_value = (
            0.0 if pd.isna(value_per_100g)
            else float(value_per_100g) * scale
        )

        # Round all outputs to two decimals
        nutrients[nutrient] = round(scaled_value, 2)

    return nutrients


# --- AGGREGATION ---
def aggregate_nutrients(
        nutrient_profiles: List[Dict[str, float]]
) -> Dict[str, float]:
    """
    Aggregates multiple nutrient dictionaries by summation.

    Returns:
        Dictionary with summed nutrient totals rounded to two decimals.
    """
    totals: Dict[str, float] = {}

    for profile in nutrient_profiles:
        for nutrient, value in profile.items():
            totals[nutrient] = totals.get(nutrient, 0.0) + value

    # Round aggregated totals
    return {k: round(v, 2) for k, v in totals.items()}
