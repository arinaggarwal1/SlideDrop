import hashlib
import sys
import tempfile
import subprocess
import base64
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import updater as module
from main import app


def release(version="v9.0.0", content=b"installer"):
    return {"tag_name": version, "draft": False, "prerelease": False, "assets": [{
        "name": "SlideDrop.dmg",
        "browser_download_url": f"https://github.com/{module.REPOSITORY}/releases/download/{version}/SlideDrop.dmg",
        "digest": "sha256:" + hashlib.sha256(content).hexdigest(), "size": len(content),
    }]}


class UpdateTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "darwin", "macOS architecture verification")
    def test_real_macos_executable_passes_architecture_check(self):
        # Exercise the real command parser, not a mock that accepts bad flags.
        module.verify_mac_architecture(Path(sys.executable))

    def test_incompatible_architecture_has_readable_error(self):
        with patch.object(module.subprocess, "run", return_value=Mock(returncode=1)):
            with self.assertRaisesRegex(ValueError, "processor"):
                module.verify_mac_architecture(Path("/test/SlideDrop"))

    def api_client(self, payload, status=200):
        return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status, json=payload)))

    def test_version_comparison_is_numeric_and_stable_only(self):
        self.assertGreater(module.version_tuple("v1.10.0"), module.version_tuple("1.9.9"))
        with self.assertRaises(ValueError):
            module.version_tuple("v2.0.0-beta")

    @patch.object(module.sys, "platform", "darwin")
    def test_new_release_and_development_install_guard(self):
        updater = module.AppUpdater()
        with patch.object(module.httpx, "Client", return_value=self.api_client(release())):
            result = updater.check()
        self.assertEqual(result["status"], "available")
        self.assertFalse(result["can_install"])
        with self.assertRaises(ValueError):
            updater.start_download()

    def test_older_or_equal_release_never_downgrades(self):
        for version in ["v0.1.0", "v" + module.APP_VERSION]:
            updater = module.AppUpdater()
            with patch.object(module.httpx, "Client", return_value=self.api_client(release(version))):
                self.assertEqual(updater.check()["status"], "current")

    def test_missing_release_and_rate_limit_are_actionable(self):
        for code, expected in [(404, "unavailable"), (403, "error"), (429, "error")]:
            with patch.object(module.httpx, "Client", return_value=self.api_client({}, code)):
                self.assertEqual(module.AppUpdater().check()["status"], expected)

    @patch.object(module.sys, "platform", "darwin")
    def test_untrusted_url_and_missing_digest_rejected(self):
        data = release()
        data["assets"][0]["browser_download_url"] = "https://example.com/installer"
        with self.assertRaises(ValueError):
            module.select_asset(data)
        data = release()
        data["assets"][0]["digest"] = None
        with self.assertRaises(ValueError):
            module.select_asset(data)

    @patch.object(module.sys, "platform", "darwin")
    def test_verified_download_and_tamper_rejection(self):
        for content, expected in [(b"installer", "ready"), (b"tampered!", "error")]:
            updater = module.AppUpdater()
            updater.asset = release()["assets"][0]
            updater.close_app = Mock()
            with tempfile.TemporaryDirectory() as folder:
                client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=content)))
                with patch.object(module.httpx, "Client", return_value=client), \
                     patch.object(module.tempfile, "mkdtemp", return_value=folder), \
                     patch.object(updater, "_stage_mac", return_value=Path(folder) / "SlideDrop.app") as stage:
                    updater._download()
                self.assertEqual(updater.snapshot()["status"], expected)
                self.assertEqual(stage.called, expected == "ready")
                updater.close_app.assert_not_called()

    @patch.object(module.sys, "platform", "darwin")
    def test_install_handoff_keeps_backup_and_closes_after_response(self):
        updater = module.AppUpdater()
        with tempfile.TemporaryDirectory() as folder:
            updater.download = Path(folder) / "SlideDrop.dmg"
            updater.staged = Path(folder) / "SlideDrop.app"
            updater.target = Path(folder) / "installed" / "SlideDrop.app"
            updater.close_app = Mock()
            updater.update(status="ready")
            with patch.object(module.subprocess, "Popen") as launch, patch.object(module.threading, "Timer") as timer:
                updater.install()
                args = launch.call_args.args[0]
                self.assertEqual(args[:1], ["/bin/sh"])
                self.assertTrue(args[-1].endswith("Previous-SlideDrop.app"))
                timer.assert_called_once_with(1.5, updater.close_app)
                updater.close_app.assert_not_called()
            self.assertEqual(updater.snapshot()["status"], "installing")

    def test_install_endpoints_require_session_token(self):
        client = TestClient(app)
        for endpoint in ["download", "install"]:
            self.assertEqual(client.post(f"/updates/{endpoint}").status_code, 403)

    @unittest.skipUnless(sys.platform == "darwin", "macOS helper test")
    def test_mac_helper_replaces_or_rolls_back_only_test_bundles(self):
        for fail_replace in [False, True]:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                target, staged, backup = [root / name for name in ["old.app", "new.app", "backup.app"]]
                target.mkdir()
                staged.mkdir()
                (target / "old-marker").touch()
                (staged / "new-marker").touch()
                # Exercise actual moves, but never launch an app or display a dialog.
                script = module.MAC_HELPER.replace("/usr/bin/open", "/usr/bin/true").replace("/usr/bin/osascript", "/usr/bin/true")
                if fail_replace:
                    script = script.replace('if /bin/mv "$staged" "$target"; then', 'if /usr/bin/false; then')
                result = subprocess.run(["/bin/sh", "-s", "99999999", str(staged), str(target), str(backup)], input=script, text=True)
                if fail_replace:
                    self.assertEqual(result.returncode, 1)
                    self.assertTrue((target / "old-marker").exists())
                else:
                    self.assertEqual(result.returncode, 0)
                    self.assertTrue((target / "new-marker").exists())
                    self.assertTrue((backup / "old-marker").exists())

    def test_windows_handoff_waits_for_exit_and_uses_msi(self):
        updater = module.AppUpdater()
        updater.download = Path("C:/Test Folder/SlideDrop-Setup.msi")
        updater.close_app = Mock()
        updater.update(status="ready")
        with patch.object(module.sys, "platform", "win32"), \
             patch.object(module.subprocess, "CREATE_NO_WINDOW", 0, create=True), \
             patch.object(module.subprocess, "DETACHED_PROCESS", 0, create=True), \
             patch.object(module.subprocess, "Popen") as launch, \
             patch.object(module.threading, "Timer"):
            updater.install()
        command = launch.call_args.args[0]
        script = base64.b64decode(command[-1]).decode("utf-16-le")
        self.assertIn("Wait-Process", script)
        self.assertIn("msiexec.exe", script)
        self.assertIn(str(updater.download), script)
        self.assertEqual(updater.snapshot()["status"], "installing")


if __name__ == "__main__":
    unittest.main()
