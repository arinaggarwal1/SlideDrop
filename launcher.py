#!/usr/bin/env python3
"""
Desktop launcher for packaged mode.
Starts FastAPI in-process and opens the UI in a native pywebview window.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

APP_NAME = os.environ.get("SLIDEDROP_APP_NAME", "SlideDrop")
APP_MODE_ENV = "SLIDEDROP_APP_MODE"
APP_HOST = "127.0.0.1"


def _get_log_dir() -> Path:
    """Use the conventional per-user log directory on each desktop OS."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / APP_NAME / "Logs"
    return Path.home() / "Library" / "Logs" / APP_NAME


LOG_DIR = _get_log_dir()
ERROR_LOG_PATH = LOG_DIR / "error.log"


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_message(message: str) -> None:
    _ensure_log_dir()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with ERROR_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")
    print(message, file=sys.stderr, flush=True)


def log_exception(context: str) -> None:
    _ensure_log_dir()
    formatted = traceback.format_exc().rstrip()
    with ERROR_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}\n{formatted}\n")
    print(f"{context}\n{formatted}", file=sys.stderr, flush=True)


def get_base_path() -> str:
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))


base_path = get_base_path()
frontend_path = os.path.join(base_path, "frontend_dist", "index.html")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((APP_HOST, 0))
        return sock.getsockname()[1]


def wait_for_server(backend: "EmbeddedBackend", timeout: float = 20.0) -> bool:
    url = f"http://{APP_HOST}:{backend.port}/health"
    start = time.time()
    while time.time() - start < timeout:
        if backend.error is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


class EmbeddedBackend:
    """Manage an in-process uvicorn server in a background thread."""

    def __init__(self, port: int):
        self.port = port
        self.error: Exception | None = None
        self._server = None
        self._thread = threading.Thread(
            target=self._run,
            name="slidedrop-fastapi",
            daemon=True,
        )

    def _run(self) -> None:
        try:
            import uvicorn
            from main import app as fastapi_app

            config = uvicorn.Config(
                fastapi_app,
                host=APP_HOST,
                port=self.port,
                log_level="info",
                lifespan="on",
            )
            self._server = uvicorn.Server(config)
            self._server.install_signal_handlers = lambda: None
            self._server.run()
        except Exception as exc:
            self.error = exc
            log_exception("Backend startup failed")

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 8.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=timeout)


def configure_runtime() -> None:
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    backend_path = os.path.join(base_path, "backend")
    if os.path.isdir(backend_path) and backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    preferred_path_entries: list[str] = []
    if sys.platform == "darwin":
        preferred_path_entries = [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/opt/homebrew/opt/poppler/bin",
            "/usr/local/bin",
            "/usr/local/sbin",
            "/usr/local/opt/poppler/bin",
        ]
    elif sys.platform == "win32":
        for environment_name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            base = os.environ.get(environment_name)
            if base:
                preferred_path_entries.append(str(Path(base) / "LibreOffice" / "program"))
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            preferred_path_entries.append(str(Path(local_app_data) / "Programs" / "Ollama"))
    current_path = os.environ.get("PATH", "")
    path_parts = [part for part in current_path.split(os.pathsep) if part]
    for entry in reversed(preferred_path_entries):
        if os.path.isdir(entry) and entry not in path_parts:
            path_parts.insert(0, entry)
    os.environ["PATH"] = os.pathsep.join(path_parts)

    os.environ.setdefault(APP_MODE_ENV, "production")


def _error_window_html(message: str) -> str:
    escaped = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<html><body style='font-family:-apple-system,Segoe UI,Arial,sans-serif;padding:28px;'>"
        f"<h2>{APP_NAME} failed to start</h2>"
        f"<p><strong>Error log:</strong> <code>{ERROR_LOG_PATH}</code></p>"
        f"<pre style='white-space:pre-wrap;background:#f6f6f6;padding:16px;border-radius:12px;'>{escaped}</pre>"
        "</body></html>"
    )


def main() -> None:
    try:
        configure_runtime()

        import webview

        port = find_free_port()
        api_base = f"http://{APP_HOST}:{port}"
        backend = EmbeddedBackend(port)
        backend.start()

        if not wait_for_server(backend):
            if backend.error is not None:
                raise RuntimeError(str(backend.error)) from backend.error
            raise RuntimeError(f"Backend did not become ready at {api_base}/health")

        if not os.path.exists(frontend_path):
            raise FileNotFoundError(f"Bundled frontend not found: {frontend_path}")

        window = webview.create_window(
            APP_NAME,
            api_base,
            width=1100,
            height=750,
            min_size=(800, 550),
        )
        window.events.closed += lambda: backend.stop()

        try:
            webview.start(debug=False)
        finally:
            backend.stop()
    except Exception as exc:
        log_exception("Application startup failed")
        try:
            import webview

            window = webview.create_window(
                APP_NAME,
                html=_error_window_html(str(exc)),
                width=760,
                height=460,
                min_size=(640, 360),
            )
            webview.start(debug=False)
        except Exception:
            log_exception("Unable to show startup error window")
            raise


if __name__ == "__main__":
    main()
