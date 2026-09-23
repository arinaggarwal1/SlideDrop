from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from platform_services import MacOSPlatform, WindowsPlatform, get_desktop_platform


class PlatformSelectionTests(unittest.TestCase):
    def test_selects_macos(self):
        self.assertIsInstance(get_desktop_platform("darwin"), MacOSPlatform)

    def test_selects_windows(self):
        self.assertIsInstance(get_desktop_platform("win32"), WindowsPlatform)


class MacOSPlatformTests(unittest.TestCase):
    @patch("platform_services.subprocess.run")
    def test_cancelled_folder_picker_returns_none(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "User canceled. (-128)")
        self.assertIsNone(MacOSPlatform().choose_folder())

    @patch("platform_services.subprocess.run")
    def test_pdf_picker_returns_each_path(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "/a/one.pdf\n/a/two.pdf\n", "")
        self.assertEqual(
            MacOSPlatform().choose_pdf_files(),
            ["/a/one.pdf", "/a/two.pdf"],
        )


class WindowsPlatformTests(unittest.TestCase):
    @patch.object(WindowsPlatform, "_run_powershell")
    def test_cancelled_folder_picker_returns_none(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        self.assertIsNone(WindowsPlatform().choose_folder())

    @patch.object(WindowsPlatform, "_run_powershell")
    def test_pdf_picker_returns_windows_paths(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "C:\\Docs\\one.pdf\nD:\\two.pdf\n", ""
        )
        self.assertEqual(
            WindowsPlatform().choose_pdf_files(),
            ["C:\\Docs\\one.pdf", "D:\\two.pdf"],
        )

    @patch("platform_services.subprocess.run")
    def test_reveals_file_in_explorer(self, run):
        with patch.object(Path, "is_file", return_value=True):
            WindowsPlatform().reveal_path(Path("C:/Docs/one.pdf"))
        run.assert_called_once_with(
            ["explorer.exe", "/select,", "C:/Docs/one.pdf"], check=True
        )


if __name__ == "__main__":
    unittest.main()

