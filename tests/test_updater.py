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
            "digest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
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

    def test_download_requires_published_digest(self):
        payload = b"MZ fake executable bytes"
        asset = {
            "name": "EasyRes.exe",
            "state": "uploaded",
            "size": len(payload),
            "browser_download_url": "https://github.com/example/release/EasyRes.exe",
        }
        with self.assertRaisesRegex(updater.UpdateError, "SHA-256"):
            updater.download_asset(
                asset,
                opener=lambda request, timeout: FakeResponse(payload, asset["browser_download_url"]),
            )

    def test_asset_selection_rejects_lookalike_names(self):
        release = {"assets": [{"name": "EasyRes-setup.exe", "state": "uploaded"}]}
        with self.assertRaises(updater.UpdateError):
            updater.select_windows_asset(release)

    def test_install_script_quotes_paths_and_rolls_back(self):
        sha = "a" * 64
        script = updater.build_install_script(r"C:\Games\It's Mine\EasyRes.exe", r"C:\Temp\x\EasyRes.exe", sha, 1234)
        self.assertIn(r"$Target = 'C:\Games\It''s Mine\EasyRes.exe'", script)
        self.assertIn(f"$ExpectedSha256 = '{sha}'", script)
        self.assertIn("$EasyResProcessId = 1234", script)
        self.assertIn("Wait-Process -Id $EasyResProcessId -Timeout 15", script)
        self.assertIn("Move-Item -LiteralPath $backup -Destination $Target", script)
        self.assertIn("Get-FileHash -LiteralPath $Target -Algorithm SHA256", script)
        self.assertNotIn("$PSCommandPath", script)

    def test_install_script_rejects_bad_digest(self):
        with self.assertRaises(updater.UpdateError):
            updater.build_install_script("a.exe", "b.exe", "not-a-sha", 1)

    def test_encoded_command_round_trips(self):
        import base64
        encoded = updater.encode_powershell_command("Write-Output 'hi'")
        self.assertEqual(base64.b64decode(encoded).decode("utf-16-le"), "Write-Output 'hi'")

    @unittest.skipUnless(os.name == "nt", "Windows replacement helper")
    def test_replacement_helper_runs_inline_script_without_file(self):
        with tempfile.TemporaryDirectory() as directory:
            downloaded = Path(directory) / "EasyRes.exe"
            target = Path(directory) / "installed" / "EasyRes.exe"
            target.parent.mkdir()
            downloaded.write_bytes(b"MZ update")
            target.write_bytes(b"MZ current")

            with patch("updater.subprocess.Popen") as popen:
                update = updater.DownloadedUpdate(str(downloaded), hashlib.sha256(downloaded.read_bytes()).hexdigest())
                updater.launch_replacement(update, str(target))

            command = popen.call_args.args[0]
            self.assertTrue(command[0].lower().endswith(r"system32\windowspowershell\v1.0\powershell.exe"))
            self.assertIn("-EncodedCommand", command)
            self.assertNotIn("-File", command)
            self.assertFalse((downloaded.parent / "install-update.ps1").exists())


if __name__ == "__main__":
    unittest.main()
