# The dashboard.py module is the main frontend for the NutriScan system and it calls each module in the pipeline in sequence and displays the results. 
# The pipeline modules don't know anything about the frontend, they just take inputs and return outputs. The dashboard is what stings them together for the user. 
# It is built with Dash -  a Python library that lets us build web interfaces. It runs a local web server and we interact with it through the browser.
# Run this file directly to start the dashboard: python frontend/dashboard.py 
# Then open your browser at: http://127.0.0.1:8050
# dependencies needed (pip install dash dash-bootstrap-components)

"""
How this file is structured:
    1. Data - all the patient data, meal data and nutrient data used in the dashboard
    2. Scoring function - a simplified version of the scoring algorithm from scoring.py
    3. Helper functions - each function builds one part of the dashboard (a card, a section etc.)
    4. Page layouts - functions that put the helper components together into full pages
    5. App layout - the overall structure of the app (sidebar + main content area)
    6. Callbacks - the functions that make the dashboard interactive
"""


# Date: 30.03.2026
# Author: Sindhuja Dantuluri

import dash 
from dash import html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc 

# Synthetic patient data
# Used for testing the dashboard before the pipeline is connected. 
# This will later be replaced by real data from the scoring module. 
# # Each patient has an id, basic demographics, and a list of health conditions.
# Conditions are split into primary (active), risk (at risk), and inactive.

PATIENTS = [
    {
        "id": "XY-5217",
        "name": "Erik Andersen",
        "sex": "Male",
        "age": 82,
        "location": "Wing A, Room 3",
        "avatar": "EA",
        "conditions": {
            "primary": ["Hypertension", "Type 2 Diabetes"],
            "risk": ["Malnutrition"],
            "inactive": []
        }
    },
    {
        "id": "XY-3891",
        "name": "Birthe Sørensen",
        "sex": "Female",
        "age": 79,
        "location": "Wing B, Room 7",
        "avatar": "BS",
        "conditions": {
            "primary": ["Osteoporosis"],
            "risk": ["Malnutrition"],
            "inactive": ["Dementia"]
        }
    },
    {
        "id": "XY-4422",
        "name": "Kaj Nielsen",
        "sex": "Male",
        "age": 85,
        "location": "Wing C, Room 12",
        "avatar": "KN",
        "conditions": {
            "primary": ["High Cholesterol"],
            "risk": ["Hypertension"],
            "inactive": []
        }
    },
    {
        "id": "XY-6104",
        "name": "Grethe Larsen",
        "sex": "Female",
        "age": 76,
        "location": "Wing A, Room 9",
        "avatar": "GL",
        "conditions": {
            "primary": ["Malnutrition Risk"],
            "risk": [],
            "inactive": ["Type 2 Diabetes"]
        }
    },
    {
        "id": "XY-7733",
        "name": "Holger Christensen",
        "sex": "Male",
        "age": 88,
        "location": "Wing D, Room 2",
        "avatar": "HC",
        "conditions": {
            "primary": [],
            "risk": [],
            "inactive": []
        }
    }
]
 
# Sample meals for the demo.
# In the real system, these come from menu_parser.py reading the Roskilde PDF menus.
# Each meal has a main dish, a list of sides, and a dessert.
SAMPLE_MEALS = {
    "March 2026 - Day 1": {
        "day": "Sunday 1 March 2026",
        "main": {
            "name": "Bøf stroganoff",
            "ingredients": ["oksekød", "løg", "champignon", "creme fraiche", "tomatpuré"]
        },
        "sides": ["kartoffelmos", "drueagurker"],
        "dessert": {
            "name": "Citronfromage",
            "ingredients": ["æg", "fløde", "sukker", "citronsaft"]
        }
    },
    "March 2026 - Day 2": {
        "day": "Monday 2 March 2026",
        "main": {
            "name": "Frikadeller",
            "ingredients": ["svinekød", "løg", "æg", "mælk", "hvedemel"]
        },
        "sides": ["stuvet ærter", "gulerødder", "surt"],
        "dessert": {
            "name": "Cheesecake i glas",
            "ingredients": ["flødeost", "fløde", "sukker", "digestive"]
        }
    },
    "March 2026 - Day 5": {
        "day": "Thursday 5 March 2026",
        "main": {
            "name": "Fiskefrikadeller",
            "ingredients": ["torskefilet", "æg", "mælk", "hvedemel", "løg"]
        },
        "sides": ["caperssovs", "citron", "gulerodsråkost"],
        "dessert": {
            "name": "Æblegrød",
            "ingredients": ["æble", "sukker"]
        }
    },
    "March 2026 - Day 10": {
        "day": "Tuesday 10 March 2026",
        "main": {
            "name": "Hakkebøf",
            "ingredients": ["oksekød", "løg", "smør", "æg", "hvedemel"]
        },
        "sides": ["bløde løg", "skysovs", "rødbeder"],
        "dessert": {
            "name": "Vanillebudding",
            "ingredients": ["mælk", "sukker", "æg", "majsstivelse"]
        }
    },
    "April 2026 - Day 14": {
        "day": "Tuesday 14 April 2026",
        "main": {
            "name": "Frikadeller",
            "ingredients": ["svinekød", "løg", "æg", "mælk", "hvedemel"]
        },
        "sides": ["stuvet ærter", "gulerødder", "surt"],
        "dessert": {
            "name": "Rabarbergrød",
            "ingredients": ["rabarber", "sukker", "kartoffelmel"]
        }
    }
}
 
