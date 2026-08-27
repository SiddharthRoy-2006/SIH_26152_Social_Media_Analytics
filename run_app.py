"""
run_app.py — SocialIQ Analytics One-Click Starter (SIH 26152)

Starts the FastAPI backend on port 8001 and serves the frontend on port 5500.
Automatically detects and uses the local virtual environment (.venv) if available.

Usage:
    python run_app.py
"""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8001
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5500


def get_python_executable() -> str:
    """Find the best Python executable, preferring the project's .venv."""
    # Check for Windows venv
    win_venv = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if win_venv.exists():
        return str(win_venv)

    # Check for POSIX venv
    posix_venv = ROOT_DIR / ".venv" / "bin" / "python"
    if posix_venv.exists():
        return str(posix_venv)

    return sys.executable


def is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is currently accepting TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def check_backend_health(timeout: float = 0.8) -> bool:
    """Ping the backend /health endpoint."""
    url = f"http://{BACKEND_HOST}:{BACKEND_PORT}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SocialIQ-Starter/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = resp.read()
                data = json.loads(body.decode("utf-8"))
                return data.get("status") == "ok"
    except Exception:
        return False
    return False


def main():
    print("=" * 64)
    print("  SocialIQ Analytics — Full-Stack Platform Starter (SIH 26152)")
    print("=" * 64)

    # Ensure live data mode by default if not set (with explicit demo fallback available)
    os.environ.setdefault("SOCIALIQ_DATA_MODE", "live")

    py_exe = get_python_executable()
    print(f"[*] Python interpreter : {py_exe}")

    backend_proc = None
    frontend_proc = None

    # --- 1. Launch / Verify Backend ---
    if check_backend_health():
        print(f"[1/3] Backend is already running and healthy on http://{BACKEND_HOST}:{BACKEND_PORT}")
    else:
        if is_port_in_use(BACKEND_HOST, BACKEND_PORT):
            print(f"[!] Warning: Port {BACKEND_PORT} is in use by another process, attempting connection...")
        else:
            print(f"[1/3] Launching FastAPI Backend on http://{BACKEND_HOST}:{BACKEND_PORT} ...")
            backend_cmd = [
                py_exe, "-m", "uvicorn", "backend.app:app",
                "--port", str(BACKEND_PORT),
                "--host", BACKEND_HOST,
            ]
            backend_proc = subprocess.Popen(backend_cmd, cwd=str(ROOT_DIR))

        # Active polling for backend health
        print("    Waiting for backend to become ready...", end="", flush=True)
        ready = False
        for _ in range(25):  # up to 10 seconds
            if backend_proc and backend_proc.poll() is not None:
                print(" FAILED.")
                print(f"[ERROR] Backend process terminated unexpectedly with exit code {backend_proc.returncode}.")
                print("       Please check if dependencies are installed: pip install -r requirements.txt")
                sys.exit(1)
            if check_backend_health():
                ready = True
                print(" OK.")
                break
            time.sleep(0.4)
            print(".", end="", flush=True)

        if not ready:
            print(" TIMEOUT.")
            print(f"[ERROR] Could not connect to backend /health at http://{BACKEND_HOST}:{BACKEND_PORT}/health.")
            if backend_proc:
                backend_proc.terminate()
            sys.exit(1)

    # --- 2. Launch / Verify Frontend ---
    if is_port_in_use(FRONTEND_HOST, FRONTEND_PORT):
        print(f"[2/3] Frontend server is already active on http://{FRONTEND_HOST}:{FRONTEND_PORT}")
    else:
        print(f"[2/3] Launching Frontend Server on http://{FRONTEND_HOST}:{FRONTEND_PORT} ...")
        frontend_cmd = [
            py_exe, "-m", "http.server", str(FRONTEND_PORT),
            "--directory", str(FRONTEND_DIR),
            "--bind", FRONTEND_HOST,
        ]
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(ROOT_DIR))
        time.sleep(0.5)

    # --- 3. Ready Banner & Browser Launch ---
    app_url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"
    api_url = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
    docs_url = f"http://{BACKEND_HOST}:{BACKEND_PORT}/docs"

    print("-" * 64)
    print("  [SUCCESS] All SocialIQ services are live!")
    print(f"  -> Frontend UI : {app_url}")
    print(f"  -> Backend API : {api_url}")
    print(f"  -> API Docs    : {docs_url}")
    print("-" * 64)
    print("Press Ctrl+C in this terminal to stop all running services cleanly.\n")

    try:
        webbrowser.open(app_url)
    except Exception:
        pass

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping SocialIQ services...")
        if backend_proc:
            backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()
        print("All services stopped cleanly.")


if __name__ == "__main__":
    main()

