# The dashboard.py module is the main frontend for the NutriScan system and it calls each module in the pipeline in sequence and displays the results. 
# The pipeline modules don't know anything about the frontend, they just take inputs and return outputs. The dashboard is what stings them together for the user. 
# It is built with Dash -  a Python library that lets us build web interfaces. It runs a local web server and we interact with it through the browser.
# Run this file directly to start the dashboard: python frontend/dashboard.py 
# Run this to start the API in a split terminal: uvicorn api.main:app --reload
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

import sys
from pathlib import Path

# Make sure the project root is on the path so pipeline imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
import dash 
from dash import html, dcc, Input, Output, State, ctx
import dash_bootstrap_components as dbc 


# ----------------
# API Connection 
# Tries to fetch live data from the FastAPI backend (port 8000).
# Falls back to hardcoded data if the API is not running, so the dashboard
# still works during development or if something goes wrong on demo day.
# ----------------

API_URL = "http://127.0.0.1:8000"
 
 
def api_get_patients():
    """Fetches patients from GET /patients. Returns None if unreachable."""
    try:
        r = requests.get(f"{API_URL}/patients", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
 
 
def api_score_meal(pdf_path, day_number, conditions, patient_id=None):
    """Calls POST /score/meal. Returns None if unreachable."""
    try:
        r = requests.post(
            f"{API_URL}/score/meal",
            json={"pdf_path": pdf_path, "day_number": day_number,
                  "conditions": conditions, "patient_id": patient_id},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
 
 
def api_score_week(pdf_path, conditions, patient_id=None):
    """Calls POST /score/week. Returns None if unreachable."""
    try:
        r = requests.post(
            f"{API_URL}/score/week",
            json={"pdf_path": pdf_path, "conditions": conditions, "patient_id": patient_id},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
 
 
def api_patient_history(patient_id):
    """Calls GET /patients/{id}/history. Returns empty list if unreachable."""
    try:
        r = requests.get(f"{API_URL}/patients/{patient_id}/history", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []
 
 
def api_check_health():
    """Returns True if the API is running, False otherwise."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=1)
        return r.status_code == 200
    except Exception:
        return False

# -------------------
# Section 1: DATA 
# Hardcoded fallback list - used when the API is not working
# Each patient has an id, basic demographics, and a list of health conditions.
# Conditions are split into primary (active), risk (at risk), and inactive.
# -------------------

_PATIENTS_FALLBACK = [
    {
        "id": "XY-5217",
        "name": "Erik Andersen",
        "sex": "Male",
        "age": 82,
        "location": "Wing A, Room 3",
        "avatar": "EA",
        "conditions": {
            "primary": ["Hypertension", "Type 2 Diabetes"],
            "risk": ["Malnutrition Risk"],
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
            "risk": ["Malnutrition Risk"],
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

# Try to load live patients from the API on startup; use fallback if it's down.
_live_patients = api_get_patients()
PATIENTS = _live_patients if _live_patients is not None else _PATIENTS_FALLBACK
 
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
# The real pipeline gives much more accurate numbers
# (see pdf_extractor.py + nutrient_lookup.py), but these work fine for the demo.
# Sodium is stored in grams here — calculate_grade() converts to mg before scoring.
MEAL_NUTRIENTS = {
    "March 2026 - Day 1":  {"energy": 680, "protein": 38, "carbs": 52, "fibre": 4,  "calcium": 180, "sodium": 0.55},
    "March 2026 - Day 2":  {"energy": 620, "protein": 42, "carbs": 48, "fibre": 6,  "calcium": 210, "sodium": 0.45},
    "March 2026 - Day 5":  {"energy": 520, "protein": 35, "carbs": 40, "fibre": 5,  "calcium": 190, "sodium": 0.38},
    "March 2026 - Day 10": {"energy": 590, "protein": 36, "carbs": 45, "fibre": 3,  "calcium": 160, "sodium": 0.52},
    "April 2026 - Day 14": {"energy": 610, "protein": 40, "carbs": 50, "fibre": 7,  "calcium": 220, "sodium": 0.42},
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
            ("Energy", "0.5x reward (reduced penalty)", "#4caf7d"),
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
    "A": "#2d7d46",   # forest green
    "B": "#5a9e3a",   # olive green
    "C": "#c8841a",   # amber
    "D": "#c0532a",   # terracotta
    "E": "#a82020",   # deep red
}
 
 
# =============================================================================
# SECTION 2: SCORING FUNCTION
# Calls pipeline/scoring.py directly.
# =============================================================================
 
def calculate_grade(nutrients, conditions):
    """
    Wraps pipeline/scoring.py so the dashboard always produces the same
    grades as the rest of the system.
 
    The dashboard stores sodium in grams (to match the g display unit),
    but scoring.py works in mg — we convert here at the boundary.
    """
    try:
        from pipeline.scoring import score_meal
    except ImportError:
        from scoring import score_meal

    # Dashboard MEAL_NUTRIENTS uses sodium in grams — convert to mg for scoring.py
    nutrients_for_scoring = {
        "energy_kcal":  nutrients.get("energy",  0),
        "protein_g":    nutrients.get("protein", 0),
        "fiber_g":      nutrients.get("fibre",   0),
        "calcium_mg":   nutrients.get("calcium", 0),
        "sodium_mg":    nutrients.get("sodium",  0) * 1000,   # g → mg
        "fat_sat_g":    nutrients.get("fat_sat", 0),
        "sugar_g":      nutrients.get("carbs",   0) * 0.3,    # rough: ~30% of carbs as sugar
        "potassium_mg": nutrients.get("potassium", 0)
    }
 
    result = score_meal(nutrients_for_scoring, conditions)
    return result["grade"], result["grade_description"]
 
 
# =============================================================================
# SECTION 3: SHARED STYLES
# These style dictionaries are reused across multiple components to keep
# the look consistent without repeating the same CSS everywhere.
# =============================================================================
 
# Palette as constants so it's easy to tweak in one place
C_SIDEBAR   = "#2c3e50"    # dark slate
C_ACCENT    = "#c8841a"    # warm amber
C_BG        = "#f5f2ed"    # warm off-white
C_CARD      = "#ffffff"
C_TEXT      = "#2c2c2c"
C_MUTED     = "#7a7a7a"
C_BORDER    = "#e0dbd3"
C_GREEN     = "#2d7d46"
C_RED       = "#a82020"
C_ORANGE    = "#c8841a"
 
SIDEBAR_STYLE = {
    "width": "230px",
    "minHeight": "100vh",
    "backgroundColor": C_SIDEBAR,
    "position": "fixed",
    "top": "0",
    "left": "0",
    "overflowY": "auto",
    "zIndex": "100"
}
 
CONTENT_STYLE = {
    "marginLeft": "230px",
    "padding": "28px 32px",
    "backgroundColor": C_BG,
    "minHeight": "100vh"
}
 
CARD_STYLE = {
    "backgroundColor": C_CARD,
    "borderRadius": "10px",
    "padding": "20px 24px",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.07)",
    "marginBottom": "16px",
    "border": f"1px solid {C_BORDER}"
}
 
# =============================================================================
# SECTION 4: UI Components
# Each function builds one reusable UI component.
# =============================================================================
 
def make_sidebar():
    """Left navigation bar. Each item has an id like 'nav-dashboard' so the
    navigate callback can pick up which one was clicked."""
 
    nav_sections = [
        ("OVERVIEW", [
            ("dashboard",        "🏠  Dashboard"),
            ("patients",         "👥  Patients"),
            ("meal-plans",       "🍽️  Meal plans"),
        ]),
        ("ANALYSIS", [
            ("nutritional-gaps", "📊  Nutritional gaps"),
            ("frida-foods",      "🥗  Frida foods"),
            ("disease-profiles", "🏥  Disease profiles"),
        ]),
        ("DATA", [
            ("data-sources",     "📁  Data sources"),
            ("settings",         "⚙️  Settings"),
        ]),
    ]
 
    nav_items = []
    for section_title, links in nav_sections:
        nav_items.append(
            html.P(section_title, style={
                "color": "#8fa3b0",
                "fontSize": "10px",
                "fontWeight": "bold",
                "letterSpacing": "1.5px",
                "marginTop": "22px",
                "marginBottom": "6px",
                "paddingLeft": "18px"
            })
        )
        for page_id, label in links:
            nav_items.append(
                html.Div(label, id="nav-" + page_id, style={
                    "padding": "9px 18px",
                    "borderRadius": "6px",
                    "cursor": "pointer",
                    "color": "#c8d6df",
                    "fontSize": "13px",
                    "marginBottom": "2px"
                })
            )
 
    return html.Div([
        # Logo
        html.Div([
            html.H2("NutriScan", style={
                "color": C_ACCENT,
                "margin": "0",
                "fontSize": "22px",
                "fontWeight": "bold",
                "letterSpacing": "0.5px"
            }),
            html.P("Meal nutrition analysis · RUC 2026", style={
                "color": "#8fa3b0",
                "fontSize": "10px",
                "margin": "4px 0 0 0"
            })
        ], style={"padding": "24px 18px 14px"}),
 
        html.Hr(style={"borderColor": "#3d5166", "margin": "0 18px"}),
 
        html.Div(nav_items, style={"padding": "6px 8px"}),
 
        # Small disclaimer at the bottom
        html.Div([
            # API status dot — green when running, grey when offline
            html.Div([
                html.Span("●", style={
                    "color": "#2d7d46" if api_check_health() else "#666",
                    "fontSize": "10px", "marginRight": "5px",
                }),
                html.Span(
                    "API connected" if api_check_health() else "API offline",
                    style={"fontSize": "10px", "color": "#5a7080"}
                ),
            ], style={"marginBottom": "5px"}),
            html.P("⚠ Synthetic patient data.", style={
                "fontSize": "10px", "color": "#5a7080", "margin": "0"
            }),
            html.P("Do not use for clinical decisions.", style={
                "fontSize": "10px", "color": "#5a7080", "margin": "2px 0 0 0"
            })
        ], style={"position": "absolute", "bottom": "16px", "padding": "0 18px"})
 
    ], style=SIDEBAR_STYLE)
 
 
def make_patient_card(patient):
    """Profile banner at the top of the dashboard page."""
    badges = []
    for condition in patient["conditions"]["primary"]:
        badges.append(
            html.Span(condition, style={
                "backgroundColor": "#fef5e7",
                "color": C_ACCENT,
                "border": f"1px solid {C_ACCENT}",
                "borderRadius": "20px",
                "padding": "3px 11px",
                "fontSize": "12px",
                "fontWeight": "bold",
                "marginRight": "6px"
            })
        )
 
    return html.Div([
        html.Div([
            # Avatar
            html.Div(patient["avatar"], style={
                "width": "48px",
                "height": "48px",
                "borderRadius": "50%",
                "backgroundColor": C_ACCENT,
                "color": "white",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "fontWeight": "bold",
                "fontSize": "15px",
                "marginRight": "16px",
                "flexShrink": "0"
            }),
            # Info
            html.Div([
                html.H4(patient["name"], style={
                    "margin": "0 0 3px 0",
                    "fontSize": "16px",
                    "color": C_TEXT
                }),
                html.P(
                    f"#{patient['id']} · {patient['sex']} · Age {patient['age']} · {patient['location']}",
                    style={"margin": "0", "color": C_MUTED, "fontSize": "12px"
}
                ),
            ]),
            # Condition badges flush right
            html.Div(badges, style={
                "marginLeft": "auto",
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px"
            })
        ], style={"display": "flex", "alignItems": "center"})
    ], style={**CARD_STYLE, "marginBottom": "20px",
              "borderLeft": f"4px solid {C_ACCENT}"})
 
 
def make_score_cards(nutrients, grade, grade_description):
    """Three summary cards across the top: energy, protein, and grade."""
    energy_pct  = round(nutrients["energy"]  / 700 * 100)
    protein_pct = round(nutrients["protein"] / 25  * 100)
    grade_color = GRADE_COLORS.get(grade, "#888")
 
    def pct_color(pct):
        return C_GREEN if pct >= 85 else (C_ORANGE if pct >= 60 else C_RED)
 
    stat_label_style = {
        "fontSize": "10px", "fontWeight": "bold", "letterSpacing": "1px",
        "color": C_MUTED, "margin": "0 0 8px 0"
    }
    stat_value_style = {
        "margin": "0 0 4px 0", "fontSize": "26px", "fontWeight": "bold",
        "color": C_TEXT
    }
    stat_sub_style = {
        "fontSize": "11px", "color": C_MUTED, "margin": "0 0 6px 0"
    }
 
    return html.Div([
 
        # Energy
        html.Div([
            html.P("ENERGY INTAKE", style=stat_label_style),
            html.H3(f"{int(nutrients['energy'])} kcal", style=stat_value_style),
            html.P("Target: ~700 kcal / meal", style=stat_sub_style),
            html.P(f"{energy_pct}% of target", style={
                "fontSize": "12px", "color": pct_color(energy_pct),
                "margin": "0", "fontWeight": "bold"
            })
        ], style={**CARD_STYLE, "flex": "1", "marginRight": "12px", "marginBottom": "0"}),
 
        # Protein
        html.Div([
            html.P("PROTEIN INTAKE", style=stat_label_style),
            html.H3(f"{nutrients['protein']} g", style=stat_value_style),
            html.P("Target: ~25 g / meal  (NNR 2023)", style=stat_sub_style),
            html.P(f"{protein_pct}% of target", style={
                "fontSize": "12px", "color": pct_color(protein_pct),
                "margin": "0", "fontWeight": "bold"
            })
        ], style={**CARD_STYLE, "flex": "1", "marginRight": "12px", "marginBottom": "0"}),
 
        # Grade
        html.Div([
            html.P("NUTRITIONAL GRADE", style=stat_label_style),
            html.Div([
                html.Span(grade, style={
                    "fontSize": "64px",
                    "fontWeight": "bold",
                    "color": grade_color,
                    "lineHeight": "1"
                }),
                html.Div([
                    html.P("Grade", style={"fontSize": "11px", "color": C_MUTED, "margin": "0"
}),
                    html.P(grade_description, style={
                        "fontSize": "11px", "color": grade_color,
                        "fontWeight": "bold", "margin": "0"
                    })
                ], style={"marginLeft": "14px"})
            ], style={"display": "flex", "alignItems": "center"}),
            html.P("A = Excellent  ·  B = Good  ·  C = Adequate  ·  D = Poor  ·  E = Critical",
                   style={"fontSize": "9px", "color": "#bbb",
                          "margin": "10px 0 0 0"
})
        ], style={**CARD_STYLE, "flex": "1", "marginBottom": "0",
                  "borderLeft": f"4px solid {grade_color}"})
 
    ], style={"display": "flex", "marginBottom": "16px"})
 
 
def make_meal_card(meal):
    """Shows today's main dish, sides, and dessert."""
    section_label = {
        "fontSize": "9px", "fontWeight": "bold", "letterSpacing": "1.5px",
        "color": C_MUTED, "margin": "0 0 4px 0"
    }
    return html.Div([
        html.H5("Today's Meal", style={
            "fontWeight": "bold", "marginBottom": "3px",
 "color": C_TEXT
        }),
        html.P(meal["day"], style={
            "color": C_MUTED, "fontSize": "12px",
            "marginBottom": "14px"
        }),
 
        # Main
        html.Div([
            html.P("MAIN DISH", style=section_label),
            html.H5(meal["main"]["name"], style={
                "margin": "0 0 3px 0",
 "color": C_TEXT
            }),
            html.P("Ingredients: " + ", ".join(meal["main"]["ingredients"]),
                   style={"fontSize": "11px", "color": C_MUTED,
                          "margin": "0"
})
        ], style={
            "backgroundColor": "#fef8ef",
            "borderLeft": f"3px solid {C_ACCENT}",
            "borderRadius": "0 6px 6px 0",
            "padding": "11px 14px",
            "marginBottom": "8px"
        }),
 
        # Sides
        html.Div([
            html.P("SIDES", style=section_label),
            html.P(", ".join(meal["sides"]),
                   style={"fontSize": "13px", "margin": "0",
 "color": C_TEXT})
        ], style={
            "backgroundColor": "#f7f5f2",
            "borderRadius": "6px",
            "padding": "11px 14px",
            "marginBottom": "8px"
        }),
 
        # Dessert
        html.Div([
            html.P("DESSERT", style=section_label),
            html.H5(meal["dessert"]["name"], style={
                "margin": "0 0 3px 0",
 "color": C_TEXT
            }),
            html.P("Ingredients: " + ", ".join(meal["dessert"]["ingredients"]),
                   style={"fontSize": "11px", "color": C_MUTED,
                          "margin": "0"
})
        ], style={
            "backgroundColor": "#f0f4f8",
            "borderLeft": "3px solid #6b8cae",
            "borderRadius": "0 6px 6px 0",
            "padding": "11px 14px"
        }),
 
    ], style=CARD_STYLE)
 
 
def make_guidelines(nutrients, conditions):
    """
    Progress bars for each nutrient with condition-specific alerts.
    reverse=True means lower is better (sodium).
    """
    nutrient_targets = [
        ("Energy (kcal)",      "energy",  700,  "kcal", False),
        ("Protein (g)",        "protein",  25,  "g",    False),
        ("Carbohydrate (g)",   "carbs",    60,  "g",    False),
        ("Dietary fibre (g)",  "fibre",     8,  "g",    False),
        ("Calcium (mg)",       "calcium", 300,  "mg",   False),
        ("Salt / sodium (g)",  "sodium",    5,  "g",    True),
    ]
 
    rows = []
    for label, key, target, unit, reverse in nutrient_targets:
        value = nutrients.get(key, 0)
        pct   = min(round(value / target * 100), 100)
 
        if reverse:
            bar_color = C_RED if value >= target else C_GREEN
        else:
            bar_color = C_GREEN if pct >= 85 else (C_ORANGE if pct >= 60 else C_RED)
 
        alert = None
        if reverse and value >= target:
            alert = "Exceeds the recommended limit. Check sodium-rich components."
        elif not reverse and pct < 60:
            alert = "Below target — consider adjusting the meal."
 
        # Condition-specific overrides
        if key == "sodium"  and "Hypertension"     in conditions and value >= target * 0.9:
            alert = "⚠ Hypertension: sodium is near the limit. Review immediately."
        if key == "protein" and "Malnutrition Risk" in conditions and pct < 80:
            alert = "⚠ Malnutrition Risk: protein is low. Consider supplementation."
        if key == "calcium" and "Osteoporosis"      in conditions and pct < 80:
            alert = "⚠ Osteoporosis: calcium is insufficient for bone health."
 
        rows.append(html.Div([
            html.Div([
                html.Span(label, style={
                    "fontSize": "12px", "fontWeight": "bold",
                    "color": C_TEXT
                }),
                html.Span(f"{value} / {target} {unit}", style={
                    "fontSize": "11px", "color": C_MUTED, "float": "right"
                })
            ]),
            # Bar track
            html.Div(
                html.Div(style={
                    "width": f"{pct}%",
                    "height": "100%",
                    "backgroundColor": bar_color,
                    "borderRadius": "4px",
                    "transition": "width 0.4s ease"
                }),
                style={
                    "backgroundColor": "#ede9e3",
                    "borderRadius": "4px",
                    "height": "7px",
                    "margin": "5px 0"
                }
            ),
            html.P(alert, style={
                "fontSize": "10px",
                "color": "white",
                "backgroundColor": C_RED,
                "borderRadius": "4px",
                "padding": "3px 8px",
                "margin": "3px 0 10px 0"
            }) if alert else html.Div(style={"marginBottom": "10px"})
        ]))
 
    return html.Div([
        html.H5("Nutrient guidelines", style={
            "fontWeight": "bold", "marginBottom": "14px",
 "color": C_TEXT
        }),
        html.Div(rows)
    ], style=CARD_STYLE)
 
 
def make_conditions_card(patient):
    """Shows all conditions grouped by type with colour-coded badges."""
    badge_colors = {
        "primary":  {"bg": "#fef5e7", "color": C_ACCENT,  "border": C_ACCENT},
        "risk":     {"bg": "#fdf0ee", "color": "#b03a2e",  "border": "#c0532a"},
        "inactive": {"bg": "#f5f5f5", "color": "#aaa",     "border": "#ddd"}
    }
 
    badges = []
    for condition_type, condition_list in patient["conditions"].items():
        c = badge_colors[condition_type]
        for name in condition_list:
            badges.append(html.Div([
                html.Span(condition_type.capitalize(), style={
                    "fontSize": "9px", "color": C_MUTED,
                    "display": "block"
                }),
                html.Span(name, style={
                    "fontSize": "12px", "fontWeight": "bold",
                    "color": c["color"]
                })
            ], style={
                "backgroundColor": c["bg"],
                "border": f"1px solid {c['border']}",
                "borderRadius": "7px",
                "padding": "7px 12px",
                "margin": "3px"
            }))
 
    if not any(patient["conditions"].values()):
        badges.append(html.P("No active conditions", style={
            "color": C_MUTED, "fontSize": "13px",
            "padding": "6px"
        }))
 
    return html.Div([
        html.H5("Active conditions", style={
            "fontWeight": "bold", "marginBottom": "10px",
 "color": C_TEXT
        }),
        html.Div(badges, style={"display": "flex", "flexWrap": "wrap"})
    ], style=CARD_STYLE)
 
 
# =============================================================================
# SECTION 5: PAGE LAYOUTS
# Each function builds a full page by combining the helper components above.
# =============================================================================

def page_dashboard(patient, meal_key, api_score=None):
    meal      = SAMPLE_MEALS[meal_key]
    nutrients = MEAL_NUTRIENTS[meal_key]
    all_conditions = patient["conditions"]["primary"] + patient["conditions"]["risk"]
    
    # Use the real API score if we have one, otherwise fall back to local
    if api_score:
        grade             = api_score["grade"]
        grade_description = api_score["grade_description"]
        # Use real nutrients from the API response if available
        api_nutrients = api_score.get("nutrients")
        if api_nutrients:
            nutrients = {
                "energy":  round(api_nutrients.get("energy_kcal", nutrients["energy"]), 0),
                "protein": round(api_nutrients.get("protein_g",   nutrients["protein"]), 1),
                "carbs":   nutrients["carbs"],
                "fibre":   round(api_nutrients.get("fiber_g",     nutrients["fibre"]), 1),
                "calcium": round(api_nutrients.get("calcium_mg",  nutrients["calcium"]), 0),
                "sodium":  round(api_nutrients.get("sodium_mg", 0) / 1000, 2),
        }
    else:
        grade, grade_description = calculate_grade(nutrients, all_conditions)

    return html.Div([
        make_patient_card(patient),
        make_score_cards(nutrients, grade, grade_description),
        html.Div([
            html.Div([
                make_conditions_card(patient),
                make_meal_card(meal),
            ], style={"width": "45%", "paddingRight": "12px"}),
            html.Div([
                make_guidelines(nutrients, all_conditions),
            ], style={"width": "55%"}),
        ], style={"display": "flex"})
    ])
 
 
def page_patients():
    """
    Builds the patients list page showing all synthetic patients.
    Each patient has a 'View Dashboard' button that navigates to their dashboard.
    """
    patient_cards = []
 
    cards = []
    for patient in PATIENTS:
        all_conditions = patient["conditions"]["primary"] + patient["conditions"]["risk"]
        condition_text = ", ".join(all_conditions) if all_conditions else "No active conditions"
 
        cards.append(html.Div([
            html.Div([
                html.Div(patient["avatar"], style={
                    "width": "42px", "height": "42px", "borderRadius": "50%",
                    "backgroundColor": C_ACCENT, "color": "white",
                    "display": "flex", "alignItems": "center",
                    "justifyContent": "center", "fontWeight": "bold",
                    "fontSize": "13px", "marginRight": "14px", "flexShrink": "0"
                }),
                html.Div([
                    html.H5(patient["name"], style={
                        "margin": "0 0 2px 0",
 "color": C_TEXT
                    }),
                    html.P(
                        f"#{patient['id']} · {patient['sex']} · Age {patient['age']} · {patient['location']}",
                        style={"margin": "0", "color": C_MUTED,
                               "fontSize": "12px"
}
                    ),
                    html.P(condition_text, style={
                        "margin": "3px 0 0 0", "fontSize": "12px",
                        "color": C_ACCENT, "fontWeight": "bold"
                    })
                ]),
                html.Button("View dashboard", id="view-patient-" + patient["id"], style={
                    "marginLeft": "auto",
                    "backgroundColor": C_ACCENT,
                    "border": "none",
                    "borderRadius": "6px",
                    "padding": "7px 14px",
                    "color": "white",
                    "cursor": "pointer",
                    "fontWeight": "bold",
                    "fontSize": "12px"
                })
            ], style={"display": "flex", "alignItems": "center"})
        ], style=CARD_STYLE))
 
    return html.Div([
        html.H4("Patients", style={
            "fontWeight": "bold", "marginBottom": "6px",
 "color": C_TEXT
        }),
        html.P(
            f"{len(PATIENTS)} synthetic patients — for testing and demonstration only.",
            style={"color": C_MUTED, "fontSize": "13px",
                   "marginBottom": "20px"
}
        ),
        html.Div(cards)
    ])
 
 
def page_disease_profiles():
    """
    Builds the disease profiles page explaining the condition multipliers
    used in the scoring algorithm.
    """
    profile_cards = []
    for profile in CONDITION_PROFILES:
        rows = []
        for nutrient_name, effect_text, effect_color in profile["multipliers"]:
            rows.append(html.Div([
                html.Span(nutrient_name, style={
                    "fontSize": "13px", "fontWeight": "bold",
                    "flex": "1",
 "color": C_TEXT
                }),
                html.Span(effect_text, style={
                    "fontSize": "11px",
                    "color": "white",
                    "backgroundColor": effect_color,
                    "borderRadius": "12px",
                    "padding": "2px 10px"
                })
            ], style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "padding": "7px 0",
                "borderBottom": f"1px solid {C_BORDER}"
            }))
 
        profile_cards.append(html.Div([
            html.H5(profile["name"], style={
                "fontWeight": "bold", "marginBottom": "3px",
 "color": C_TEXT
            }),
            html.P(profile["description"], style={
                "color": C_MUTED, "fontSize": "12px",
                "marginBottom": "10px"
            }),
            html.Div(rows)
        ], style=CARD_STYLE))
 
    return html.Div([
        html.H4("Disease profiles", style={
            "fontWeight": "bold", "marginBottom": "6px",
 "color": C_TEXT
        }),
        html.P(
            "How each condition changes the scoring weights. "
            "Based on NNR 2023 and Institutionskost 2025.",
            style={"color": C_MUTED, "fontSize": "13px",
                   "marginBottom": "20px"
}
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
        html.H4(title, style={
            "fontWeight": "bold", "marginBottom": "8px",
 "color": C_TEXT
        }),
        html.Div([
            html.P("🚧", style={"fontSize": "44px", "margin": "0 0 12px 0"}),
            html.P(message, style={
                "color": C_MUTED, "fontSize": "14px"
            })
        ], style={**CARD_STYLE, "textAlign": "center", "padding": "56px 20px"})
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
    patient_options = [
        {"label": f"{p['name']} (#{p['id']})", "value": p["id"]}
        for p in PATIENTS
    ]
 
    # Build dropdown options from the meals list
    meal_options = [
        {"label": k, "value": k} for k in SAMPLE_MEALS.keys()
    ]
 
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Score a meal", style={
 "color": C_TEXT
        })),
        dbc.ModalBody([
            html.P(
                "Pick a patient and a menu day. The system will run the scoring algorithm "
                "and show you a grade preview before you confirm.",
                style={"color": C_MUTED, "marginBottom": "18px",
                       "fontSize": "13px"
}
            ),
            html.Label("Patient", style={
                "fontWeight": "bold", "marginBottom": "5px"
            }),
            dcc.Dropdown(
                id="modal-patient-select",
                options=patient_options,
                placeholder="Choose a patient...",
                style={"marginBottom": "14px"
}
            ),
            html.Label("Menu day", style={
                "fontWeight": "bold", "marginBottom": "5px"
            }),
            dcc.Dropdown(
                id="modal-meal-select",
                options=meal_options,
                placeholder="Choose a day...",
                style={"marginBottom": "14px"
}
            ),
            html.Div(id="modal-preview", style={"marginTop": "14px"})
        ]),
        dbc.ModalFooter([
            html.Button("Cancel", id="modal-cancel", style={
                "backgroundColor": "white",
                "border": f"1px solid {C_BORDER}",
                "borderRadius": "6px",
                "padding": "7px 18px",
                "marginRight": "8px",
                "cursor": "pointer"
            }),
            html.Button("Score this meal →", id="modal-score", style={
                "backgroundColor": C_ACCENT,
                "border": "none",
                "borderRadius": "6px",
                "padding": "7px 18px",
                "color": "white",
                "cursor": "pointer",
                "fontWeight": "bold"
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
    dcc.Store(id="last-api-score",      data=None), 

 
    # Sidebar (always visible on the left)
    make_sidebar(),
 
    # Modal popup (hidden by default, shown when + ADD Meal is clicked)
    make_add_meal_modal(),
 
    # Main content area
    html.Div([
 
        # Top bar with title and buttons
        html.Div([
            html.H3("Patient Nutrition Dashboard", id="page-title", style={
                "margin": "0", "fontWeight": "bold",
                "color": C_TEXT,
                "fontSize": "20px"
            }),
            html.Div([
                html.Button("📄 Export PDF", id="export-pdf-btn", style={
                    "backgroundColor": "white",
                    "border": f"1px solid {C_BORDER}",
                    "borderRadius": "6px",
                    "padding": "7px 14px",
                    "marginRight": "10px",
                    "cursor": "pointer",
                    "fontWeight": "bold",
                    "fontSize": "12px",
                    "color": C_TEXT
                }),
                html.Button("+ Add meal", id="open-modal-btn", style={
                    "backgroundColor": C_ACCENT,
                    "border": "none",
                    "borderRadius": "6px",
                    "padding": "7px 14px",
                    "color": "white",
                    "cursor": "pointer",
                    "fontWeight": "bold",
                    "fontSize": "12px"
                })
            ])
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "22px",
            "paddingBottom": "14px",
            "borderBottom": f"1px solid {C_BORDER}"
        }),
 
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
    Output("page-title",   "children"),
    Input("current-page",        "data"),
    Input("selected-patient-id", "data"),
    Input("selected-meal-key",   "data"),
    Input("last-api-score",      "data"), 
)

def render_page(page, patient_id, meal_key, api_score):
    # Find the patient object that matches the selected id
    selected_patient = next(
        (p for p in PATIENTS if p["id"] == patient_id), PATIENTS[0]
    )
 
    # Map page names to their display titles
    page_titles = {
        "dashboard":        "Patient Nutrition Dashboard",
        "patients":         "Patients",
        "meal-plans":       "Meal Plans",
        "nutritional-gaps": "Nutritional Gaps",
        "frida-foods":      "Frida Foods",
        "disease-profiles": "Disease Profiles",
        "data-sources":     "Data Sources",
        "settings":         "Settings"
    }
    title = page_titles.get(page, "NutriScan")
 
    page_map = {
        "dashboard":        lambda: page_dashboard(selected_patient, meal_key, api_score),
        "patients":         page_patients,
        "disease-profiles": page_disease_profiles,
        "data-sources":     page_data_sources,
        "nutritional-gaps": lambda: page_placeholder("Nutritional Gaps", "Coming soon — will show weekly nutrient gaps across all patients."),
        "frida-foods":      lambda: page_placeholder("Frida Foods", "Coming soon — browse the Frida 5.5 food database."),
        "settings":         lambda: page_placeholder("Settings", "Reserved for future configuration options."),
        "meal-plans":       lambda: page_placeholder("Meal Plans", "Coming soon — full meal plan history for each patient.")
    }
 
    content_fn = page_map.get(page, lambda: page_dashboard(selected_patient, meal_key))
    return content_fn(), title
 
 
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
    triggered = ctx.triggered_id
    return triggered.replace("nav-", "") if triggered else "dashboard"
 
 
# --- Callback 3: Open/close modal and score the meal ---
# This handles three different buttons: open, cancel, and score.
# ctx.triggered_id tells us which button was clicked.
@app.callback(
    Output("add-meal-modal",     "is_open"),
    Output("selected-patient-id","data"),
    Output("selected-meal-key",  "data"),
    Output("current-page",       "data", allow_duplicate=True),
    Output("last-api-score",     "data"),
    Input("open-modal-btn",  "n_clicks"),
    Input("modal-cancel",    "n_clicks"),
    Input("modal-score",     "n_clicks"),
    State("modal-patient-select", "value"),
    State("modal-meal-select",    "value"),
    State("add-meal-modal",       "is_open"),
    State("selected-patient-id",  "data"),
    State("selected-meal-key",    "data"),
    prevent_initial_call=True
)
def handle_modal(open_click, cancel_click, score_click,
                 selected_patient, selected_meal,
                 is_open, current_patient, current_meal):

    triggered = ctx.triggered_id

    if triggered == "open-modal-btn":
        return True, current_patient, current_meal, "dashboard", None

    if triggered == "modal-cancel":
        return False, current_patient, current_meal, "dashboard", None

    if triggered == "modal-score":
        new_patient = selected_patient or current_patient
        new_meal    = selected_meal    or current_meal

        # Fetch the real score from the API to display on the main dashboard
        if selected_patient and selected_meal:
            patient_obj = next((p for p in PATIENTS if p["id"] == new_patient), None)
            if patient_obj:
                conditions = patient_obj["conditions"]["primary"] + patient_obj["conditions"]["risk"]
                pdf_map = {
                    "March 2026": "sample_data/menuplan-marts-2026.pdf",
                    "April 2026": "sample_data/menuplan-april-2026.pdf",
                }
                period   = new_meal.split(" - ")[0]
                pdf_path = pdf_map.get(period, "sample_data/menuplan-marts-2026.pdf")
                try:
                    day_number = int(new_meal.split("Day")[-1].strip())
                except (ValueError, IndexError):
                    day_number = 1

                api_result = api_score_meal(pdf_path, day_number, conditions, new_patient)
                return False, new_patient, new_meal, "dashboard", api_result

        return False, new_patient, new_meal, "dashboard", None

    return is_open, current_patient, current_meal, "dashboard", None
 
 
# --- Callback 4: Live preview in the modal ---
# This runs whenever the patient or meal dropdown changes in the modal.
# It shows a preview of the grade before the user confirms.
@app.callback(
    Output("modal-preview", "children"),
    Input("modal-patient-select", "value"),
    Input("modal-meal-select",    "value"),
)
def update_modal_preview(patient_id, meal_key):
    if not patient_id or not meal_key:
        return html.P(
            "Select a patient and a meal day to see a grade preview.",
            style={"color": "#aaa", "fontSize": "12px"
}
        )
 
    selected_patient = next((p for p in PATIENTS if p["id"] == patient_id), None)
    meal      = SAMPLE_MEALS.get(meal_key)
    nutrients = MEAL_NUTRIENTS.get(meal_key, {})
 
    if not selected_patient or not meal:
        return None
 
    all_conditions = selected_patient["conditions"]["primary"] + selected_patient["conditions"]["risk"]
 
    # Try the API first for a real pipeline score; fall back to local scoring.
    # Work out which PDF and day number to use based on the selected meal key
    pdf_map = {
        "March 2026": "sample_data/menuplan-marts-2026.pdf",
        "April 2026": "sample_data/menuplan-april-2026.pdf",
    }
    period = meal_key.split(" - ")[0]
    pdf_path = pdf_map.get(period, "sample_data/menuplan-marts-2026.pdf")

    try:
        day_number = int(meal_key.split("Day")[-1].strip())
    except (ValueError, IndexError):
        day_number = 1

    api_result = api_score_meal(
        pdf_path=pdf_path,
        day_number=day_number,
        conditions=all_conditions,
        patient_id=patient_id,
    )

    if api_result:
        grade             = api_result["grade"]
        grade_description = api_result["grade_description"]
        source_label      = "Live score via API"
        source_color      = C_GREEN
    else:
        grade, grade_description = calculate_grade(nutrients, all_conditions)
        source_label = "Local score (API offline)"
        source_color = C_ORANGE
 
    grade_color = GRADE_COLORS.get(grade, "#888")
 
    return html.Div([
        html.Hr(style={"borderColor": C_BORDER}),
        html.P("PREVIEW", style={
            "fontWeight": "bold", "color": C_MUTED,
            "fontSize": "10px", "letterSpacing": "1.5px"
        }),
        html.Div([
            html.Div([
                html.P(f"Patient: {selected_patient['name']}",
                       style={"margin": "0", "fontWeight": "bold",
 "color": C_TEXT}),
                html.P(f"Meal: {meal['main']['name']} + {meal['dessert']['name']}",
                       style={"margin": "0", "color": C_MUTED,
                              "fontSize": "12px"
}),
                html.P(f"Conditions: {', '.join(all_conditions) if all_conditions else 'None'}",
                       style={"margin": "0", "color": C_MUTED, "fontSize": "12px"}),
                html.P(source_label, style={
                    "margin": "4px 0 0 0", "fontSize": "10px",
                    "color": source_color, "fontWeight": "bold"
                })
            ], style={"flex": "1"}),
            html.Div([
                html.Span(grade, style={
                    "fontSize": "48px",
                    "fontWeight": "bold",
                    "color": grade_color,
                    "lineHeight": "1"
                }),
                html.P(grade_description, style={
                    "fontSize": "11px", "color": grade_color,
                    "fontWeight": "bold", "margin": "0"
                })
            ], style={"textAlign": "center"})
        ], style={
            "display": "flex",
            "alignItems": "center",
            "backgroundColor": "#f7f5f2",
            "borderRadius": "8px",
            "padding": "12px"
        })
    ])
 
 
# =============================================================================
# RUN
# This block only runs when you execute this file directly.
# =============================================================================
if __name__ == "__main__":
    print("Starting NutriScan...")
    print("Open http://127.0.0.1:8050 in your browser")
    app.run(debug=True)
