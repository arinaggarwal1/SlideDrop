#!/usr/bin/env python3
"""
SlideDrop — Launch script.
Starts the backend (FastAPI) and frontend (Next.js) servers.
Opens http://localhost:3000 in the default browser.
"""

import os
import sys
import time
import signal
import subprocess
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

processes: list[subprocess.Popen] = []


def cleanup(signum=None, frame=None):
    """Terminate all child processes."""
    print("\n🛑 Shutting down SlideDrop...")
    for proc in processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    sys.exit(0)


def check_prerequisites():
    """Verify that required tools are available."""
    # Check Python packages
    try:
        import fastapi  # noqa: F401
        import pdf2image  # noqa: F401
    except ImportError:
        print("📦 Installing backend dependencies...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt")],
            check=True,
        )

    # Check if node_modules exists for frontend
    if not (FRONTEND_DIR / "node_modules").exists():
        print("📦 Installing frontend dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(FRONTEND_DIR),
            check=True,
        )


def main():
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=" * 50)
    print("  🖼️  SlideDrop — Slide-to-Image Converter")
    print("=" * 50)
    print()

    check_prerequisites()

    # Start backend
    print("🚀 Starting backend server (port 8000)...")
    backend_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
        ],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    processes.append(backend_proc)

    # Start frontend
    print("🚀 Starting frontend server (port 3000)...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(FRONTEND_DIR),
    )
    processes.append(frontend_proc)

    # Wait a moment before opening browser
    time.sleep(3)

    url = "http://localhost:3000"
    print()
    print(f"✅ SlideDrop is running at: {url}")
    print("   Press Ctrl+C to stop.")
    print()

    webbrowser.open(url)

    # Wait for processes to finish
    try:
        while True:
            # Check if either process has exited
            if backend_proc.poll() is not None:
                print("⚠️  Backend server stopped unexpectedly.")
                cleanup()
            if frontend_proc.poll() is not None:
                print("⚠️  Frontend server stopped unexpectedly.")
                cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
