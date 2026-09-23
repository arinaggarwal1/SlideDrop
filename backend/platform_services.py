"""Native desktop operations behind a small cross-platform interface.

The API and frontend call these functions without needing to know whether the
desktop shell is running on macOS or Windows.  Keeping the platform branching
here prevents OS-specific behavior from leaking into the shared application.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Protocol


class DesktopPlatform(Protocol):
    name: str
    file_manager_name: str

    def choose_folder(self) -> str | None: ...

    def choose_pdf_files(self) -> list[str]: ...

    def reveal_path(self, target: Path) -> None: ...


class MacOSPlatform:
    name = "macOS"
    file_manager_name = "Finder"

    def choose_folder(self) -> str | None:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "Select a save folder")',
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        stderr = (result.stderr or "").strip()
        if "-128" in stderr:
            return None
        raise RuntimeError(stderr or "Failed to open the folder picker.")

    def choose_pdf_files(self) -> list[str]:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'set chosenFiles to choose file of type {"com.adobe.pdf"} with prompt "Select PDF files to merge" with multiple selections allowed',
                "-e",
                'set output to ""',
                "-e",
                "repeat with chosenFile in chosenFiles",
                "-e",
                'set output to output & POSIX path of chosenFile & linefeed',
                "-e",
                "end repeat",
                "-e",
                "return output",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        stderr = (result.stderr or "").strip()
        if "-128" in stderr:
            return []
        raise RuntimeError(stderr or "Failed to open the PDF picker.")

    def reveal_path(self, target: Path) -> None:
        command = ["open", "-R", str(target)] if target.is_file() else ["open", str(target)]
        subprocess.run(command, check=True)


class WindowsPlatform:
    name = "Windows"
    file_manager_name = "File Explorer"

    @staticmethod
    def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-STA",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def choose_folder(self) -> str | None:
        script = """
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select a save folder'
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Out.Write($dialog.SelectedPath)
}
"""
        result = self._run_powershell(script)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "").strip() or "Failed to open the folder picker.")
        return result.stdout.strip() or None

    def choose_pdf_files(self) -> list[str]:
        script = """
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Select PDF files to merge'
$dialog.Filter = 'PDF files (*.pdf)|*.pdf'
$dialog.Multiselect = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    $dialog.FileNames | ForEach-Object { [Console]::Out.WriteLine($_) }
}
"""
        result = self._run_powershell(script)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "").strip() or "Failed to open the PDF picker.")
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def reveal_path(self, target: Path) -> None:
        if target.is_file():
            subprocess.run(["explorer.exe", "/select,", str(target)], check=True)
        else:
            subprocess.run(["explorer.exe", str(target)], check=True)


class UnsupportedPlatform:
    name = sys.platform
    file_manager_name = "file manager"

    @staticmethod
    def _unsupported() -> RuntimeError:
        return RuntimeError(f"Native desktop operations are not supported on {sys.platform}.")

    def choose_folder(self) -> str | None:
        raise self._unsupported()

    def choose_pdf_files(self) -> list[str]:
        raise self._unsupported()

    def reveal_path(self, target: Path) -> None:
        raise self._unsupported()


def get_desktop_platform(platform_name: str | None = None) -> DesktopPlatform:
    """Return native operations for the current OS (or an explicit test OS)."""
    selected = platform_name or sys.platform
    if selected == "darwin":
        return MacOSPlatform()
    if selected == "win32" or selected.startswith("cygwin"):
        return WindowsPlatform()
    return UnsupportedPlatform()


desktop_platform = get_desktop_platform()
