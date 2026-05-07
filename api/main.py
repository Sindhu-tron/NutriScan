"""
main.py
-------
Responsibility:
- Expose the NutriScan pipeline as a REST API
- Sits between the Dash dashboard (presentation layer) and the pipeline + SQLite
  (logic + data layer) -- the API is the middle tier of the three-tier architecture
- Validates requests and responses with Pydantic so the contract between layers is explicit

Run the API locally:
    uvicorn api.main:app --reload

Then open the auto-generated docs in the browser:
    http://127.0.0.1:8000/docs
"""

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Make sure the pipeline package is importable when running uvicorn from the project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_FILE = PROJECT_ROOT / "nutriscan.db"


# Pydantic models
# These describe the shape of every request and response so FastAPI can validate
# inputs, generate the docs page on /docs, and so the dashboard knows exactly
# what to send and expect back.

class ScoreRequest(BaseModel):
    pdf_path: str
    day_number: int
    conditions: list[str]
    patient_id: Optional[str] = None


class WeekScoreRequest(BaseModel):
    pdf_path: str
    conditions: list[str]
    patient_id: Optional[str] = None


class MenuParseRequest(BaseModel):
    pdf_path: str


class NutrientValues(BaseModel):
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_sat_g: float = 0.0
    fiber_g: float = 0.0
    sugar_g: float = 0.0
    sodium_mg: float = 0.0
    potassium_mg: float = 0.0
    calcium_mg: float = 0.0


class MealSummary(BaseModel):
    day_number: int
    day_name: str
    main: str
    dessert: str
    sides: list[str]
    vegetarian: bool


class MealScoreResponse(BaseModel):
    day_number: int
    day_name: str
    main: str
    dessert: str
    sides: list[str]
    vegetarian: bool
    grade: str
    score: float
    grade_description: str
    flags: list[str]
    nutrients: NutrientValues
    coverage_pct: int
    unmatched: list[str]
    conditions: list[str]


class WeekSummaryResponse(BaseModel):
    weekly_grade: str
    weekly_avg_score: float
    weekly_description: str
    grade_counts: dict[str, int]
    avg_nutrients: NutrientValues
    meal_count: int
    all_flags: list[str]
    meals: list[MealScoreResponse]


class PatientCondition(BaseModel):
    primary: list[str]
    risk: list[str]
    inactive: list[str]


class PatientResponse(BaseModel):
    id: str
    name: str
    sex: str
    age: int
    location: str
    avatar: str
    conditions: PatientCondition


class HistoryEntry(BaseModel):
    meal_id: int
    grade: str
    score: float
    scored_at: str
    main: str
    period: str


# Lifespan event
# This runs once when the server starts and once when it shuts down.
# We use it to load the Frida dataset into memory so the first /score request
# is fast (otherwise every request would re-read the 12 MB Excel file).

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load Frida once and create the history table if it does not exist
    try:
        from pipeline.nutrient_lookup import load_frida_dataset
        load_frida_dataset()
    except Exception as exc:
        print(f"[startup] Warning: could not preload Frida dataset: {exc}")

    _ensure_history_table()
    yield
    # Shutdown: nothing to clean up


# Build the FastAPI app with CORS and lifespan attached
app = FastAPI(
    title="NutriScan API",
    description="REST API for the NutriScan project (Roskilde University, Spring 2026)",
    version="1.0",
    lifespan=lifespan,
)


# CORS middleware
# The Dash frontend runs on port 8050 and the API on port 8000. Without CORS
# the browser would block every cross-origin request from the dashboard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8050",
        "http://127.0.0.1:8050",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Database helpers

def _get_connection():
    """Opens a SQLite connection with row access by column name."""
    if not DB_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Database not found at {DB_FILE}. Run build_db.py first."
        )
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_history_table():
    """Creates the score_history table if it does not exist yet."""
    if not DB_FILE.exists():
        return

    connection = sqlite3.connect(DB_FILE)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS score_history (
            meal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  TEXT NOT NULL,
            main        TEXT,
            period      TEXT,
            grade       TEXT,
            score       REAL,
            scored_at   TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)
    connection.commit()
    connection.close()


# Pipeline helpers
# Wrappers around the pipeline modules. Keeping them small means the endpoints
# stay readable and we have one place to handle pipeline errors.

