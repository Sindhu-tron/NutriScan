import pytest

from pipeline.scoring import score_meal, score_week


# 1. Basic structure test
def test_score_meal_returns_expected_keys():
    nutrients = {
        "energy_kcal": 650,
        "protein_g": 30,
        "fiber_g": 8,
        "calcium_mg": 300,
        "sodium_mg": 500,
        "fat_sat_g": 6,
        "sugar_g": 8,
    }

    result = score_meal(nutrients, conditions=[])

    assert isinstance(result, dict)
    assert "score" in result
    assert "grade" in result
    assert "flags" in result
    assert "nutrient_scores" in result


# 2. Balanced meal should score well (A or B)
def test_balanced_meal_good_grade():
    nutrients = {
        "energy_kcal": 680,
        "protein_g": 25,
        "fiber_g": 8,
        "calcium_mg": 300,
        "sodium_mg": 500,
        "fat_sat_g": 6,
        "sugar_g": 8,
    }

    result = score_meal(nutrients, conditions=[])

    assert result["grade"] in ["A", "B"]


# 3. High sodium penalty + flag
def test_high_sodium_penalty_and_flag():
    nutrients = {
        "energy_kcal": 650,
        "protein_g": 25,
        "fiber_g": 8,
        "calcium_mg": 300,
        "sodium_mg": 2000,  # VERY HIGH
        "fat_sat_g": 6,
        "sugar_g": 8,
    }

    result = score_meal(nutrients, conditions=[])

    assert result["score"] > 0   # worse score
    assert any("Sodium" in flag for flag in result["flags"])


# 4. Protein deficiency → flag
def test_low_protein_flag():
    nutrients = {
        "energy_kcal": 650,
        "protein_g": 5,  # VERY LOW
        "fiber_g": 8,
        "calcium_mg": 300,
        "sodium_mg": 500,
        "fat_sat_g": 6,
        "sugar_g": 8,
    }

    result = score_meal(nutrients, conditions=[])

    assert any("Protein" in flag for flag in result["flags"])


# 5. Condition multipliers (Hypertension)
def test_hypertension_increases_sodium_penalty():
    nutrients = {
        "energy_kcal": 650,
        "protein_g": 25,
        "fiber_g": 8,
        "calcium_mg": 300,
        "sodium_mg": 1200,  # high but moderate
        "fat_sat_g": 6,
        "sugar_g": 8,
    }

    result_no_condition = score_meal(nutrients, [])
    result_with_condition = score_meal(nutrients, ["Hypertension"])

    # Score should be worse with hypertension
    assert result_with_condition["score"] > result_no_condition["score"]


# 6. Reward multiplier (Osteoporosis → calcium boost)
def test_osteoporosis_rewards_calcium():
    nutrients = {
        "energy_kcal": 650,
        "protein_g": 25,
        "fiber_g": 8,
        "calcium_mg": 350,  # good calcium
        "sodium_mg": 500,
        "fat_sat_g": 6,
        "sugar_g": 8,
    }

    result_no_condition = score_meal(nutrients, [])
    result_with_condition = score_meal(nutrients, ["Osteoporosis"])

    # Lower score is better → should improve
    assert result_with_condition["score"] < result_no_condition["score"]


# 7. Multiple conditions stack correctly
def test_multiple_conditions_stack():
    nutrients = {
        "energy_kcal": 750,
        "protein_g": 20,
        "fiber_g": 5,
        "calcium_mg": 200,
        "sodium_mg": 1000,
        "fat_sat_g": 10,
        "sugar_g": 20,
    }

    result = score_meal(
        nutrients,
        ["Hypertension", "Type 2 Diabetes"]
    )

    assert isinstance(result["score"], float)
    assert len(result["condition_effects"]) == 2


# 8. Missing nutrients handled as 0
def test_missing_nutrients_defaults_to_zero():
    nutrients = {
        "energy_kcal": 650,
        # missing others
    }

    result = score_meal(nutrients, [])

    assert isinstance(result["score"], float)


# 9. Grade boundaries test
def test_extremely_unhealthy_meal_gets_bad_grade():
    nutrients = {
        "energy_kcal": 5000,
        "protein_g": 0,
        "fiber_g": 0,
        "calcium_mg": 0,
        "sodium_mg": 10000,
        "fat_sat_g": 30,
        "sugar_g": 200,
    }

    result = score_meal(nutrients, [])

    assert result["grade"] in ["D", "E"]


# 10. Weekly scoring test
def test_score_week_summary():
    meal1 = score_meal({
        "energy_kcal": 650,
        "protein_g": 25,
        "fiber_g": 8,
        "calcium_mg": 300,
        "sodium_mg": 500,
        "fat_sat_g": 6,
        "sugar_g": 8,
    }, [])

    meal2 = score_meal({
        "energy_kcal": 800,
        "protein_g": 10,
        "fiber_g": 3,
        "calcium_mg": 100,
        "sodium_mg": 1500,
        "fat_sat_g": 12,
        "sugar_g": 25,
    }, [])

    weekly = score_week([meal1, meal2])

    assert "weekly_grade" in weekly
    assert "grade_counts" in weekly
    assert weekly["meal_count"] == 2