# Nutrient values per meal.
# These are simplified placeholder values for the demo.
# In the real system, these come from nutrient_lookup.py using the Frida database.
# Values are per meal (not per 100g).
MEAL_NUTRIENTS = {
    "March 2026 - Day 1":  {"energy": 680, "protein": 38, "carbs": 52, "fibre": 4, "calcium": 180, "sodium": 6.1},
    "March 2026 - Day 2":  {"energy": 620, "protein": 42, "carbs": 48, "fibre": 6, "calcium": 210, "sodium": 4.8},
    "March 2026 - Day 5":  {"energy": 520, "protein": 35, "carbs": 40, "fibre": 5, "calcium": 190, "sodium": 3.9},
    "March 2026 - Day 10": {"energy": 590, "protein": 36, "carbs": 45, "fibre": 3, "calcium": 160, "sodium": 5.5},
    "April 2026 - Day 14": {"energy": 610, "protein": 40, "carbs": 50, "fibre": 7, "calcium": 220, "sodium": 4.2},
}
 
# Condition profiles shown on the Disease Profiles page.
# Each profile has a name, a short description, and a list of nutrient multipliers.
# These multipliers match the ones used in pipeline/scoring.py.
CONDITION_PROFILES = [
    {
        "name": "Hypertension",
        "description": "High blood pressure — affects approx. 2/3 of people over 65",
        "multipliers": [
            ("Sodium", "2.5x penalty", "#d94f3d"),
            ("Potassium", "1.5x reward", "#4caf7d"),
            ("Saturated fat", "1.3x penalty", "#e8a838")
        ]
    },
    {
        "name": "Type 2 Diabetes",
        "description": "Impaired blood sugar regulation — common in nursing home population",
        "multipliers": [
            ("Sugar", "2.5x penalty", "#d94f3d"),
            ("Energy", "1.5x penalty", "#e8a838"),
            ("Fibre", "1.5x reward", "#4caf7d")
        ]
    },
    {
        "name": "Osteoporosis",
        "description": "Reduced bone density — elevated fracture risk in elderly",
        "multipliers": [
            ("Calcium", "2.0x reward", "#4caf7d"),
            ("Protein", "1.3x reward", "#4caf7d")
        ]
    },
    {
        "name": "Malnutrition Risk",
        "description": "Risk of undernutrition — common in elderly with low appetite",
        "multipliers": [
            ("Energy", "0.3x penalty (reduced)", "#4caf7d"),
            ("Protein", "2.0x reward", "#4caf7d")
        ]
    },
    {
        "name": "High Cholesterol",
        "description": "Elevated blood lipids — cardiovascular risk factor",
        "multipliers": [
            ("Saturated fat", "2.0x penalty", "#d94f3d"),
            ("Fibre", "1.5x reward", "#4caf7d")
        ]
    }
]
 
# Data sources shown on the Data Sources page.
DATA_SOURCES = [
    {
        "name": "Nordic Nutrition Recommendations 2023 (NNR 2023)",
        "description": "Scientific basis for nutrient reference values across Nordic and Baltic countries. Primary source for nutrient thresholds used in the scoring algorithm.",
        "url": "https://www.norden.org/en/publication/nordic-nutrition-recommendations-2023",
        "publisher": "Nordic Council of Ministers"
    },
    {
        "name": "Anbefalinger for den danske institutionskost 2025",
        "description": "Official Danish dietary standards for institutional kitchens including nursing homes. Defines kostformer and daily nutrient targets.",
        "url": "https://www.sst.dk",
        "publisher": "Fødevarestyrelsen & Sundhedsstyrelsen"
    },
    {
        "name": "Frida Food Data v5.5",
        "description": "The Danish national food composition database maintained by DTU. Primary source for all nutrient values per 100g used in this system.",
        "url": "https://frida.fooddata.dk",
        "publisher": "DTU National Food Institute"
    }
]
 
# Grade colours used throughout the dashboard.
# Green = good, orange = adequate, red = poor/critical.
GRADE_COLORS = {
    "A": "#4caf7d",
    "B": "#8bc34a",
    "C": "#e8a838",
    "D": "#ff7043",
    "E": "#d94f3d"
}
 
 
# =============================================================================
# SECTION 2: SCORING FUNCTION
# This is a simplified version of the full scoring algorithm in scoring.py.
# It takes nutrient values and a patient's conditions, and returns a grade A-E.
# The full algorithm with all nutrients and thresholds is in pipeline/scoring.py.
# =============================================================================
 
def calculate_grade(nutrients, conditions):
    """
    Calculates a nutritional grade (A-E) for a meal based on its nutrient
    values and the patient's health conditions.
 
    Parameters:
        nutrients (dict): nutrient values for the meal
        conditions (list): list of condition names for the patient
 
    Returns:
        grade (str): letter grade A to E
        description (str): short description of the grade
    """
    score = 0
 
    # --- PENALTIES (bad nutrients add to the score) ---
 
    # Sodium is the most important nutrient to monitor for elderly patients.
    # If the patient has hypertension, the penalty is doubled.
    sodium_multiplier = 2.0 if "Hypertension" in conditions else 1.0
    if nutrients["sodium"] > 5.0:
        score = score + (nutrients["sodium"] - 5.0) * 2 * sodium_multiplier
 
    # High carbohydrates are a concern for diabetes patients.
    sugar_multiplier = 1.5 if "Type 2 Diabetes" in conditions else 1.0
    if nutrients["carbs"] > 55:
        score = score + (nutrients["carbs"] - 55) * 0.1 * sugar_multiplier
 
    # --- REWARDS (good nutrients reduce the score) ---
 
    # Protein is especially important for patients at risk of malnutrition.
    protein_multiplier = 2.0 if "Malnutrition Risk" in conditions else 1.0
    if nutrients["protein"] >= 25:
        score = score - (3 * protein_multiplier)
    elif nutrients["protein"] >= 20:
        score = score - (1.5 * protein_multiplier)
 
    # Calcium is especially important for osteoporosis patients.
    calcium_multiplier = 2.0 if "Osteoporosis" in conditions else 1.0
    if nutrients["calcium"] >= 250:
        score = score - (2 * calcium_multiplier)
    elif nutrients["calcium"] >= 180:
        score = score - (1 * calcium_multiplier)
 
    # Fibre is beneficial for most patients.
    fibre_multiplier = 1.5 if "High Cholesterol" in conditions else 1.0
    if nutrients["fibre"] >= 6:
        score = score - (2 * fibre_multiplier)
    elif nutrients["fibre"] >= 4:
        score = score - (1 * fibre_multiplier)
 
    # Map the final score to a letter grade.
    # Lower score = better grade. E requires multiple nutrients to be failing.
    if score <= -2:
        return "A", "Excellent nutritional balance"
    elif score <= 2:
        return "B", "Good - minor improvements possible"
    elif score <= 6:
        return "C", "Adequate - improvements recommended"
    elif score <= 11:
        return "D", "Poor - action recommended"
    else:
        return "E", "Critical - immediate review needed"
 
 