def _resolve_pdf_path(pdf_path: str) -> Path:
    """Resolve the given PDF path relative to the project root if it is not absolute."""
    candidate = Path(pdf_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {pdf_path}")
    return candidate


def _run_pipeline_extract(pdf_path: str):
    """Calls pdf_extractor.extract_meals() with proper error handling."""
    full_path = _resolve_pdf_path(pdf_path)

    try:
        from pipeline.pdf_extractor import extract_meals
        return extract_meals(str(full_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed while extracting meals: {exc}"
        )


def _run_menu_parse(pdf_path: str):
    """Calls menu_parser.parse_menu() with proper error handling."""
    full_path = _resolve_pdf_path(pdf_path)

    try:
        from pipeline.menu_parser import parse_menu
        return parse_menu(str(full_path))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed while parsing menu: {exc}"
        )


def _build_meal_response(meal: dict, score_result: dict, conditions: list[str]) -> dict:
    """Combines the enriched meal and the scoring result into the response shape."""
    nutrients = meal.get("nutrients", {})
    return {
        "day_number":         meal.get("day_number", 0),
        "day_name":           meal.get("day_name", ""),
        "main":               meal.get("main", ""),
        "dessert":            meal.get("dessert", ""),
        "sides":              meal.get("sides", []),
        "vegetarian":         meal.get("vegetarian", False),
        "grade":              score_result["grade"],
        "score":              score_result["score"],
        "grade_description":  score_result["grade_description"],
        "flags":              score_result["flags"],
        "nutrients": {
            "energy_kcal":  nutrients.get("energy_kcal", 0.0),
            "protein_g":    nutrients.get("protein_g", 0.0),
            "fat_sat_g":    nutrients.get("fat_sat_g", 0.0),
            "fiber_g":      nutrients.get("fiber_g", 0.0),
            "sugar_g":      nutrients.get("sugar_g", 0.0),
            "sodium_mg":    nutrients.get("sodium_mg", 0.0),
            "potassium_mg": nutrients.get("potassium_mg", 0.0),
            "calcium_mg":   nutrients.get("calcium_mg", 0.0),
        },
        "coverage_pct":  meal.get("coverage_pct", 0),
        "unmatched":     meal.get("unmatched", []),
        "conditions":    conditions,
    }


def _save_score_to_history(patient_id: str, main: str, period: str,
                           grade: str, score: float):
    """Inserts one row into the score_history table."""
    connection = _get_connection()
    connection.execute(
        """INSERT INTO score_history (patient_id, main, period, grade, score, scored_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (patient_id, main, period, grade, score, datetime.utcnow().isoformat())
    )
    connection.commit()
    connection.close()


# 1. Health endpoint

@app.get("/health")
def health():
    """
    Liveness check. Returns immediately without touching the pipeline or database.
    Used to confirm the server is running.
    """
    return {"status": "ok", "version": "1.0"}


# 2. Menu parsing endpoint

@app.post("/menu/parse", response_model=list[MealSummary])
def menu_parse(request: MenuParseRequest):
    """
    Parses a menu PDF and returns the raw meal list -- no scoring, no Frida lookup.
    Used by the "Meal Plans" page in the dashboard to browse the menu.
    """
    raw_meals = _run_menu_parse(request.pdf_path)

    return [
        {
            "day_number": meal.get("day_number", 0),
            "day_name":   meal.get("day_name", ""),
            "main":       meal.get("main", ""),
            "dessert":    meal.get("dessert", ""),
            "sides":      meal.get("sides", []),
            "vegetarian": meal.get("vegetarian", False),
        }
        for meal in raw_meals
    ]


# 3. Single-meal scoring endpoint

@app.post("/score/meal", response_model=MealScoreResponse)
def score_meal_endpoint(request: ScoreRequest):
    """
    Runs the full pipeline for one day in the menu and returns the grade,
    score, flags and nutrients for one patient's conditions.

    This replaces the hardcoded preview in the dashboard's "+ ADD Meal" modal.
    """
    meals = _run_pipeline_extract(request.pdf_path)

    # Find the requested day
    target_meal = None
    for meal in meals:
        if meal.get("day_number") == request.day_number:
            target_meal = meal
            break

    if target_meal is None:
        raise HTTPException(
            status_code=404,
            detail=f"Day {request.day_number} not found in {request.pdf_path}"
        )

    # Score the meal
    from pipeline.scoring import score_meal as score_meal_fn
    result = score_meal_fn(target_meal, request.conditions)
    response = _build_meal_response(target_meal, result, request.conditions)

    # If a patient_id was provided, record this scoring event in the history table
    if request.patient_id:
        _save_score_to_history(
            patient_id=request.patient_id,
            main=target_meal.get("main", ""),
            period=Path(request.pdf_path).stem,
            grade=result["grade"],
            score=result["score"],
        )

    return response


# 4. Weekly scoring endpoint

@app.post("/score/week", response_model=WeekSummaryResponse)
def score_week_endpoint(request: WeekScoreRequest):
    """
    Scores all meals in a PDF for one patient's conditions and returns a
    weekly summary plus the individual meal scores.
    """
    meals = _run_pipeline_extract(request.pdf_path)

    if not meals:
        raise HTTPException(
            status_code=404,
            detail=f"No meals found in {request.pdf_path}"
        )

    from pipeline.scoring import score_meal as score_meal_fn, score_week

    # Score every meal for the patient's conditions
    score_results = []
    meal_responses = []
    for meal in meals:
        result = score_meal_fn(meal, request.conditions)
        score_results.append(result)
        meal_responses.append(_build_meal_response(meal, result, request.conditions))

    weekly = score_week(score_results)

    # If a patient_id was provided, save every meal to history
    if request.patient_id:
        period = Path(request.pdf_path).stem
        for meal, result in zip(meals, score_results):
            _save_score_to_history(
                patient_id=request.patient_id,
                main=meal.get("main", ""),
                period=period,
                grade=result["grade"],
                score=result["score"],
            )

    avg_nutrients = weekly.get("avg_nutrients", {})
    return {
        "weekly_grade":       weekly.get("weekly_grade", "E"),
        "weekly_avg_score":   weekly.get("weekly_avg_score", 0.0),
        "weekly_description": weekly.get("weekly_description", ""),
        "grade_counts":       weekly.get("grade_counts", {}),
        "avg_nutrients": {
            "energy_kcal":  avg_nutrients.get("energy_kcal", 0.0),
            "protein_g":    avg_nutrients.get("protein_g", 0.0),
            "fat_sat_g":    avg_nutrients.get("fat_sat_g", 0.0),
            "fiber_g":      avg_nutrients.get("fiber_g", 0.0),
            "sugar_g":      avg_nutrients.get("sugar_g", 0.0),
            "sodium_mg":    avg_nutrients.get("sodium_mg", 0.0),
            "potassium_mg": avg_nutrients.get("potassium_mg", 0.0),
            "calcium_mg":   avg_nutrients.get("calcium_mg", 0.0),
        },
        "meal_count":  weekly.get("meal_count", 0),
        "all_flags":   weekly.get("all_flags", []),
        "meals":       meal_responses,
    }


# 5. Patients endpoint

@app.get("/patients", response_model=list[PatientResponse])
def list_patients():
    """
    Returns all patients from the SQLite database with their conditions.
    Replaces the hardcoded PATIENTS list in dashboard.py.
    """
    connection = _get_connection()

    patient_rows = connection.execute(
        "SELECT id, name, sex, age, location, avatar FROM patients ORDER BY id"
    ).fetchall()

    condition_rows = connection.execute(
        "SELECT patient_id, condition, status FROM patient_conditions"
    ).fetchall()

    connection.close()

    # Group conditions by patient_id and by status
    conditions_by_patient: dict[str, dict[str, list[str]]] = {}
    for row in condition_rows:
        bucket = conditions_by_patient.setdefault(
            row["patient_id"],
            {"primary": [], "risk": [], "inactive": []},
        )
        bucket[row["status"]].append(row["condition"])

    result = []
    for row in patient_rows:
        patient = dict(row)
        patient["conditions"] = conditions_by_patient.get(
            row["id"],
            {"primary": [], "risk": [], "inactive": []},
        )
        result.append(patient)

    return result


# 6. Patient history endpoint

@app.get("/patients/{patient_id}/history", response_model=list[HistoryEntry])
def patient_history(patient_id: str):
    """
    Returns all previously saved scores for one patient from the
    score_history table. Used by the dashboard to show grades over time.
    """
    connection = _get_connection()

    # Check the patient exists
    exists = connection.execute(
        "SELECT 1 FROM patients WHERE id = ?", (patient_id,)
    ).fetchone()
    if exists is None:
        connection.close()
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    rows = connection.execute(
        """SELECT meal_id, grade, score, scored_at, main, period
           FROM score_history WHERE patient_id = ?
           ORDER BY scored_at DESC""",
        (patient_id,),
    ).fetchall()

    connection.close()
    return [dict(row) for row in rows]
