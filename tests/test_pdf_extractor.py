import pytest
from pathlib import Path

from pipeline.pdf_extractor import extract_meals


# Setup

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PDF_PATH = PROJECT_ROOT / "sample_data" / "menuplan-marts-2026.pdf"


# 1. Basic extraction works
def test_extract_meals_returns_list():
    meals = extract_meals(str(PDF_PATH))

    assert isinstance(meals, list)
    assert len(meals) > 0


# 2. Meal structure is correct
def test_meal_has_expected_keys():
    meals = extract_meals(str(PDF_PATH))
    meal = meals[0]

    expected_keys = [
        "day_number",
        "day_name",
        "main",
        "sides",
        "dessert",
        "nutrients",
        "matched",
        "unmatched",
        "coverage_pct",
    ]

    for key in expected_keys:
        assert key in meal


# 3. Nutrients structure
def test_nutrients_structure():
    meals = extract_meals(str(PDF_PATH))
    nutrients = meals[0]["nutrients"]

    assert isinstance(nutrients, dict)

    for _, value in nutrients.items():
        assert isinstance(value, (int, float))


# 4. Coverage percentage valid
def test_coverage_percentage_valid():
    meals = extract_meals(str(PDF_PATH))

    for meal in meals:
        assert 0 <= meal["coverage_pct"] <= 100


# 5. Unmatched ingredients
def test_unmatched_is_list():
    meals = extract_meals(str(PDF_PATH))

    for meal in meals:
        assert isinstance(meal["unmatched"], list)


# 6. Matched ingredients structure
def test_matched_structure():
    meals = extract_meals(str(PDF_PATH))

    for meal in meals:
        for item in meal["matched"]:
            assert "ingredient" in item
            assert "amount_g" in item


# 7. File not found (edge case)
def test_extract_meals_file_not_found():
    with pytest.raises(Exception):
        extract_meals("non_existent_file.pdf")


# 8. Day numbers valid
def test_day_numbers_valid():
    meals = extract_meals(str(PDF_PATH))

    for meal in meals:
        assert isinstance(meal["day_number"], int)
        assert meal["day_number"] > 0


# 9. Main dish structure
def test_main_dish_string():
    meals = extract_meals(str(PDF_PATH))

    for meal in meals:
        assert isinstance(meal["main"], str)
        assert len(meal["main"]) > 0


# 10. Full pipeline sanity check
def test_full_pipeline_output_reasonable():
    meals = extract_meals(str(PDF_PATH))

    meal = meals[0]

    assert isinstance(meal["nutrients"]["energy_kcal"], (int, float))
    assert isinstance(meal["coverage_pct"], int)