# =============================================================================
# SECTION 3: SHARED STYLES
# These style dictionaries are reused across multiple components to keep
# the look consistent without repeating the same CSS everywhere.
# =============================================================================
 
# Style for the left sidebar
SIDEBAR_STYLE = {
    "width": "240px",
    "minHeight": "100vh",
    "backgroundColor": "#1a1a2e",
    "position": "fixed",
    "top": "0",
    "left": "0",
    "overflowY": "auto",
    "zIndex": "100"
}
 
# Style for the main content area (offset to the right of the sidebar)
CONTENT_STYLE = {
    "marginLeft": "240px",
    "padding": "24px",
    "backgroundColor": "#f4f4f4",
    "minHeight": "100vh"
}
 
# Style for individual cards (white boxes with rounded corners)
CARD_STYLE = {
    "backgroundColor": "white",
    "borderRadius": "12px",
    "padding": "20px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
    "marginBottom": "16px"
}
 
 
# =============================================================================
# SECTION 4: HELPER FUNCTIONS
# Each function builds one reusable UI component.
# =============================================================================
 
def make_sidebar():
    """
    Builds the left navigation sidebar.
    Each nav item has an id like "nav-dashboard" so the callback
    can detect which one was clicked.
    """
    # Navigation structure: section heading -> list of (page_id, label) pairs
    nav_sections = [
        ("OVERVIEW", [
            ("dashboard", "🏠 Dashboard"),
            ("patients", "👥 Patients"),
            ("meal-plans", "🍽️ Meal plans"),
        ]),
        ("ANALYSIS", [
            ("nutritional-gaps", "📊 Nutritional gaps"),
            ("frida-foods", "🥗 Frida Foods"),
            ("disease-profiles", "🏥 Disease Profiles"),
        ]),
        ("DATA", [
            ("data-sources", "📁 Data sources"),
            ("settings", "⚙️ Settings"),
        ])
    ]
 
    # Build the list of nav items to display in the sidebar
    nav_items = []
    for section_title, links in nav_sections:
        # Add the section heading
        nav_items.append(
            html.P(section_title, style={
                "color": "#999",
                "fontSize": "11px",
                "fontWeight": "600",
                "letterSpacing": "1px",
                "marginTop": "20px",
                "marginBottom": "8px",
                "paddingLeft": "16px"
            })
        )
        # Add each link under the section
        for page_id, label in links:
            nav_items.append(
                html.Div(label, id="nav-" + page_id, style={
                    "padding": "10px 16px",
                    "borderRadius": "8px",
                    "cursor": "pointer",
                    "color": "#ccc",
                    "marginBottom": "4px"
                })
            )
 
    return html.Div([
        # Logo area
        html.Div([
            html.H2("NutriScan", style={
                "color": "#e8a838",
                "margin": "0",
                "fontSize": "24px",
                "fontWeight": "800"
            }),
            html.P("Nutritional intelligence guide", style={
                "color": "#aaa",
                "fontSize": "11px",
                "margin": "0"
            })
        ], style={"padding": "24px 16px 16px"}),
 
        html.Hr(style={"borderColor": "#333", "margin": "0 16px"}),
 
        # Navigation links
        html.Div(nav_items, style={"padding": "8px"}),
 
        # Footer disclaimer
        html.Div([
            html.P("Synthetic patient data only.", style={
                "fontSize": "10px", "color": "#666", "margin": "0"
            }),
            html.P("Please double-check all outputs.", style={
                "fontSize": "10px", "color": "#666", "margin": "0"
            })
        ], style={"position": "absolute", "bottom": "16px", "padding": "0 16px"})
 
    ], style=SIDEBAR_STYLE)
 
 
def make_patient_card(patient):
    """
    Builds the patient profile card shown at the top of the dashboard.
    Shows the patient's name, age, location, and primary conditions.
    """
    # Build a badge for each primary condition
    condition_badges = []
    for condition in patient["conditions"]["primary"]:
        condition_badges.append(
            html.Span(condition, style={
                "backgroundColor": "#fff3e0",
                "color": "#e8a838",
                "border": "1px solid #e8a838",
                "borderRadius": "20px",
                "padding": "4px 12px",
                "fontSize": "12px",
                "fontWeight": "600",
                "marginRight": "8px"
            })
        )
 
    return html.Div([
        html.Div([
            # Avatar circle with patient initials
            html.Div(patient["avatar"], style={
                "width": "50px",
                "height": "50px",
                "borderRadius": "50%",
                "backgroundColor": "#e8a838",
                "color": "white",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "fontWeight": "bold",
                "fontSize": "16px",
                "marginRight": "16px",
                "flexShrink": "0"
            }),
            # Patient details
            html.Div([
                html.H4("Patient #" + patient["id"], style={
                    "margin": "0 0 4px 0", "fontSize": "16px"
                }),
                html.P(patient["sex"] + " · Age " + str(patient["age"]), style={
                    "margin": "0", "color": "#666", "fontSize": "13px"
                }),
                html.P(patient["location"], style={
                    "margin": "0", "color": "#666", "fontSize": "13px"
                })
            ]),
            # Condition badges on the right side
            html.Div(condition_badges, style={
                "marginLeft": "auto",
                "display": "flex",
                "alignItems": "center"
            })
        ], style={"display": "flex", "alignItems": "center"})
    ], style={**CARD_STYLE, "marginBottom": "20px"})
 
 
