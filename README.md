# Computer-Science-Project-Repository
# NutriScan — Nutritional Monitoring for Danish Nursing Homes

This is a Computer science subject module project within the spring 2026 semester at Roskilde University. 

**Authors:** Sindhuja Varma Dantuluri, Ayperi Akkas, Anne Margaret Lorenzen, Jalte Dan Eliasen, Alisha Noor Ahmed

NutriScan is a modular Python system that automatically scores weekly nursing home menus against Danish nutritional guidelines, personalised to each resident's health conditions. A meal PDF is parsed, ingredients are matched to the Frida 5.5 food composition database, and each meal is given a letter grade (A–E) based on NNR 2023 and *Institutionskost 2025* reference values.

---

## Features

- Parses real nursing home menu PDFs (normal and pescetarian diet)
- Fuzzy ingredient matching against 1,600+ entries in Frida 5.5
- Condition-specific scoring for hypertension, Type 2 diabetes, osteoporosis, and sarcopenia
- Letter grade A–E per meal and per patient
- Weekly nutritional summary view
- Web dashboard (Plotly Dash) served via FastAPI backend
- SQLite database for persistent patient profiles and meal history
- 50 unit tests across all pipeline modules

---

## Project Structure

```
├── pipeline/
│   ├── menu_parser.py        # Extracts dish names from PDF columns
│   ├── pdf_extractor.py      # Decomposes dishes into ingredients + gram weights
│   ├── frida_matcher.py      # Fuzzy matches ingredients to Frida 5.5
│   ├── nutrient_lookup.py    # Looks up nutrient values from Frida dataset
│   ├── scoring.py            # ElderScore algorithm — produces A–E grade
│   └── build_db.py           # Builds SQLite database from pipeline output
├── api/
│   └── main.py               # FastAPI backend
├── frontend/
│   └── dashboard.py          # Plotly Dash web dashboard
├── tests/                    # 50 pytest unit tests
├── data/
│   └── Frida_5.5_Dataset.xlsx
├── sample_data/              # Sample menu PDFs (Roskilde municipality)
├── main.py                   # Entry point
└── requirements.txt
```

---

## Setup

**Requirements:** Python 3.9+

```bash
git clone https://github.com/your-org/Computer-Science-Project-Repository.git
cd Computer-Science-Project-Repository
pip install -r requirements.txt
```

Place `Frida_5.5_Dataset.xlsx` in the `data/` folder if not already present.

---

## Usage

**1. Build the database from a menu PDF:**
```bash
python main.py --pdf sample_data/menuplan-marts-2026.pdf
```

**2. Start the API:**
```bash
uvicorn api.main:app --reload
```

**3. Start the dashboard** (in a separate terminal):
```bash
python frontend/dashboard.py
```

Then open `http://localhost:8050` in your browser.

---

## Running Tests

```bash
pytest tests/
```

All 50 tests should pass. To see line count:
```bash
find . -name "*.py" | grep -v .venv | grep -v __pycache__ | xargs wc -l
```
Total: ~5,200 lines across pipeline, API, dashboard, and tests.

---

## Data

Patient profiles used in this project are **fully synthetic** and contain no real personal data, in compliance with GDPR. Sample menu PDFs are from publicly available institutional meal planning materials.

The Frida 5.5 food composition dataset is published by DTU National Food Institute:
> Marija Langwagen et al., *The Danish Food Composition Database, Frida version 5.5*, November 2025, DTU. https://doi.org/10.11583/DTU.29500682

---

## Scientific Basis

Nutrient targets and condition multipliers in the scoring algorithm are grounded in:
- Nordic Nutrition Recommendations 2023 (NNR 2023)
- *Anbefalinger for den danske institutionskost*, 2025 edition

---

## License

This project was developed for academic purposes at Roskilde University. Not intended for clinical use.