# main.py
# Entry point for the NutriScan system.
# Starts both the FastAPI backend and the Dash frontend together so the whole system runs with one command from the project root:
#
# run: python main.py
#
# Terminal output will confirm both servers are running.
# Open http://127.0.0.1:8050 in your browser.

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def main():
    print("=" * 50)
    print("  NutriScan — RUC Computer Science Project 2026")
    print("=" * 50)
    print()

    # Start the FastAPI backend on port 8000
    print("Starting API server on http://127.0.0.1:8000 ...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--port", "8000"],
        cwd=PROJECT_ROOT,
    )

    # Give the API a moment to start before the dashboard tries to connect
    time.sleep(2)

    # Start the Dash frontend on port 8050
    print("Starting dashboard on http://127.0.0.1:8050 ...")
    dashboard_process = subprocess.Popen(
        [sys.executable, "frontend/dashboard.py"],
        cwd=PROJECT_ROOT,
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