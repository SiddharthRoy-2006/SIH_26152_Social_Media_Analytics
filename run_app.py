"""
run_app.py — SocialIQ Analytics One-Click Starter (SIH 26152)

Starts the FastAPI backend on port 8001 and serves the frontend on port 5500.
Usage:
    python run_app.py
"""

import os
import subprocess
import sys
import time
import webbrowser

def main():
    print("=" * 60)
    print("  SocialIQ Analytics — Starting Full-Stack Platform (SIH 26152)")
    print("=" * 60)

    # Set demo data mode by default if not set
    os.environ.setdefault("SOCIALIQ_DATA_MODE", "demo")

    backend_cmd = [
        sys.executable, "-m", "uvicorn", "backend.app:app",
        "--port", "8001",
        "--host", "127.0.0.1",
    ]

    frontend_cmd = [
        sys.executable, "-m", "http.server", "5500",
        "--directory", "frontend",
        "--bind", "127.0.0.1",
    ]

    print("[1/3] Launching FastAPI Backend on http://127.0.0.1:8001 ...")
    backend_proc = subprocess.Popen(backend_cmd)

    print("[2/3] Launching Frontend Server on http://127.0.0.1:5500 ...")
    frontend_proc = subprocess.Popen(frontend_cmd)

    time.sleep(1.5)

    print("[3/3] Ready!")
    print("  Frontend UI : http://127.0.0.1:5500")
    print("  Backend API : http://127.0.0.1:8001")
    print("  API Docs    : http://127.0.0.1:8001/docs")
    print("\nPress Ctrl+C in this terminal to stop both servers cleanly.\n")

    try:
        webbrowser.open("http://127.0.0.1:5500")
    except Exception:
        pass

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping SocialIQ services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Done.")

if __name__ == "__main__":
    main()