def make_score_cards(nutrients, grade, grade_description):
    """
    Builds the three summary cards: energy intake, protein intake, and grade.
    These sit side by side at the top of the dashboard.
    """
    # Calculate how close each value is to its target (as a percentage)
    energy_pct = round(nutrients["energy"] / 700 * 100)
    protein_pct = round(nutrients["protein"] / 25 * 100)
 
    # Choose the colour for the grade
    grade_color = GRADE_COLORS.get(grade, "#888")
 
    # Choose text colour based on whether the value is close to target
    if energy_pct < 85:
        energy_color = "#d94f3d"
    else:
        energy_color = "#4caf7d"
 
    if protein_pct < 85:
        protein_color = "#d94f3d"
    else:
        protein_color = "#4caf7d"
 
    return html.Div([
 
        # Energy card
        html.Div([
            html.P("ENERGY INTAKE", style={
                "fontSize": "11px", "fontWeight": "600",
                "letterSpacing": "1px", "color": "#888", "margin": "0 0 8px 0"
            }),
            html.H3(str(nutrients["energy"]) + " kcal", style={
                "margin": "0 0 4px 0", "fontSize": "28px", "fontWeight": "800"
            }),
            html.P("Target: ~700 kcal/meal", style={
                "fontSize": "12px", "color": "#888", "margin": "0 0 8px 0"
            }),
            html.P("▲ " + str(energy_pct) + "% of target", style={
                "fontSize": "11px", "color": energy_color,
                "margin": "0", "fontWeight": "600"
            })
        ], style={**CARD_STYLE, "flex": "1", "marginRight": "12px", "marginBottom": "0"}),
 
        # Protein card
        html.Div([
            html.P("PROTEIN INTAKE", style={
                "fontSize": "11px", "fontWeight": "600",
                "letterSpacing": "1px", "color": "#888", "margin": "0 0 8px 0"
            }),
            html.H3(str(nutrients["protein"]) + " g", style={
                "margin": "0 0 4px 0", "fontSize": "28px", "fontWeight": "800"
            }),
            html.P("Target: ~25g/meal (NNR 2023)", style={
                "fontSize": "12px", "color": "#888", "margin": "0 0 8px 0"
            }),
            html.P("▲ " + str(protein_pct) + "% of target", style={
                "fontSize": "11px", "color": protein_color,
                "margin": "0", "fontWeight": "600"
            })
        ], style={**CARD_STYLE, "flex": "1", "marginRight": "12px", "marginBottom": "0"}),
 
        # Nutritional score / grade card
        html.Div([
            html.P("NUTRITIONAL SCORE", style={
                "fontSize": "11px", "fontWeight": "600",
                "letterSpacing": "1px", "color": "#888", "margin": "0 0 8px 0"
            }),
            html.Div([
                # Large letter grade
                html.Span(grade, style={
                    "fontSize": "72px",
                    "fontWeight": "900",
                    "color": grade_color,
                    "lineHeight": "1"
                }),
                # Grade description next to the letter
                html.Div([
                    html.P("Grade", style={
                        "fontSize": "12px", "color": "#888", "margin": "0"
                    }),
                    html.P(grade_description, style={
                        "fontSize": "11px", "color": grade_color,
                        "fontWeight": "600", "margin": "0"
                    })
                ], style={"marginLeft": "16px"})
            ], style={"display": "flex", "alignItems": "center"}),
            html.P("A = Excellent  B = Good  C = Adequate  D = Poor  E = Critical",
                   style={"fontSize": "10px", "color": "#bbb", "margin": "8px 0 0 0"})
        ], style={**CARD_STYLE, "flex": "1", "marginBottom": "0"})
 
    ], style={"display": "flex", "marginBottom": "16px"})
 
 
def make_meal_card(meal):
    """
    Builds the Today's Menu card showing the main dish, sides, and dessert.
    """
    return html.Div([
        html.H5("Today's Menu", style={"fontWeight": "700", "marginBottom": "4px"}),
        html.P(meal["day"], style={
            "color": "#888", "fontSize": "12px", "marginBottom": "16px"
        }),
 
        # Main dish section
        html.Div([
            html.P("MAIN DISH", style={
                "fontSize": "10px", "fontWeight": "600",
                "letterSpacing": "1px", "color": "#888", "margin": "0 0 4px 0"
            }),
            html.H5(meal["main"]["name"], style={"margin": "0 0 4px 0"}),
            html.P("Ingredients: " + ", ".join(meal["main"]["ingredients"]),
                   style={"fontSize": "11px", "color": "#666", "margin": "0"})
        ], style={
            "backgroundColor": "#fff8ee",
            "borderLeft": "3px solid #e8a838",
            "borderRadius": "0 8px 8px 0",
            "padding": "12px",
            "marginBottom": "10px"
        }),
 
        # Sides section
        html.Div([
            html.P("SIDES", style={
                "fontSize": "10px", "fontWeight": "600",
                "letterSpacing": "1px", "color": "#888", "margin": "0 0 4px 0"
            }),
            html.P(", ".join(meal["sides"]),
                   style={"fontSize": "13px", "margin": "0"})
        ], style={
            "backgroundColor": "#f8f8f8",
            "borderRadius": "8px",
            "padding": "12px",
            "marginBottom": "10px"
        }),
 
        # Dessert section
        html.Div([
            html.P("DESSERT", style={
                "fontSize": "10px", "fontWeight": "600",
                "letterSpacing": "1px", "color": "#888", "margin": "0 0 4px 0"
            }),
            html.H5(meal["dessert"]["name"], style={"margin": "0 0 4px 0"}),
            html.P("Ingredients: " + ", ".join(meal["dessert"]["ingredients"]),
                   style={"fontSize": "11px", "color": "#666", "margin": "0"})
        ], style={
            "backgroundColor": "#f0f4ff",
            "borderLeft": "3px solid #7986cb",
            "borderRadius": "0 8px 8px 0",
            "padding": "12px"
        })
 
    ], style=CARD_STYLE)
 
 
