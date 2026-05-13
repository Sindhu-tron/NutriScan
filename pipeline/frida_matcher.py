import pandas as pd
from rapidfuzz import process, fuzz

# If the match score is below this number, we flag it so someone can check it manually
# We use 50 instead of 80 because short Danish ingredient words like "2løg" or "2æg2" naturally score lower against longer Frida names, even when the match is correct.
THRESHOLD = 50

# Manual overrides for ingredients that fuzzy matching consistently get wrong. 
# Key: the ingredient name as it appears in dish_ingredients.json
# Value: the exact Danish name as it appears in the Frida Food sheet (FødevareNavn).
# Add new entries here whenever a flagged ingredient has a clearly wrong match.
MANUAL_OVERRIDES = {
    "æg":           "Æg, høne, æggehvide, rå",
    "løg":          "Løg, rå",
    "oksekød":      "Oksekød, inderlår uden kappe, rå",
    "svinekød":     "Kalv- og svinekød, hakket kalv og flæsk, 15-20% fedt, råt",
    "sukker":       "Sukker, stødt melis (sakkarose)",
    "smør":         "Smør, usaltet",
    "fløde":        "Fløde 38 %, piskefløde",
    "mælk":         "Sødmælk, konventionel (ikke-økologisk)",
    "kartoffel":    "Kartoffel, uspec., rå",
    "ost":          "Ost, fast, 45+, alle typer",
    "salt":         "Salt, bordsalt (jodberiget)",
    "oksebouillon": "Bouillon, oksekød, terning, spiseklar",
    "torsk":        "Torsk, filet, rå",
    "fiskefilet":   "Torsk, filet, rå",
    "ris":          "Risengryn, grødris, brune, rå",
    "pasta":        "Pasta, rå",
    "æbler":        "Æble, uspec., råt",
    "peberfrugt":     "Peberfrugt, rød, rå",
    "laks":           "Laks, atlantisk, vild, rå",
    "valnød":        "Valnød, tørret",
    "gulerod":       "Gulerod, uspec., rå",
    "tomat":         "Tomat, uspec., rå",
    "karry":         "Karry, pulver",
    "kaffe":         "Kaffe, drikkeklar",
    "yoghurt":      "Yoghurt naturel, sødmælk",
    "kalvekød":     "Kalvekød, helt magert, råt",
    "skinke":       "Skinke, kogt, skiveskåret",
    "kikærter":     "Kikærter, tørrede, rå",
    "kalkun":       "Kalkun, kød, rå",
    "bacon":        "Bacon i skiver, rå",
    "ymer":         "Ymer naturel",
    "ladyfinger":   "Kiks, Marie",

    # plantefars has no entry in Frida 5.5 — will be flagged and left unmatched
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
    query_lower = ingredient.strip().lower()

    # Step 1: check the manual override dict first
    # These are known good mappings for ingredients that fuzzy matching gets wrong because the query word is short or appears inside many unrelated Frida names. 
    override = MANUAL_OVERRIDES.get(query_lower)
    if override:
        override_rows = frida_df[frida_df["FødevareNavn"] == override]
        if not override_rows.empty:
            frida_id = override_rows.iloc[0]["FoodID"]
            return {
                "query": ingredient,
                "matched_name": override,
                "frida_id": frida_id,
                "confidence": 100.0,
                "flagged_for_review": False
            }


    # Step 2: Find candidates whose Frida name contains the query as a substring.
    # This filters out clearly irrelevant entries before scoring.
    candidates = [
        (i, name) for i, name in enumerate(food_names)
        if query_lower in name.lower()
    ]

    # Step 3: If no candidates contain the query as a substring (e.g. spelling variation
    # or an ingredient name with no direct substring match), fall back to full fuzzy search.
    if not candidates:
        best_match, score, index = process.extractOne(ingredient, food_names, scorer=fuzz.token_set_ratio)
        frida_id = frida_df.iloc[index]["FoodID"]
        reported_score = round(score, 1)
        return {
            "query": ingredient,
            "matched_name": best_match,
            "frida_id": frida_id,
            "confidence": reported_score,
            "flagged_for_review": reported_score < THRESHOLD
        }
    
    # Step 4: among the substring candidates, pick the shortest name.
    # The shortest matching Frida name is almost always the most generic raw ingredient.
    # For example "Løg, rå" (7 chars) is preferred over "Løg, kogt, drænet" (18 chars).
    best_index, best_name = min(candidates, key=lambda x: len(x[1]))

    frida_id = frida_df.iloc[best_index]["FoodID"]
    reported_score = round(fuzz.token_set_ratio(ingredient, best_name), 1)

    result = {
        "query": ingredient,
        "matched_name": best_name,
        "frida_id": frida_id,
        "confidence": reported_score,
        "flagged_for_review": reported_score < THRESHOLD
    }

    return result

# This function matches a whole list of ingredients at once
def match_all_ingredients(ingredients, frida_df):
    all_results = []

    # Loop through each ingredient and match it
    for ingredient in ingredients:
        result = match_ingredient(ingredient, frida_df)
        all_results.append(result)

    # Convert the list to a dataframe so it is easier to work with
    results_df = pd.DataFrame(all_results)

    return results_df


# Test the code with some example ingredients from the REH menu
if __name__ == "__main__":
    # Ask the user for the path to the Frida file instead of hardcoding it
    filepath = input("Enter the path to the Frida Excel file: ")

    # Load the Frida database
    frida_df = load_frida(filepath)

    # Print how many foods were loaded
    number_of_foods = len(frida_df)
    print("Loaded " + str(number_of_foods) + " foods from Frida database")

    # Some example ingredients from the dish_ingredients.json file
    ingredients = [
        "oksekød",
        "champignon",
        "creme fraiche",
        "torskefilet",
        "kartoffel",
        "løg",
    ]

    results = match_all_ingredients(ingredients, frida_df)

    print("Match Results:")
    print(results)

    # Show which ingredients need to be checked manually
    flagged = results[results["flagged_for_review"] == True]

    if len(flagged) > 0:
        # Print how many ingredients need to be checked
        number_of_flagged = len(flagged)
        print("Warning: " + str(number_of_flagged) + " ingredient(s) need manual review:")
        print(flagged[["query", "matched_name", "confidence"]])
    else:
        print("All ingredients matched successfully!")

 # data/Frida_5.5_Dataset.xlsx