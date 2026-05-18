import pytest

from pipeline.menu_parser import (
    clean_sides,
    is_vegetarian,
    parse_menu,
)


# 1. Sides are cleaned correctly
def test_clean_sides():

    result = clean_sides(
        "Med kartoffelmos og drueagurker"
    )

    assert result == [
        "kartoffelmos",
        "drueagurker"
    ]


# 2. Vegetarian meals are detected
def test_is_vegetarian_true():

    result = is_vegetarian(
        "(Vegetarisk) med rodfrugter"
    )

    assert result is True


# 3. Non-vegetarian meals return False
def test_is_vegetarian_false():

    result = is_vegetarian(
        "Med kartofler og sovs"
    )

    assert result is False


# 4. Empty sides return empty list
def test_clean_sides_empty():

    result = clean_sides("")

    assert result == []


# 5. Connector words are removed
def test_clean_sides_removes_connector_words():

    result = clean_sides(
        "Med ris og sovs"
    )

    assert "med" not in result
    assert result == ["ris", "sovs"]


# 6. Parse menu returns correct structure
def test_parse_menu_structure(monkeypatch):

    fake_rows = [
        ("MAN Frikadeller", "Æblekage"),
        ("12 Med kartofler og sovs", ""),
    ]

    # Fake PDF extraction
    def fake_get_rows_from_pdf(pdf_path):
        return fake_rows

    monkeypatch.setattr(
        "pipeline.menu_parser.get_rows_from_pdf",
        fake_get_rows_from_pdf
    )

    result = parse_menu("fake.pdf")

    assert isinstance(result, list)
    assert len(result) == 1


# 7. Parse menu extracts correct values
def test_parse_menu_values(monkeypatch):

    fake_rows = [
        ("MAN Frikadeller", "Æblekage"),
        ("12 Med kartofler og sovs", ""),
    ]

    def fake_get_rows_from_pdf(pdf_path):
        return fake_rows

    monkeypatch.setattr(
        "pipeline.menu_parser.get_rows_from_pdf",
        fake_get_rows_from_pdf
    )

    result = parse_menu("fake.pdf")

    meal = result[0]

    assert meal["day_name"] == "MAN"
    assert meal["day_number"] == 12
    assert meal["main"] == "Frikadeller"
    assert meal["dessert"] == "Æblekage"
    assert meal["sides"] == ["kartofler", "sovs"]
    assert meal["vegetarian"] is False


# 8. Vegetarian meals are parsed correctly
def test_parse_menu_vegetarian(monkeypatch):

    fake_rows = [
        ("TIR Grøntsagssuppe", "Kage"),
        ("13 (Vegetarisk) med rodfrugter", ""),
    ]

    def fake_get_rows_from_pdf(pdf_path):
        return fake_rows

    monkeypatch.setattr(
        "pipeline.menu_parser.get_rows_from_pdf",
        fake_get_rows_from_pdf
    )

    result = parse_menu("fake.pdf")

    meal = result[0]

    assert meal["vegetarian"] is True

# 9. Dessert is extracted correctly
def test_parse_menu_dessert(monkeypatch):
     
    fake_rows = [
        ("ONS Kylling", "Chokoladekage"),
        ("14 Med ris og sovs", ""),
    ]

    def fake_get_rows_from_pdf(pdf_path):
        return fake_rows

    monkeypatch.setattr(
        "pipeline.menu_parser.get_rows_from_pdf",
        fake_get_rows_from_pdf
    )

    result = parse_menu("fake.pdf")

    meal = result[0]

    assert meal["dessert"] == "Chokoladekage"
    