def make_guidelines(nutrients, conditions):
    """
    Builds the guidelines panel showing progress bars for each nutrient.
    The progress bars turn red when a value is too low (or too high for sodium).
    Condition-specific alerts are shown when a nutrient is clinically significant
    for that patient's conditions.
    """
    # List of nutrients to display.
    # Format: (display label, key in nutrients dict, target value, unit, reverse)
    # reverse=True means lower is better (like sodium)
    nutrient_targets = [
        ("Energy (kcal)", "energy", 700,  "kcal", False),
        ("Protein (g)",   "protein", 25,  "g",    False),
        ("Carbohydrate (g)", "carbs", 60, "g",    False),
        ("Dietary Fibre (g)", "fibre", 8, "g",    False),
        ("Calcium (mg)",  "calcium", 300, "mg",   False),
        ("Salt/Sodium (g)", "sodium", 5.0, "g",   True),
    ]
 
    nutrient_rows = []
 
    for label, key, target, unit, reverse in nutrient_targets:
        value = nutrients.get(key, 0)
 
        # Calculate how much of the target is reached (capped at 100%)
        pct = round((value / target) * 100)
        if pct > 100:
            pct = 100
 
        # Choose bar colour based on whether the value is good or bad
        if reverse:
            # For sodium: green if under target, red if over
            if value >= target:
                bar_color = "#d94f3d"
            else:
                bar_color = "#4caf7d"
        else:
            # For all other nutrients: green if close to target, red if low
            if pct >= 85:
                bar_color = "#4caf7d"
            elif pct >= 60:
                bar_color = "#e8a838"
            else:
                bar_color = "#d94f3d"
 
        # Default alert message
        alert = None
 
        # General alerts
        if reverse and value >= target:
            alert = "Exceeds recommended limit. Review sodium-rich components."
        elif not reverse and pct < 60:
            alert = "Below target - consider adjusting meal components."
 
        # Condition-specific alerts (these override the general ones)
        if key == "sodium" and "Hypertension" in conditions and value >= target * 0.9:
            alert = "⚠ Hypertension: sodium limit critical. Review immediately."
        if key == "protein" and "Malnutrition Risk" in conditions and pct < 80:
            alert = "⚠ Malnutrition risk: protein supplementation strongly recommended."
        if key == "calcium" and "Osteoporosis" in conditions and pct < 80:
            alert = "⚠ Osteoporosis: calcium intake insufficient for bone health."
 
        # Build the row for this nutrient
        nutrient_rows.append(html.Div([
            # Label and value
            html.Div([
                html.Span(label, style={"fontSize": "12px", "fontWeight": "600"}),
                html.Span(str(value) + " / " + str(target) + " " + unit, style={
                    "fontSize": "11px", "color": "#888", "float": "right"
                })
            ]),
            # Progress bar
            html.Div(
                html.Div(style={
                    "width": str(pct) + "%",
                    "height": "100%",
                    "backgroundColor": bar_color,
                    "borderRadius": "4px"
                }),
                style={
                    "backgroundColor": "#f0f0f0",
                    "borderRadius": "4px",
                    "height": "8px",
                    "margin": "4px 0"
                }
            ),
            # Alert message (only shown if there is an alert)
            html.P(alert, style={
                "fontSize": "10px",
                "color": "white",
                "backgroundColor": "#d94f3d",
                "borderRadius": "4px",
                "padding": "4px 8px",
                "margin": "4px 0 8px 0"
            }) if alert else html.Div(style={"marginBottom": "8px"})
        ]))
 
    return html.Div([
        html.H5("Guidelines", style={"fontWeight": "700", "marginBottom": "16px"}),
        html.Div(nutrient_rows)
    ], style=CARD_STYLE)
 
 
def make_conditions_card(patient):
    """
    Builds the active conditions card showing primary, risk, and inactive conditions.
    Each condition type has a different colour to show its severity.
    """
    # Colour scheme for each condition type
    badge_colors = {
        "primary":  {"bg": "#fff3e0", "color": "#e8a838", "border": "#e8a838"},
        "risk":     {"bg": "#fff3e0", "color": "#ff7043", "border": "#ff7043"},
        "inactive": {"bg": "#f5f5f5", "color": "#bbb",    "border": "#ddd"}
    }
 
    badges = []
    for condition_type, condition_list in patient["conditions"].items():
        colors = badge_colors[condition_type]
        for condition_name in condition_list:
            badges.append(html.Div([
                html.Span(condition_type.capitalize(), style={
                    "fontSize": "10px", "color": "#888", "display": "block"
                }),
                html.Span(condition_name, style={
                    "fontSize": "13px", "fontWeight": "600", "color": colors["color"]
                })
            ], style={
                "backgroundColor": colors["bg"],
                "border": "1px solid " + colors["border"],
                "borderRadius": "8px",
                "padding": "8px 12px",
                "margin": "4px"
            }))
 
    # Show a message if the patient has no conditions at all
    has_any_conditions = any(patient["conditions"].values())
    if not has_any_conditions:
        badges.append(html.P("No active conditions", style={
            "color": "#888", "fontSize": "13px", "padding": "8px"
        }))
 
    return html.Div([
        html.H5("Active Conditions", style={"fontWeight": "700", "marginBottom": "12px"}),
        html.Div(badges, style={"display": "flex", "flexWrap": "wrap"})
    ], style=CARD_STYLE)
 
 
# =============================================================================
# SECTION 5: PAGE LAYOUTS
# Each function builds a full page by combining the helper components above.
# =============================================================================
 
