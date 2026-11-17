"""MoMo Shield — one-command demo launcher.

Starts the FastAPI fraud engine (backend) and the Streamlit
FraudOps dashboard (frontend), waits for the engine to come up,
then opens the dashboard in the browser.

Run:  python run_demo.py        (or double-click start_demo.bat)
Stop: Ctrl+C
"""

import subprocess
import os
import secrets
import socket
import sys
import time
import urllib.request
import webbrowser
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

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


def lan_ip() -> str:
    """Best-effort local interface address for a phone on the same Wi-Fi."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        address = sock.getsockname()[0]
        return address if not address.startswith("127.") else "127.0.0.1"
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> None:
    child_env = os.environ.copy()
    device_token = child_env.get("DEMO_DEVICE_TOKEN") or secrets.token_urlsafe(32)
    child_env["DEMO_DEVICE_TOKEN"] = device_token
    child_env.setdefault(
        "DEMO_DEVICE_URL",
        f"http://{lan_ip()}:8000/api/v1/demo-device#token={quote(device_token, safe='')}"
    )
    child_env.setdefault("BACKEND_API_URL", BACKEND_URL)

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=BACKEND_DIR,
        env=child_env,
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
        env=child_env,
    )

    time.sleep(2)
    webbrowser.open(FRONTEND_URL)
    print(f"[ok] FraudOps dashboard at {FRONTEND_URL}")
    print(f"[ok] Second-device handset is available from the dashboard link on {lan_ip()}:8000")
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
