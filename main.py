"""
main.py
-------
Entry point for the NutriScan system. Starts both the FastAPI backend and the Dash frontend together 
so the whole system runs with one command:

    python main.py

Requirements:
    - Run from the project root directory
    - Use the venv Python: .venv/bin/python main.py

Once running, open http://127.0.0.1:8050 in your browser.
Press Ctrl+C to stop both servers.

------------------------------------------------------------------------
TROUBLESHOOTING
------------------------------------------------------------------------

If ports are already in use, free them first then re-run:

    kill -9 $(lsof -ti :8000) 2>/dev/null
    kill -9 $(lsof -ti :8050) 2>/dev/null
    sleep 2
    .venv/bin/python main.py

------------------------------------------------------------------------
RUNNING TESTS
------------------------------------------------------------------------

Run all unit tests from the project root (should see 50 passed):

    python -m pytest tests/ -v

------------------------------------------------------------------------
"""

import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _free_port(port: int) -> None:
    """Kill any process already listening on the given port."""
    subprocess.call(
        f"lsof -ti :{port} | xargs kill -9 2>/dev/null || true",
        shell=True
    )


def _resolve_python() -> Path:
    """
    Return the venv Python executable.
    Falls back to sys.executable if the venv sibling binary is not found.
    """
    venv_python = Path(sys.executable).parent / "python"
    return venv_python if venv_python.exists() else Path(sys.executable)


def main() -> None:
    print("=" * 50)
    print("  NutriScan — RUC Computer Science Project 2026")
    print("=" * 50)
    print()

    # Clear ports so we always get a clean start
    _free_port(8000)

    python = _resolve_python()

    # Start the FastAPI backend
    print("Starting API server on http://127.0.0.1:8000 ...")
    api_process = subprocess.Popen(
        [str(python), "-m", "uvicorn", "api.main:app", "--port", "8000"],
        cwd=PROJECT_ROOT,
    )

    # Give the API time to initialise before the dashboard connects
    time.sleep(2)

    # NUTRISCAN_NO_DEBUG=1 tells dashboard.py to run with debug=False
    # so Werkzeug does not try to attach a reloader to a non-interactive process
    env = os.environ.copy()
    env["NUTRISCAN_NO_DEBUG"] = "1"

    # Start the Dash frontend
    print("Starting dashboard on http://127.0.0.1:8050 ...")
    dashboard_process = subprocess.Popen(
        [str(python), "frontend/dashboard.py"],
        cwd=PROJECT_ROOT,
        env=env,
    )

    print()
    print("Both servers are running.")
    print("Open http://127.0.0.1:8050 in your browser.")
    print("Press Ctrl+C to stop.")
    print()

    try:
        api_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        api_process.terminate()
        dashboard_process.terminate()
        api_process.wait()
        dashboard_process.wait()
        print("Done.")


if __name__ == "__main__":
    main()