def page_dashboard(patient, meal_key):
    """
    Builds the main dashboard page for a given patient and meal.
    This is the default page when the app loads.
    """
    meal = SAMPLE_MEALS[meal_key]
    nutrients = MEAL_NUTRIENTS[meal_key]
 
    # Combine primary and risk conditions for scoring
    all_conditions = patient["conditions"]["primary"] + patient["conditions"]["risk"]
 
    # Calculate the nutritional grade
    grade, grade_description = calculate_grade(nutrients, all_conditions)
 
    return html.Div([
        make_patient_card(patient),
        make_score_cards(nutrients, grade, grade_description),
        # Bottom row: conditions + meal on the left, guidelines on the right
        html.Div([
            html.Div([
                make_conditions_card(patient),
                make_meal_card(meal)
            ], style={"width": "45%", "paddingRight": "12px"}),
            html.Div([
                make_guidelines(nutrients, all_conditions)
            ], style={"width": "55%"})
        ], style={"display": "flex"})
    ])
 
 
def page_patients():
    """
    Builds the patients list page showing all synthetic patients.
    Each patient has a 'View Dashboard' button that navigates to their dashboard.
    """
    patient_cards = []
 
    for patient in PATIENTS:
        # Get all active conditions for display
        all_conditions = patient["conditions"]["primary"] + patient["conditions"]["risk"]
        if all_conditions:
            conditions_text = ", ".join(all_conditions)
        else:
            conditions_text = "No active conditions"
 
        patient_cards.append(
            html.Div([
                html.Div([
                    # Avatar
                    html.Div(patient["avatar"], style={
                        "width": "44px", "height": "44px", "borderRadius": "50%",
                        "backgroundColor": "#e8a838", "color": "white",
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "fontWeight": "bold",
                        "fontSize": "14px", "marginRight": "14px", "flexShrink": "0"
                    }),
                    # Patient info
                    html.Div([
                        html.H5(patient["name"], style={"margin": "0 0 2px 0"}),
                        html.P(
                            "#" + patient["id"] + " · " + patient["sex"] +
                            " · Age " + str(patient["age"]) + " · " + patient["location"],
                            style={"margin": "0", "color": "#666", "fontSize": "12px"}
                        ),
                        html.P(conditions_text, style={
                            "margin": "4px 0 0 0", "fontSize": "12px",
                            "color": "#e8a838", "fontWeight": "600"
                        })
                    ]),
                    # View button - the id is used by the callback to know which patient was clicked
                    html.Button("View Dashboard", id="view-patient-" + patient["id"], style={
                        "marginLeft": "auto",
                        "backgroundColor": "#e8a838",
                        "border": "none",
                        "borderRadius": "8px",
                        "padding": "8px 16px",
                        "color": "white",
                        "cursor": "pointer",
                        "fontWeight": "600"
                    })
                ], style={"display": "flex", "alignItems": "center"})
            ], style=CARD_STYLE)
        )
 
    return html.Div([
        html.H4("Patients", style={"fontWeight": "700", "marginBottom": "20px"}),
        html.P(
            str(len(PATIENTS)) + " synthetic patients — for testing and demonstration purposes only.",
            style={"color": "#888", "fontSize": "13px", "marginBottom": "20px"}
        ),
        html.Div(patient_cards)
    ])
 
 
def page_disease_profiles():
    """
    Builds the disease profiles page explaining the condition multipliers
    used in the scoring algorithm.
    """
    profile_cards = []
 
    for profile in CONDITION_PROFILES:
        multiplier_rows = []
 
        for nutrient_name, effect_text, effect_color in profile["multipliers"]:
            multiplier_rows.append(
                html.Div([
                    html.Span(nutrient_name, style={
                        "fontSize": "13px", "fontWeight": "600", "flex": "1"
                    }),
                    html.Span(effect_text, style={
                        "fontSize": "12px",
                        "color": "white",
                        "backgroundColor": effect_color,
                        "borderRadius": "12px",
                        "padding": "2px 10px"
                    })
                ], style={
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "padding": "8px 0",
                    "borderBottom": "1px solid #f0f0f0"
                })
            )
 
        profile_cards.append(html.Div([
            html.H5(profile["name"], style={"fontWeight": "700", "marginBottom": "4px"}),
            html.P(profile["description"], style={
                "color": "#666", "fontSize": "12px", "marginBottom": "12px"
            }),
            html.Div(multiplier_rows)
        ], style=CARD_STYLE))
 
    return html.Div([
        html.H4("Disease Profiles", style={"fontWeight": "700", "marginBottom": "8px"}),
        html.P(
            "Condition-specific multipliers applied to the nutritional scoring algorithm. "
            "Based on NNR 2023 and Institutionskost 2025 clinical guidelines.",
            style={"color": "#666", "fontSize": "13px", "marginBottom": "20px"}
        ),
        html.Div(profile_cards)
    ])
 
 
def page_data_sources():
    """
    Builds the data sources page with links to NNR 2023, Institutionskost, and Frida.
    """
    source_cards = []
 
    for source in DATA_SOURCES:
        source_cards.append(html.Div([
            html.H5(source["name"], style={"fontWeight": "700", "marginBottom": "4px"}),
            html.P(source["publisher"], style={
                "color": "#e8a838", "fontSize": "12px",
                "fontWeight": "600", "marginBottom": "8px"
            }),
            html.P(source["description"], style={
                "color": "#666", "fontSize": "13px", "marginBottom": "12px"
            }),
            html.A("Visit source →", href=source["url"], target="_blank", style={
                "color": "#e8a838", "fontSize": "13px", "fontWeight": "600"
            })
        ], style=CARD_STYLE))
 
    return html.Div([
        html.H4("Data Sources", style={"fontWeight": "700", "marginBottom": "8px"}),
        html.P(
            "All nutritional guidelines and food composition data used in this system.",
            style={"color": "#666", "fontSize": "13px", "marginBottom": "20px"}
        ),
        html.Div(source_cards)
    ])
 
 
