import pandas as pd
from rapidfuzz import process, fuzz
import pandas as pd
from rapidfuzz import process, fuzz

# If the match score is below this number, we flag it so someone can check it manually
THRESHOLD = 80

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
    # WRatio is good at matching even if the word order is different
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
if __name__ == "main":
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
