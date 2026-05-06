"""
frida_matcher.py
----------------
Responsibility:
- Load food names from the Frida 5.5 Data_Table (same sheet as nutrient_lookup.py)
- Fuzzy match Danish ingredient names to exact Frida food names

"""

import pandas as pd
from rapidfuzz import process, fuzz

# Matches below this confidence score are flagged for manual review
THRESHOLD = 80


def load_frida(filepath):
    """
    Loads food names from the Frida 5.5 Data_Table sheet.

    """
    df = pd.read_excel(
        filepath,
        sheet_name="Data_Table",
        header=3,
        index_col=0,
        engine="openpyxl",
    )

    food_names = df.index.astype(str).str.strip()

    result = pd.DataFrame({
        "FødevareNavn": food_names,
        "FoodID": range(len(food_names))
    }).reset_index(drop=True)

    result = result.dropna(subset=["FødevareNavn"])
    result = result[result["FødevareNavn"] != "nan"]
    result = result[result["FødevareNavn"].str.len() > 1]

    return result


def match_ingredient(ingredient, frida_df):
    """
    Finds the best matching Frida food name for a Danish ingredient name.

    Args:
        ingredient: Danish ingredient name (e.g. "oksekød", "kartoffel")
        frida_df:   DataFrame from load_frida()

    Returns:
        dict with keys: query, matched_name, frida_id, confidence,
        flagged_for_review
    """
    food_names = frida_df["FødevareNavn"].tolist()

    best_match, score, index = process.extractOne(
        ingredient, food_names, scorer=fuzz.WRatio
    )

    frida_id = frida_df.iloc[index]["FoodID"]
    score = round(score, 1)

    return {
        "query":              ingredient,
        "matched_name":       best_match,
        "frida_id":           frida_id,
        "confidence":         score,
        "flagged_for_review": score < THRESHOLD,
    }


def match_all_ingredients(ingredients, frida_df):
    """
    Matches a list of ingredient names against Frida all at once.
    """
    results = [match_ingredient(ing, frida_df) for ing in ingredients]
    return pd.DataFrame(results)


if __name__ == "__main__":
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    filepath = str(project_root / "sample_data" / "Frida_5.5_Dataset.xlsx")

    print(f"Loading Frida from: {filepath}\n")
    frida_df = load_frida(filepath)
    print(f"Loaded {len(frida_df)} foods from Frida Data_Table\n")

    ingredients = [
        "oksekød", "svinekød", "kylling", "torskefilet",
        "champignon", "løg", "kartoffel", "mælk",
        "æg", "fløde", "smør", "hvedemel", "sukker", "rasp",
    ]

    print("Match results:")
    print("-" * 65)
    results = match_all_ingredients(ingredients, frida_df)
    for _, row in results.iterrows():
        flag = " ⚠ LOW CONFIDENCE" if row["flagged_for_review"] else ""
        print(f"  {row['query']:<20} → {row['matched_name']:<35} ({row['confidence']}%){flag}")

    flagged = results[results["flagged_for_review"] == True]
    print()
    if len(flagged) > 0:
        print(f"⚠ {len(flagged)} ingredient(s) need manual review")
    else:
        print("✓ All ingredients matched with high confidence")
