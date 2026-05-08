import pytest
from pathlib import Path

from pipeline.nutrient_lookup import (
    load_frida_dataset,
    nutrients_for_food,
    aggregate_nutrients,
)


# Setup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRIDA_PATH = PROJECT_ROOT / "data" / "Frida_5.5_Dataset.xlsx"


# 1. Dataset loads correctly
def test_load_frida_dataset_returns_dataframe():
    df = load_frida_dataset()

    assert df is not None
    assert len(df) > 0


# 2. Known food exists
def test_known_food_in_dataset():
    df = load_frida_dataset()

    # Pick a known food from Frida (adjust if needed)
    assert any("banana" in name.lower() for name in df.index)


# 3. Nutrients return correct structure
def test_nutrients_for_food_structure():
    df = load_frida_dataset()

    food_name = df.index[0]  # safe: first available food
    result = nutrients_for_food(food_name, 100)

    assert isinstance(result, dict)

    expected_keys = [
        "energy_kcal",
        "protein_g",
        "fat_sat_g",
        "fiber_g",
        "sugar_g",
        "sodium_mg",
        "potassium_mg",
        "calcium_mg",
    ]

    for key in expected_keys:
        assert key in result


# 4. Scaling works correctly
def test_nutrients_scaling():
    df = load_frida_dataset()

    food_name = df.index[0]

    nutrients_100g = nutrients_for_food(food_name, 100)
    nutrients_50g = nutrients_for_food(food_name, 50)

    for key in nutrients_100g:
        expected = nutrients_100g[key] / 2
        actual = nutrients_50g[key]

        assert abs(expected - actual) < 0.01


# 5. Missing food raises error
def test_nutrients_for_unknown_food():
    with pytest.raises(KeyError):
        nutrients_for_food("this_food_does_not_exist", 100)


# 6. Aggregation works
def test_aggregate_nutrients():
    profiles = [
        {"energy_kcal": 100, "protein_g": 10},
        {"energy_kcal": 200, "protein_g": 20},
    ]

    result = aggregate_nutrients(profiles)

    assert result["energy_kcal"] == 300
    assert result["protein_g"] == 30


# 7. Aggregation handles empty list
def test_aggregate_empty():
    result = aggregate_nutrients([])

    assert result == {}


#  8. Aggregation rounding
def test_aggregate_rounding():
    profiles = [
        {"energy_kcal": 100.123},
        {"energy_kcal": 200.456},
    ]

    result = aggregate_nutrients(profiles)

    assert isinstance(result["energy_kcal"], float)
    assert round(result["energy_kcal"], 2) == result["energy_kcal"]