def page_placeholder(title, message):
    """
    A simple placeholder page for sections that are not yet implemented.
    """
    return html.Div([
        html.H4(title, style={"fontWeight": "700", "marginBottom": "8px"}),
        html.Div([
            html.P("🚧", style={"fontSize": "48px", "margin": "0 0 16px 0"}),
            html.P(message, style={"color": "#666", "fontSize": "14px"})
        ], style={**CARD_STYLE, "textAlign": "center", "padding": "60px 20px"})
    ])
 
 
# =============================================================================
# SECTION 6: ADD MEAL MODAL
# The modal is the popup window that appears when "+ ADD Meal" is clicked.
# It lets the user select a patient and a menu day, shows a preview of the
# score, and then updates the dashboard when confirmed.
# =============================================================================
 
def make_add_meal_modal():
    """
    Builds the modal popup for scoring a meal.
    The dropdowns are populated with the patient list and meal list from the data above.
    """
    # Build dropdown options from the patients list
    patient_options = []
    for patient in PATIENTS:
        patient_options.append({
            "label": patient["name"] + " (#" + patient["id"] + ")",
            "value": patient["id"]
        })
 
    # Build dropdown options from the meals list
    meal_options = []
    for meal_key in SAMPLE_MEALS.keys():
        meal_options.append({"label": meal_key, "value": meal_key})
 
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Score a Meal")),
        dbc.ModalBody([
            html.P(
                "Select a patient and a menu day to calculate the nutritional score.",
                style={"color": "#666", "marginBottom": "20px"}
            ),
 
            html.Label("Select Patient", style={"fontWeight": "600", "marginBottom": "6px"}),
            dcc.Dropdown(
                id="modal-patient-select",
                options=patient_options,
                placeholder="Choose a patient...",
                style={"marginBottom": "16px"}
            ),
 
            html.Label("Select Menu Day", style={"fontWeight": "600", "marginBottom": "6px"}),
            dcc.Dropdown(
                id="modal-meal-select",
                options=meal_options,
                placeholder="Choose a day...",
                style={"marginBottom": "16px"}
            ),
 
            # Preview area - updated by a callback when selections change
            html.Div(id="modal-preview", style={"marginTop": "16px"})
        ]),
        dbc.ModalFooter([
            html.Button("Cancel", id="modal-cancel", style={
                "backgroundColor": "white",
                "border": "1px solid #ddd",
                "borderRadius": "8px",
                "padding": "8px 20px",
                "marginRight": "8px",
                "cursor": "pointer"
            }),
            html.Button("Score this meal →", id="modal-score", style={
                "backgroundColor": "#e8a838",
                "border": "none",
                "borderRadius": "8px",
                "padding": "8px 20px",
                "color": "white",
                "cursor": "pointer",
                "fontWeight": "700"
            })
        ])
    ], id="add-meal-modal", is_open=False, size="lg")
 
 
# =============================================================================
# SECTION 7: APP LAYOUT
# This puts together the full page structure: sidebar + main content area.
# dcc.Store is used to remember the current page and selected patient/meal
# across interactions without needing a database.
# =============================================================================
 
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="NutriScan",
    suppress_callback_exceptions=True
)
 
app.layout = html.Div([
 
    # These stores act like variables that persist across interactions.
    # They store the current page name and the selected patient/meal.
    dcc.Store(id="current-page", data="dashboard"),
    dcc.Store(id="selected-patient-id", data=PATIENTS[0]["id"]),
    dcc.Store(id="selected-meal-key", data=list(SAMPLE_MEALS.keys())[0]),
 
    # Sidebar (always visible on the left)
    make_sidebar(),
 
    # Modal popup (hidden by default, shown when + ADD Meal is clicked)
    make_add_meal_modal(),
 
    # Main content area
    html.Div([
 
        # Top bar with title and buttons
        html.Div([
            html.H3("Patient Nutrition Dashboard", id="page-title", style={
                "margin": "0", "fontWeight": "700", "color": "#e8a838"
            }),
            html.Div([
                html.Button("📄 Export PDF", id="export-pdf-btn", style={
                    "backgroundColor": "white",
                    "border": "1px solid #ddd",
                    "borderRadius": "8px",
                    "padding": "8px 16px",
                    "marginRight": "12px",
                    "cursor": "pointer",
                    "fontWeight": "600"
                }),
                html.Button("+ ADD Meal", id="open-modal-btn", style={
                    "backgroundColor": "#e8a838",
                    "border": "none",
                    "borderRadius": "8px",
                    "padding": "8px 16px",
                    "color": "white",
                    "cursor": "pointer",
                    "fontWeight": "700"
                })
            ])
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "20px"
        }),
 
        # Page content area - updated by the render_page callback
        html.Div(id="page-content")
 
    ], style=CONTENT_STYLE)
])
 
 
# =============================================================================
# SECTION 8: CALLBACKS
# Callbacks are what make Dash interactive. Each callback is a function that
# runs automatically when its Input changes, and updates its Output.
# =============================================================================
 
# --- Callback 1: Render the correct page ---
# This runs whenever the current page, patient, or meal changes.
# It returns the right page layout and updates the title in the top bar.
@app.callback(
    Output("page-content", "children"),
    Output("page-title", "children"),
    Input("current-page", "data"),
    Input("selected-patient-id", "data"),
    Input("selected-meal-key", "data")
)
def render_page(page, patient_id, meal_key):
    # Find the patient object that matches the selected id
    selected_patient = PATIENTS[0]
    for patient in PATIENTS:
        if patient["id"] == patient_id:
            selected_patient = patient
            break
 
    # Map page names to their display titles
    page_titles = {
        "dashboard": "Patient Nutrition Dashboard",
        "patients": "Patients",
        "meal-plans": "Meal Plans",
        "nutritional-gaps": "Nutritional Gaps",
        "frida-foods": "Frida Foods",
        "disease-profiles": "Disease Profiles",
        "data-sources": "Data Sources",
        "settings": "Settings"
    }
    title = page_titles.get(page, "NutriScan")
 
    # Return the right page layout based on the current page
    if page == "dashboard":
        return page_dashboard(selected_patient, meal_key), title
    elif page == "patients":
        return page_patients(), title
    elif page == "disease-profiles":
        return page_disease_profiles(), title
    elif page == "data-sources":
        return page_data_sources(), title
    elif page == "nutritional-gaps":
        return page_placeholder("Nutritional Gaps", "Nutritional gap analysis coming soon."), title
    elif page == "frida-foods":
        return page_placeholder("Frida Foods", "Frida food database browser coming soon."), title
    elif page == "settings":
        return page_placeholder("Settings", "Settings panel reserved for future development."), title
    elif page == "meal-plans":
        return page_placeholder("Meal Plans", "Full meal plan history coming soon."), title
    else:
        return page_dashboard(selected_patient, meal_key), title
 
 
