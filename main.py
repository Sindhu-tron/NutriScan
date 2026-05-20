# main.py
# Entry point for the NutriScan system.
# Starts both the FastAPI backend and the Dash frontend together
# so the whole system runs with one command from the project root:
#
#     python main.py
#
# Always run with the venv Python:
#     .venv/bin/python main.py
#
# Open http://127.0.0.1:8050 in your browser.

import subprocess
import sys
import time
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    print("=" * 50)
    print("  NutriScan — RUC Computer Science Project 2026")
    print("=" * 50)
    print()

    # Kill anything already on port 8000 so we get a clean start
    subprocess.call("lsof -ti :8000 | xargs kill -9 2>/dev/null || true", shell=True)

    # Use the venv Python explicitly to avoid picking up system anaconda
    venv_python = Path(sys.executable).parent / "python"
    if not venv_python.exists():
        venv_python = Path(sys.executable)

    # Start the FastAPI backend on port 8000
    print("Starting API server on http://127.0.0.1:8000 ...")
    api_process = subprocess.Popen(
        [str(venv_python), "-m", "uvicorn", "api.main:app", "--port", "8000"],
        cwd=PROJECT_ROOT,
    )

    # Give the API a moment to start before the dashboard tries to connect
    time.sleep(2)

    # Build the environment for the dashboard subprocess
    # NUTRISCAN_NO_DEBUG=1 tells dashboard.py to run with debug=False
    # so Werkzeug doesn't try to attach to a terminal that doesn't exist
    env = os.environ.copy()
    env["NUTRISCAN_NO_DEBUG"] = "1"

    # Start the Dash frontend on port 8050
    print("Starting dashboard on http://127.0.0.1:8050 ...")
    dashboard_process = subprocess.Popen(
        [str(venv_python), "frontend/dashboard.py"],
        cwd=PROJECT_ROOT,
        env=env,
    )

    print()
    print("Both servers are running.")
    print("Open http://127.0.0.1:8050 in your browser.")
    print("Press Ctrl+C to stop.")
    print()

    # Keep running until the user presses Ctrl+C
    try:
        api_process.wait()
    except KeyboardInterrupt:
        print()
        print("Shutting down...")
        api_process.terminate()
        dashboard_process.terminate()
        api_process.wait()
        dashboard_process.wait()
        print("Done.")


if __name__ == "__main__":
    main()

# If Port 8050 is already in use
# kill -9 $(lsof -ti :8000) 2>/dev/null
# kill -9 $(lsof -ti :8050) 2>/dev/null
# sleep 2
# .venv/bin/python main.py

# Run all tests (should see 50 passed)
# cd Computer-Science-Project-Repository
#  python -m pytest tests/ -v