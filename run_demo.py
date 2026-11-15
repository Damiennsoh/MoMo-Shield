"""MoMo Shield — one-command demo launcher.

Starts the FastAPI fraud engine (backend_part2) and the Streamlit
FraudOps dashboard (frontend_part1), waits for the engine to come up,
then opens the dashboard in the browser.

Run:  python run_demo.py        (or double-click start_demo.bat)
Stop: Ctrl+C
"""

import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend_part2"
FRONTEND_DIR = ROOT / "frontend_part1"

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:8501"


def wait_for_health(url: str, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + "/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> None:
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=BACKEND_DIR,
    )

    if not wait_for_health(BACKEND_URL):
        print(f"[!] Backend did not respond at {BACKEND_URL}/health — "
              "the dashboard will use its offline fallback engine.")
    else:
        print(f"[ok] Fraud engine up at {BACKEND_URL}")

    frontend = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", "8501", "--server.headless", "true"],
        cwd=FRONTEND_DIR,
    )

    time.sleep(2)
    webbrowser.open(FRONTEND_URL)
    print(f"[ok] FraudOps dashboard at {FRONTEND_URL}")
    print("Running — press Ctrl+C to stop both services.\n")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (backend, frontend):
            if proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    main()