# --- Callback 2: Sidebar navigation ---
# This runs when any sidebar link is clicked.
# It updates the current-page store, which triggers callback 1 above.
@app.callback(
    Output("current-page", "data"),
    [Input("nav-" + page, "n_clicks") for page in [
        "dashboard", "patients", "meal-plans", "nutritional-gaps",
        "frida-foods", "disease-profiles", "data-sources", "settings"
    ]],
    prevent_initial_call=True
)
def navigate(*args):
    # ctx.triggered_id tells us which element triggered the callback
    triggered = ctx.triggered_id
    if triggered:
        # Remove the "nav-" prefix to get just the page name
        return triggered.replace("nav-", "")
    return "dashboard"
 
 
# --- Callback 3: Open/close modal and score the meal ---
# This handles three different buttons: open, cancel, and score.
# ctx.triggered_id tells us which button was clicked.
@app.callback(
    Output("add-meal-modal", "is_open"),
    Output("selected-patient-id", "data"),
    Output("selected-meal-key", "data"),
    Output("current-page", "data", allow_duplicate=True),
    Input("open-modal-btn", "n_clicks"),
    Input("modal-cancel", "n_clicks"),
    Input("modal-score", "n_clicks"),
    State("modal-patient-select", "value"),
    State("modal-meal-select", "value"),
    State("add-meal-modal", "is_open"),
    State("selected-patient-id", "data"),
    State("selected-meal-key", "data"),
    prevent_initial_call=True
)
def handle_modal(open_click, cancel_click, score_click,
                 selected_patient, selected_meal,
                 is_open, current_patient, current_meal):
 
    triggered = ctx.triggered_id
 
    # Open button was clicked - show the modal
    if triggered == "open-modal-btn":
        return True, current_patient, current_meal, "dashboard"
 
    # Cancel button was clicked - close the modal without changing anything
    if triggered == "modal-cancel":
        return False, current_patient, current_meal, "dashboard"
 
    # Score button was clicked - update the dashboard with the selected patient and meal
    if triggered == "modal-score":
        if selected_patient:
            new_patient = selected_patient
        else:
            new_patient = current_patient
 
        if selected_meal:
            new_meal = selected_meal
        else:
            new_meal = current_meal
 
        return False, new_patient, new_meal, "dashboard"
 
    # Fallback - no change
    return is_open, current_patient, current_meal, "dashboard"
 
 
# --- Callback 4: Live preview in the modal ---
# This runs whenever the patient or meal dropdown changes in the modal.
# It shows a preview of the grade before the user confirms.
@app.callback(
    Output("modal-preview", "children"),
    Input("modal-patient-select", "value"),
    Input("modal-meal-select", "value")
)
def update_modal_preview(patient_id, meal_key):
    # If either dropdown is empty, show a hint message
    if not patient_id or not meal_key:
        return html.P(
            "Select a patient and meal day to see a preview.",
            style={"color": "#aaa", "fontSize": "12px"}
        )
 
    # Find the selected patient
    selected_patient = None
    for patient in PATIENTS:
        if patient["id"] == patient_id:
            selected_patient = patient
            break
 
    meal = SAMPLE_MEALS.get(meal_key)
    nutrients = MEAL_NUTRIENTS.get(meal_key, {})
 
    if not selected_patient or not meal:
        return None
 
    # Calculate the grade for this patient + meal combination
    all_conditions = selected_patient["conditions"]["primary"] + selected_patient["conditions"]["risk"]
    grade, grade_description = calculate_grade(nutrients, all_conditions)
    grade_color = GRADE_COLORS.get(grade, "#888")
 
    # Show a small preview card
    return html.Div([
        html.Hr(),
        html.P("Preview", style={
            "fontWeight": "600", "color": "#888",
            "fontSize": "11px", "letterSpacing": "1px"
        }),
        html.Div([
            # Patient and meal info
            html.Div([
                html.P("Patient: " + selected_patient["name"],
                       style={"margin": "0", "fontWeight": "600"}),
                html.P("Meal: " + meal["main"]["name"] + " + " + meal["dessert"]["name"],
                       style={"margin": "0", "color": "#666", "fontSize": "12px"}),
                html.P("Conditions: " + (", ".join(all_conditions) if all_conditions else "None"),
                       style={"margin": "0", "color": "#666", "fontSize": "12px"})
            ], style={"flex": "1"}),
            # Grade preview
            html.Div([
                html.Span(grade, style={
                    "fontSize": "48px",
                    "fontWeight": "900",
                    "color": grade_color,
                    "lineHeight": "1"
                }),
                html.P(grade_description, style={
                    "fontSize": "11px",
                    "color": grade_color,
                    "fontWeight": "600",
                    "margin": "0"
                })
            ], style={"textAlign": "center"})
        ], style={
            "display": "flex",
            "alignItems": "center",
            "backgroundColor": "#f8f8f8",
            "borderRadius": "8px",
            "padding": "12px"
        })
    ])
 
 
# =============================================================================
# RUN
# This block only runs when you execute this file directly.
# =============================================================================
if __name__ == "__main__":
    print("Starting NutriScan dashboard...")
    print("Open your browser at: http://127.0.0.1:8050")
    app.run(debug=True)
