# Import pandas and the functions that will be tested
import pandas as pd

from pipeline.frida_matcher import (
    load_frida,
    match_ingredient,
    match_all_ingredients,
)


# Test exact ingredient matching
def test_match_ingredient_exact_match():

    # Sample Frida data
    df = pd.DataFrame({
        "FødevareNavn": ["oksekød", "kartoffel", "mælk"],
        "FoodID": [0, 1, 2],
    })

    # Run the original function
    result = match_ingredient("oksekød", df)

    # Check returned values
    assert result["query"] == "oksekød"
    assert result["matched_name"] == "oksekød"
    assert result["frida_id"] == 0
    assert result["confidence"] >= 80
    assert result["flagged_for_review"] is False


# Test fuzzy matching with a spelling mistake
def test_match_ingredient_fuzzy_match():

    df = pd.DataFrame({
        "FødevareNavn": ["oksekød", "kartoffel", "mælk"],
        "FoodID": [0, 1, 2],
    })

    result = match_ingredient("kartofel", df)

    assert result["matched_name"] == "kartoffel"
    assert result["frida_id"] == 1
    assert result["flagged_for_review"] is False


# Test matching multiple ingredients
def test_match_all_ingredients_returns_dataframe():

    df = pd.DataFrame({
        "FødevareNavn": ["oksekød", "kartoffel", "mælk"],
        "FoodID": [0, 1, 2],
    })

    result = match_all_ingredients(
        ["oksekød", "mælk"],
        df
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert list(result["query"]) == ["oksekød", "mælk"]
    assert list(result["matched_name"]) == ["oksekød", "mælk"]


# Test if load_frida cleans invalid food names
def test_load_frida_cleans_food_names(monkeypatch):

    # Fake Excel data matching the real Frida structure
    def fake_read_excel(*args, **kwargs):
        return pd.DataFrame({
            "FødevareNavn": [" oksekød ", "kartoffel", float("nan"), "", "x"],
            "FoodID": [1, 2, 3, 4, 5]
        })

    monkeypatch.setattr(
        pd,
        "read_excel",
        fake_read_excel
    )

    result = load_frida("fake_file.xlsx")

    # Check cleaned result
    assert "oksekød" in list(result["FødevareNavn"]) or " oksekød " in list(result["FødevareNavn"])
    assert "kartoffel" in list(result["FødevareNavn"])
    assert len(result) >= 2