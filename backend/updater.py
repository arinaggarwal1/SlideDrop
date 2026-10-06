"""Download verified GitHub releases and hand off installation after app exit."""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import plistlib
import re
import secrets
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable

import httpx

from app_version import APP_VERSION

REPOSITORY = "arinaggarwal1/SlideDrop"
RELEASE_URL = f"https://github.com/{REPOSITORY}/releases/latest"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": f"SlideDrop/{APP_VERSION}"}
MAX_DOWNLOAD = 1024 * 1024 * 1024


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("The release does not have a supported stable version number.")
    return tuple(map(int, match.groups()))


def installation_target() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        target = executable.parent.parent.parent
        if target.suffix != ".app" or not os.access(target.parent, os.W_OK):
            return None
        return target
    if sys.platform == "win32":
        return executable
    return None


def select_asset(release: dict) -> dict | None:
    name = {"darwin": "SlideDrop.dmg", "win32": "SlideDrop-Setup.msi"}.get(sys.platform)
    for asset in release.get("assets", []):
        if asset.get("name") != name:
            continue
        url = asset.get("browser_download_url", "")
        if not url.startswith(f"https://github.com/{REPOSITORY}/releases/download/"):
            raise ValueError("The release download is not from the SlideDrop repository.")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
            raise ValueError("This release has no verified download checksum yet. Try again later.")
        if not 0 < asset.get("size", 0) <= MAX_DOWNLOAD:
            raise ValueError("The release download has an unsupported size.")
        return asset
    return None


