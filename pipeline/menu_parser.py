"""
Parses Madservice Roskilde Kommune weekly menu PDFs into structured meal records ready for ingredient lookup and nutrition scoring.

Input: Path to a PDF menu file (e.g. menuplan-marts-2026.pdf) Output: List of dicts, one per day, with keys:
            - day_number (int)
            - day_name (str)
            - main (str) 
            - sides (list of str)
            - dessert (str)
            - vegetarian (bool) 

Strategy: The Roskilde menu has a consistent two-column layout. pdfplumber exposes the x-coordinate of every word. Words with x0 < COLUMN_SPLIT belong to the 
left column (day name, main dish, sides). Words with x0 >= COLUMN_SPLIT belong to the right column (dessert).This cleanly separates main dishes from desserts without guesswork.

Usage: 

"""

import re
import pdfplumber

# x-coordinate threshold separating left column from right column.
# Determined by inspecting word positions in the Roskilde PDF:
# main dish words have x0 ~68-270, dessert words start at x0 ~357.
# 300 is a safe midpoint.
COLUMN_SPLIT = 300

# Danish day name abbreviations (started with sunday, cause themenu starts that way)
DAY_NAMES = {"SØN", "MAN", "TIR", "ONS", "TOR", "FRE", "LØR"}
 
# Connector words to strip when cleaning sides
SIDES_STRIP_WORDS = {"med", "og", "samt", "på", "i", "af"}

def _clean_sides(sides_text):
    """
    Cleans the raw sides string into a list of individual side names.
 
    Example:
        "Med kartoffelmos og drueagurker" -> ["kartoffelmos", "drueagurker"]
        "(Vegetarisk) med rodfrugter"     -> ["rodfrugter"]
 
    Parameters:
        sides_text (str): Raw sides line from the menu.
 
    Returns:
        list[str]: Cleaned list of side dish names.
    """
    text = re.sub(r'\(vegetarisk\)', '', sides_text, flags=re.IGNORECASE).strip()
    text = re.sub(r'^\s*(med|på|i|af)\s+', '', text, flags=re.IGNORECASE)
    parts = re.split(r',|\bog\b|\bsamt\b', text, flags=re.IGNORECASE)
    cleaned = []
    for part in parts:
        part = part.strip().lower()
        if part and part not in SIDES_STRIP_WORDS and len(part) > 2:
            cleaned.append(part)
    return cleaned
 

def _is_vegetarian(text):
    """
    Returns True if the text contains a vegetarian marker.
 
    Parameters:
        text (str): Any text from the menu line.
 
    Returns:
        bool
    """
    return bool(re.search(r'\(vegetarisk\)', text, re.IGNORECASE))
 
 
def _extract_rows(pdf_path):
    """
    Opens the PDF and extracts each text row as (left_text, right_text)
    using word x-positions to separate the two columns.
 
    Parameters:
        pdf_path (str): Path to the PDF file.
 
    Returns:
        list[tuple]: Each item is (left_col_text, right_col_text).
    """
    rows = []
 
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue
 
            # Group words by vertical position (round to 2px to cluster same line)
            lines = {}
            for word in words:
                line_key = round(word['top'] / 2) * 2
                lines.setdefault(line_key, []).append(word)
 
            for line_key in sorted(lines.keys()):
                line_words = lines[line_key]
                left_words = [w['text'] for w in line_words if w['x0'] < COLUMN_SPLIT]
                right_words = [w['text'] for w in line_words if w['x0'] >= COLUMN_SPLIT]
 
                left_text = ' '.join(left_words).strip()
                right_text = ' '.join(right_words).strip()
 
                if not left_text:
                    continue
                if left_text.startswith("MADSERVICE") or left_text.startswith("Periode"):
                    continue
                if "allergener" in left_text.lower():
                    continue
 
                rows.append((left_text, right_text))
 
    return rows
 
 
def parse_menu(pdf_path):
    """
    Main entry point. Parses a Roskilde menu PDF into structured meal records.
 
    Parameters:
        pdf_path (str): Path to the menu PDF file.
 
    Returns:
        list[dict]: One dict per day with keys:
                    day_number, day_name, main, sides, dessert, vegetarian
    """
    rows = _extract_rows(pdf_path)
    meals = []
 
    i = 0
    while i < len(rows):
        left, right = rows[i]
        tokens = left.split()
 
        if tokens and tokens[0] in DAY_NAMES:
            day_name = tokens[0]
            main = ' '.join(tokens[1:]).strip()
            dessert = right.strip()
 
            day_number = None
            sides = []
            vegetarian = False
 
            if i + 1 < len(rows):
                next_left, _ = rows[i + 1]
                next_tokens = next_left.split()
                if next_tokens and next_tokens[0].isdigit():
                    day_number = int(next_tokens[0])
                    sides_text = ' '.join(next_tokens[1:])
                    vegetarian = _is_vegetarian(sides_text)
                    sides = _clean_sides(sides_text)
                    i += 1
 
            meals.append({
                "day_number": day_number,
                "day_name": day_name,
                "main": main,
                "sides": sides,
                "dessert": dessert,
                "vegetarian": vegetarian
            })
 
        i += 1
 
    return meals
 
 
# ---------------------------------------------------------------------------
# SELF-TEST — run directly: python3 menu_parser.py [path_to_pdf]
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
 
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/mnt/user-data/uploads/menuplan-marts-2026.pdf"
 
    print(f"Parsing: {pdf_path}\n")
    meals = parse_menu(pdf_path)
    print(f"Found {len(meals)} meals\n")
 
    errors = 0
    for meal in meals:
        veg_flag = " [VEGETARISK]" if meal["vegetarian"] else ""
        print(f"Day {str(meal['day_number']):>2} {meal['day_name']}  "
              f"Main: {meal['main']:<30} "
              f"Dessert: {meal['dessert']:<28}"
              f"{veg_flag}")
        print(f"           Sides: {meal['sides']}")
 
        if not meal['main']:
            print("  !! WARNING: empty main dish")
            errors += 1
        if not meal['dessert']:
            print("  !! WARNING: empty dessert")
            errors += 1
        print()
 
    print(f"Parsing complete. {len(meals)} meals, {errors} warnings.")
 