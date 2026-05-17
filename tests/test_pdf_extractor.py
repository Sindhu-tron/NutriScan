import pytest
from pathlib import Path

from pipeline.pdf_extractor import extract_meals


# Setup
PROJECT_ROOT = Path(__file__).resolve().parents[1]
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


# 11. Dessert nutrient contribution
# Desserts in Danish institutional menus are typically cream-based
# (fløde, sukker, æg) and contribute meaningfully to the total energy
# and sugar content of the meal. This is documented in the literature
# on elderly institutional nutrition — desserts are often used
# deliberately to boost energy intake for residents with low appetite.
# This test verifies that the dessert component is actually contributing
# nutrients to the total meal, and is not being silently ignored.
def test_dessert_contributes_nutrients():
    meals = extract_meals(str(PDF_PATH))

    # Find a meal where the dessert is in dish_ingredients.json
    # Day 1 has Citronfromage (citron, æg, sukker, fløde) — known to be in catalogue
    day_1 = next((m for m in meals if m["day_number"] == 1), None)
    assert day_1 is not None, "Day 1 not found in parsed meals"

    # The dessert should have ingredients listed
    assert len(day_1["dessert_ingredients"]) > 0, (
        "Dessert ingredients are empty — dessert is not contributing to nutrients"
    )

    # Total meal sugar should be above zero, since Citronfromage contains sukker
    # This confirms the dessert's sugar is included in the aggregated total
    total_sugar = day_1["nutrients"].get("sugar_g", 0)
    assert total_sugar > 0, (
        "Sugar is 0 — dessert sugar contribution is missing from meal total"
    )

    # Total meal energy should reflect both main dish and dessert
    # Citronfromage (fløde + sukker + æg) adds meaningful kcal
    total_energy = day_1["nutrients"].get("energy_kcal", 0)
    assert total_energy > 100, (
        "Energy is suspiciously low — dessert energy may not be aggregated"
    )
