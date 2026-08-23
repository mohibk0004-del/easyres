import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import updater


class FakeResponse:
    def __init__(self, payload, url):
        self.payload = payload
        self.url = url
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self):
        return self.url

    def read(self, size=-1):
        if self.offset >= len(self.payload):
            return b""
        end = len(self.payload) if size < 0 else min(len(self.payload), self.offset + size)
        chunk = self.payload[self.offset:end]
        self.offset = end
        return chunk


class UpdaterTests(unittest.TestCase):
    def test_version_comparison_handles_v_prefix_and_missing_parts(self):
        self.assertTrue(updater.is_newer_version("v2.2", "2.1.4"))
        self.assertFalse(updater.is_newer_version("v2.1.4", "2.1.4"))
        self.assertFalse(updater.is_newer_version("2.1", "2.1.1"))

    def test_asset_selection_prefers_exact_executable(self):
        release = {
            "assets": [
                {"name": "EasyRes-setup.exe", "state": "uploaded"},
                {"name": "EasyRes.exe", "state": "uploaded"},
            ]
        }
        self.assertEqual(updater.select_windows_asset(release)["name"], "EasyRes.exe")

    def test_download_validates_size_and_sha256(self):
        payload = b"MZ fake executable bytes"
        asset = {
            "name": "EasyRes.exe",
            "state": "uploaded",
            "size": len(payload),
            "digest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
            "browser_download_url": "https://github.com/example/release/EasyRes.exe",
        }
        original_mkdtemp = tempfile.mkdtemp
        with tempfile.TemporaryDirectory() as directory:
            updater.tempfile.mkdtemp = lambda prefix: directory
            try:
                result = updater.download_asset(
                    asset,
                    opener=lambda request, timeout: FakeResponse(payload, asset["browser_download_url"]),
                )
                self.assertEqual(Path(result.path).read_bytes(), payload)
                self.assertEqual(result.sha256, hashlib.sha256(payload).hexdigest())
            finally:
                updater.tempfile.mkdtemp = original_mkdtemp

    def test_download_rejects_bad_digest(self):
        payload = b"MZ fake executable bytes"
        asset = {
            "name": "EasyRes.exe",
            "state": "uploaded",
            "size": len(payload),
            "digest": "sha256:" + "0" * 64,
            "browser_download_url": "https://github.com/example/release/EasyRes.exe",
        }
        with tempfile.TemporaryDirectory() as directory:
            original_mkdtemp = tempfile.mkdtemp
            updater.tempfile.mkdtemp = lambda prefix: directory
            try:
                with self.assertRaises(updater.UpdateError):
                    updater.download_asset(
                        asset,
                        opener=lambda request, timeout: FakeResponse(payload, asset["browser_download_url"]),
                    )
            finally:
                updater.tempfile.mkdtemp = original_mkdtemp

    def test_download_rejects_non_windows_payload(self):
        payload = b"not an executable"
        asset = {
            "name": "EasyRes.exe",
            "state": "uploaded",
            "size": len(payload),
            "browser_download_url": "https://github.com/example/release/EasyRes.exe",
        }
        with tempfile.TemporaryDirectory() as directory:
            original_mkdtemp = tempfile.mkdtemp
            updater.tempfile.mkdtemp = lambda prefix: directory
            try:
                with self.assertRaisesRegex(updater.UpdateError, "valid Windows executable"):
                    updater.download_asset(
                        asset,
                        opener=lambda request, timeout: FakeResponse(payload, asset["browser_download_url"]),
                    )
            finally:
                updater.tempfile.mkdtemp = original_mkdtemp

    @unittest.skipUnless(os.name == "nt", "Windows replacement helper")
    def test_replacement_helper_uses_argument_list_and_rollback_script(self):
        with tempfile.TemporaryDirectory() as directory:
            downloaded = Path(directory) / "EasyRes.exe"
            target = Path(directory) / "installed" / "EasyRes.exe"
            target.parent.mkdir()
            downloaded.write_bytes(b"MZ update")
            target.write_bytes(b"MZ current")

            def fake_which(name):
                if name == "powershell.exe":
                    return r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
                if name == "cmd.exe":
                    return r"C:\Windows\System32\cmd.exe"
                return None

            with patch("updater.shutil.which", side_effect=fake_which), patch("updater.subprocess.Popen") as popen:
                update = updater.DownloadedUpdate(str(downloaded), hashlib.sha256(downloaded.read_bytes()).hexdigest())
                updater.launch_replacement(update, str(target))

            command = popen.call_args.args[0]
            self.assertEqual(command[0], r"C:\Windows\System32\cmd.exe")
            self.assertIn("start", command)
            self.assertIn(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", command)
            self.assertIn("-File", command)
            script_path = downloaded.parent / "install-update.ps1"
            script = script_path.read_text(encoding="utf-8")
            self.assertIn("Wait-Process -Id $EasyResProcessId -Timeout 15", script)
            self.assertIn("Stop-Process -Id $EasyResProcessId -Force", script)
            self.assertIn("Move-Item -LiteralPath $Target -Destination $backup", script)
            self.assertIn("Move-Item -LiteralPath $backup -Destination $Target", script)
            self.assertIn("Get-FileHash -LiteralPath $Target -Algorithm SHA256", script)
            self.assertIn("-ExpectedSha256", command)


if __name__ == "__main__":
    unittest.main()
