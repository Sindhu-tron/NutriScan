"""
menu_parser.py
--------------
Responsibility:
- Read a Madservice Roskilde menu PDF and extract each day's meal into a
  structured dict that the rest of the pipeline can work with

The menu uses a two-column layout where the main dish and dessert appear on
the same line in separate columns. pdfplumber's word-position data is used
to split them by x-coordinate (threshold: 300).

Input:  Path to a menu PDF (e.g. sample_data/menuplan-marts-2026.pdf)
Output: List of dicts, one per day, each with keys:
            - day_number  (int)
            - day_name    (str)   e.g. "MAN"
            - main        (str)   e.g. "Frikadeller"
            - sides       (list of str)
            - dessert     (str)
            - vegetarian  (bool)

Usage:
    from pipeline.menu_parser import parse_menu

    meals = parse_menu("sample_data/menuplan-marts-2026.pdf")

Run directly to test:
    python pipeline/menu_parser.py sample_data/menuplan-marts-2026.pdf
"""

import re
import pdfplumber

# Words in the left column (main dish side) have x position below 300 and words in the right column (dessert side) have x position above 300.
# We figured this out by printing the x positions of all words in the PDF.
COLUMN_SPLIT = 300

# The menu uses these abbreviations for the days of the week
DAY_NAMES = {"SØN", "MAN", "TIR", "ONS", "TOR", "FRE", "LØR"}
 
# These small words appear in the sides line but are not ingredients
WORDS_TO_IGNORE = {"med", "og", "samt", "på", "i", "af"}

def clean_sides(sides_text):
    """
    Takes the raw sides text from the menu and returns a list of individual side dish names.
 
    For example:
        "Med kartoffelmos og drueagurker" becomes ["kartoffelmos", "drueagurker"]
        "(Vegetarisk) med rodfrugter" becomes ["rodfrugter"]
    """
    # Remove the vegetarian label if it is there
    text = re.sub(r'\(vegetarisk\)', '', sides_text, flags=re.IGNORECASE)
    text = text.strip()
 
    # Remove leading connector words like "Med", "På" etc.
    text = re.sub(r'^\s*(med|på|i|af)\s+', '', text, flags=re.IGNORECASE)
 
    # Split the text on commas, "og", and "samt"
    parts = re.split(r',|\bog\b|\bsamt\b', text, flags=re.IGNORECASE)
 
    # Clean up each part and skip empty strings and connector words
    result = []
    for part in parts:
        part = part.strip().lower()
        if part and part not in WORDS_TO_IGNORE and len(part) > 2:
            result.append(part)
 
    return result
 

def is_vegetarian(text):
    """
    Returns True if the text contains the vegetarian label.
    """
    return bool(re.search(r'\(vegetarisk\)', text, re.IGNORECASE))
 
 
def get_rows_from_pdf(pdf_path):
    """
    Opens the PDF and reads all the text rows.
    
    Each row is returned as a tuple of (left_column_text, right_column_text).
    We split by x position - words below 300 are in the left column (main dish), words above 300 are in the right column (dessert).
    
    Header and footer lines are skipped.
    """
    all_rows = []
 
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue
 
            # Group words into lines based on their vertical position. We round to the nearest 2 pixels because words on the same line can have slightly different vertical positions in the PDF.
            lines = {}
            for word in words:
                line_key = round(word['top'] / 2) * 2
                if line_key not in lines:
                    lines[line_key] = []
                lines[line_key].append(word)
 
            # Go through each line from top to bottom
            for line_key in sorted(lines.keys()):
                line_words = lines[line_key]
 
                # Split words into left and right column based on x position
                left_words = []
                right_words = []
                for word in line_words:
                    if word['x0'] < COLUMN_SPLIT:
                        left_words.append(word['text'])
                    else:
                        right_words.append(word['text'])
 
                left_text = ' '.join(left_words).strip()
                right_text = ' '.join(right_words).strip()
 
                # Skip empty lines
                if not left_text:
                    continue
 
                # Skip the header and footer lines
                if left_text.startswith("MADSERVICE") or left_text.startswith("Periode"):
                    continue
                if "allergener" in left_text.lower():
                    continue
 
                all_rows.append((left_text, right_text))
 
    return all_rows
 
 
def parse_menu(pdf_path):
    """
    Main function. Takes a path to a menu PDF and returns a list of meal dictionaries, one for each day in the menu.
    """
    rows = get_rows_from_pdf(pdf_path)
    meals = []
 
    i = 0
    while i < len(rows):
        left_text, right_text = rows[i]
        words = left_text.split()
 
        # Check if this row starts with a day name like "MAN" or "TIR"
        if words and words[0] in DAY_NAMES:
            day_name = words[0]
 
            # The main dish name is the rest of the left column
            main = ' '.join(words[1:]).strip()
 
            # The dessert is in the right column
            dessert = right_text.strip()
 
            # The next row should have the day number and the sides
            day_number = None
            sides = []
            vegetarian = False
 
            if i + 1 < len(rows):
                next_left, next_right = rows[i + 1]
                next_words = next_left.split()
 
                # Check if the next row starts with a number (the day number)
                if next_words and next_words[0].isdigit():
                    day_number = int(next_words[0])
 
                    # The sides are the rest of the text on that row
                    sides_text = ' '.join(next_words[1:])
                    vegetarian = is_vegetarian(sides_text)
                    sides = clean_sides(sides_text)
 
                    # Skip the sides row since we already read it
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
 
 
# This block only runs when you execute this file directly. It's used for testing the module during development.
# Example: python pipeline/menu_parser.py sample_data/menuplan-marts-2026.pdf
if __name__ == "__main__":
    import sys
 
    # Use the file path from the command line, or default to March menu
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "sample_data/menuplan-marts-2026.pdf"
 
    print("Parsing:", pdf_path)
    print()
 
    meals = parse_menu(pdf_path)
    print("Found", len(meals), "meals")
    print()
 
    warnings = 0
    for meal in meals:
        veg_label = " [VEGETARISK]" if meal["vegetarian"] else ""
        print("Day", meal["day_number"], meal["day_name"])
        print("  Main:    ", meal["main"])
        print("  Dessert: ", meal["dessert"])
        print("  Sides:   ", meal["sides"])
        print("  " + veg_label if veg_label else "")
 
        # Basic checks
        if not meal["main"]:
            print("  WARNING: no main dish found")
            warnings += 1
        if not meal["dessert"]:
            print("  WARNING: no dessert found")
            warnings += 1
        print()
 
    print("Done.", len(meals), "meals parsed,", warnings, "warnings.")