def verify_mac_architecture(executable: Path):
    # -verify_arch consumes all following arguments as architecture names.
    # The input executable must precede it.
    result = subprocess.run(
        ["/usr/bin/lipo", str(executable), "-verify_arch", platform.machine()],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise ValueError(
            "The downloaded app could not be verified for this Mac’s processor. "
            "Your installed app has not been changed."
        )


# The old bundle is retained beside the new one for recovery. No broad deletion.
MAC_HELPER = r'''#!/bin/sh
pid="$1"; staged="$2"; target="$3"; backup="$4"
count=0
while kill -0 "$pid" 2>/dev/null; do
  sleep 1
  count=$((count + 1))
  if [ "$count" -ge 60 ]; then
    /usr/bin/osascript -e 'display alert "SlideDrop update paused" message "SlideDrop did not close. Your installed app has not been changed. Please try again."'
    exit 1
  fi
done
if /bin/mv "$target" "$backup"; then
  if /bin/mv "$staged" "$target"; then
    if /usr/bin/open "$target"; then
      exit 0
    fi
    /bin/mv "$target" "$staged"
  fi
  /bin/mv "$backup" "$target"
fi
/usr/bin/osascript -e 'display alert "SlideDrop update failed" message "The previous app has been kept. Please reopen SlideDrop and try again."'
/usr/bin/open "$target"
exit 1
'''


class AppUpdater:
    def __init__(self):
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.close_app: Callable[[], None] | None = None
        self.asset: dict | None = None
        self.download: Path | None = None
        self.staged: Path | None = None
        self.target: Path | None = None
        self.state = {"status": "idle", "current_version": APP_VERSION, "latest_version": None,
                      "message": "", "progress": 0, "release_url": RELEASE_URL}

    def snapshot(self) -> dict:
        with self.lock:
            return {**self.state, "can_install": installation_target() is not None and self.close_app is not None,
                    "token": self.token}

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def check(self) -> dict:
        with self.lock:
            if self.state["status"] in {"checking", "downloading", "ready", "installing"}:
                return self.snapshot()
            self.update(status="checking", message="Checking GitHub…", progress=0)
        try:
            with httpx.Client(timeout=20, headers=HEADERS) as client:
                response = client.get(API_URL)
            if response.status_code == 404:
                self.update(status="unavailable", message="No published release is available yet.")
                return self.snapshot()
            if response.status_code in {403, 429}:
                raise ValueError("GitHub is limiting update checks. Please try again later.")
            response.raise_for_status()
            release = response.json()
            if release.get("draft") or release.get("prerelease"):
                raise ValueError("No stable release is available yet.")
            latest = release.get("tag_name", "")
            newer = version_tuple(latest) > version_tuple(APP_VERSION)
            self.update(latest_version=latest.lstrip("v"))
            if not newer:
                message = f"You’re up to date (v{APP_VERSION})."
                if version_tuple(latest) < version_tuple(APP_VERSION):
                    message = f"This build (v{APP_VERSION}) is newer than the latest published release ({latest})."
                self.update(status="current", message=message)
            else:
                self.asset = select_asset(release)
                if not self.asset:
                    self.update(status="unavailable", message=f"Version {latest} is available, but its installer for this computer is not published yet.")
                else:
                    message = f"Version {latest} is available."
                    if installation_target() is None or self.close_app is None:
                        message += " Open the installed desktop app to update. On macOS, keep it in a writable Applications folder."
                    self.update(status="available", message=message)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Could not reach GitHub. Check your connection and try again."
            self.update(status="error", message=message)
        return self.snapshot()

    def start_download(self):
        with self.lock:
            if self.state["status"] != "available" or not self.asset:
                raise ValueError("Check for an available update first.")
            self.target = installation_target()
            if self.target is None or self.close_app is None:
                raise ValueError("Install updates from the packaged desktop app.")
            self.update(status="downloading", progress=0, message="Downloading update…")
            threading.Thread(target=self._download, daemon=True, name="slidedrop-update").start()

    def _download(self):
        try:
            asset = self.asset
            if asset is None:
                raise ValueError("No update selected.")
            folder = Path(tempfile.mkdtemp(prefix="slidedrop-update-"))
            download = folder / asset["name"]
            digest = hashlib.sha256()
            received = 0
            with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
                with client.stream("GET", asset["browser_download_url"]) as response:
                    response.raise_for_status()
                    with download.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 256):
                            received += len(chunk)
                            if received > asset["size"] or received > MAX_DOWNLOAD:
                                raise ValueError("The update download size did not match the release.")
                            handle.write(chunk)
                            digest.update(chunk)
                            self.update(progress=min(99, int(received * 100 / asset["size"])))
            if received != asset["size"] or f"sha256:{digest.hexdigest()}" != asset["digest"]:
                raise ValueError("Update verification failed. The installed app has not been changed.")
            self.download = download
            self.update(message="Preparing update…")
            if sys.platform == "darwin":
                self.staged = self._stage_mac(download)
            self.update(status="ready", progress=100, message="Update ready. Save your work before installing; SlideDrop will close.")
        except Exception as exc:
            self.update(status="error", message=f"Could not prepare the update: {exc}")

    def _stage_mac(self, download: Path) -> Path:
        if self.target is None:
            raise ValueError("Cannot locate the installed app.")
        mount = download.parent / "mount"
        mount.mkdir()
        subprocess.run(["/usr/bin/hdiutil", "attach", str(download), "-mountpoint", str(mount),
                        "-nobrowse", "-readonly", "-quiet"], check=True, timeout=120)
        try:
            app = mount / "SlideDrop.app"
            with (app / "Contents" / "Info.plist").open("rb") as handle:
                info = plistlib.load(handle)
            if info.get("CFBundleIdentifier") != "com.slidedrop.app":
                raise ValueError("The download is not a SlideDrop app.")
            if version_tuple(info.get("CFBundleShortVersionString", "")) != version_tuple(self.state["latest_version"]):
                raise ValueError("The downloaded app version does not match its release.")
            executable = app / "Contents" / "MacOS" / "SlideDrop"
            verify_mac_architecture(executable)
            staging = Path(tempfile.mkdtemp(prefix=".slidedrop-update-", dir=self.target.parent)) / "SlideDrop.app"
            subprocess.run(["/usr/bin/ditto", str(app), str(staging)], check=True, timeout=180)
            return staging
        finally:
            subprocess.run(["/usr/bin/hdiutil", "detach", str(mount), "-quiet"], check=True, timeout=30)

    def install(self):
        with self.lock:
            if self.state["status"] != "ready" or self.download is None or self.close_app is None:
                raise ValueError("Download an update before installing.")
            if sys.platform == "darwin":
                if self.staged is None or self.target is None:
                    raise ValueError("The update is not staged.")
                helper = self.download.parent / "install.sh"
                helper.write_text(MAC_HELPER)
                backup = self.staged.parent / "Previous-SlideDrop.app"
                command = ["/bin/sh", str(helper), str(os.getpid()), str(self.staged), str(self.target), str(backup)]
                subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "win32":
                # Encoded PowerShell avoids command-line quoting issues in user paths.
                msi = str(self.download).replace("'", "''")
                script = f'''$ErrorActionPreference = 'Stop'
try {{
  Wait-Process -Id {os.getpid()} -Timeout 60 -ErrorAction SilentlyContinue
  if (Get-Process -Id {os.getpid()} -ErrorAction SilentlyContinue) {{ throw 'SlideDrop did not close. Please try again.' }}
  $installer = Start-Process msiexec.exe -ArgumentList @('/i', '"{msi}"', '/passive', '/norestart') -Wait -PassThru
  if ($installer.ExitCode -notin @(0, 3010)) {{ throw "Installer exited with code $($installer.ExitCode)." }}
  Start-Process "$env:ProgramFiles\\SlideDrop\\SlideDrop.exe"
}} catch {{
  $popup = New-Object -ComObject WScript.Shell
  $popup.Popup("SlideDrop update could not finish: " + $_.Exception.Message, 0, 'SlideDrop update', 16)
}}
'''
                encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
                subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                 creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
            else:
                raise ValueError("Updates are supported on macOS and Windows.")
            self.update(status="installing", message="Installing update. SlideDrop will reopen when it finishes.")
            timer = threading.Timer(1.5, self.close_app)
            timer.daemon = True
            timer.start()


updater = AppUpdater()
