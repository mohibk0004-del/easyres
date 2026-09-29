"""Safe, release-asset based self-updates for packaged EasyRes builds."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sysutil import powershell_path


RELEASE_API_URL = "https://api.github.com/repos/mohibk0004-del/easyres/releases/latest"
USER_AGENT = "EasyRes-Updater"
ALLOWED_DOWNLOAD_HOSTS = ("github.com", "githubusercontent.com")
CURRENT_VERSION = "2.1.8"


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadedUpdate:
    path: str
    sha256: str


def _version_parts(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version or "")
    return tuple(int(part) for part in numbers) if numbers else (0,)


def is_newer_version(latest: str, current: str) -> bool:
    latest_parts = _version_parts(latest)
    current_parts = _version_parts(current)
    width = max(len(latest_parts), len(current_parts))
    return latest_parts + (0,) * (width - len(latest_parts)) > current_parts + (0,) * (width - len(current_parts))


def fetch_latest_release(timeout: int = 8) -> dict:
    request = urllib.request.Request(
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            release = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise UpdateError(f"Could not check for updates: {exc}") from exc

    if release.get("draft") or release.get("prerelease"):
        raise UpdateError("Latest release is not a stable public release.")
    if not release.get("tag_name"):
        raise UpdateError("Latest release has no version tag.")
    return release


def select_windows_asset(release: dict) -> dict:
    assets = [asset for asset in release.get("assets", []) if asset.get("state") == "uploaded"]
    candidates = [asset for asset in assets if asset.get("name", "").lower() == "easyres.exe"]
    if not candidates:
        raise UpdateError("This release does not include an EasyRes Windows executable.")
    return candidates[0]


def can_self_update() -> bool:
    return os.name == "nt" and bool(getattr(sys, "frozen", False)) and Path(sys.executable).suffix.lower() == ".exe"


def _allowed_download_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_DOWNLOAD_HOSTS)


def download_asset(asset: dict, progress_callback=None, opener=urllib.request.urlopen) -> DownloadedUpdate:
    url = asset.get("browser_download_url", "")
    name = os.path.basename(asset.get("name", ""))
    if not _allowed_download_url(url) or not name.lower().endswith(".exe"):
        raise UpdateError("Release asset URL or filename is invalid.")

    expected_size = int(asset.get("size") or 0)
    digest = asset.get("digest") or ""
    expected_sha256 = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else None
    if not expected_sha256 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise UpdateError("This release has no published SHA-256 digest, so it cannot be verified.")

    update_dir = Path(tempfile.mkdtemp(prefix="EasyResUpdate-"))
    partial_path = update_dir / f"{name}.part"
    final_path = update_dir / name
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    hasher = hashlib.sha256()
    downloaded = 0
    file_header = b""

    try:
        with opener(request, timeout=30) as response, partial_path.open("wb") as output:
            final_url = response.geturl() if hasattr(response, "geturl") else url
            if not _allowed_download_url(final_url):
                raise UpdateError("Release download redirected to an untrusted host.")
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                output.write(chunk)
                hasher.update(chunk)
                if len(file_header) < 2:
                    file_header += chunk[:2 - len(file_header)]
                downloaded += len(chunk)
                if progress_callback and expected_size:
                    progress_callback(min(100, int(downloaded * 100 / expected_size)))

        if expected_size and downloaded != expected_size:
            raise UpdateError(f"Downloaded size mismatch: expected {expected_size} bytes, received {downloaded}.")
        if expected_sha256 and hasher.hexdigest().lower() != expected_sha256:
            raise UpdateError("Downloaded update failed SHA-256 verification.")
        if downloaded == 0:
            raise UpdateError("Downloaded update is empty.")
        if file_header != b"MZ":
            raise UpdateError("Downloaded update is not a valid Windows executable.")

        os.replace(partial_path, final_path)
        if progress_callback:
            progress_callback(100)
        return DownloadedUpdate(str(final_path), hasher.hexdigest().lower())
    except Exception:
        shutil.rmtree(update_dir, ignore_errors=True)
        raise


def discard_download(downloaded_update) -> None:
    path = Path(downloaded_update.path if isinstance(downloaded_update, DownloadedUpdate) else downloaded_update)
    if path.parent.name.startswith("EasyResUpdate-"):
        shutil.rmtree(path.parent, ignore_errors=True)


def launch_replacement(downloaded_update: DownloadedUpdate, target_executable: str | None = None) -> None:
    if os.name != "nt":
        raise UpdateError("Self-update is only supported on Windows.")

    if not isinstance(downloaded_update, DownloadedUpdate) or not re.fullmatch(r"[0-9a-f]{64}", downloaded_update.sha256):
        raise UpdateError("Verified update metadata is invalid.")

    downloaded = Path(downloaded_update.path).resolve()
    target = Path(target_executable or sys.executable).resolve()
    if not downloaded.is_file() or downloaded.suffix.lower() != ".exe":
        raise UpdateError("Downloaded update executable is missing.")
    if target.suffix.lower() != ".exe":
        raise UpdateError("Current EasyRes executable path is invalid.")

    powershell = powershell_path()
    if not os.path.isfile(powershell):
        raise UpdateError("Windows PowerShell is required to finish the update.")
    # The installer runs elevated. It is passed inline via -EncodedCommand so
    # there is no script file on disk that a non-admin process could swap
    # between writing and execution. PowerShell is launched directly (not via
    # cmd.exe) because cmd.exe truncates command lines at 8191 characters.
    script = build_install_script(str(target), str(downloaded), downloaded_update.sha256, os.getpid())

    creation_flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    try:
        subprocess.Popen(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encode_powershell_command(script),
            ],
            close_fds=True,
            creationflags=creation_flags,
        )
    except Exception as exc:
        discard_download(downloaded_update)
        raise UpdateError(f"Could not launch the update installer: {exc}") from exc


def _ps_literal(value: str) -> str:
    """Quote a value as a PowerShell single-quoted string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def encode_powershell_command(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def build_install_script(target: str, download: str, expected_sha256: str, process_id: int) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""):
        raise UpdateError("Verified update metadata is invalid.")
    header = (
        f"$Target = {_ps_literal(target)}\n"
        f"$Download = {_ps_literal(download)}\n"
        f"$ExpectedSha256 = {_ps_literal(expected_sha256)}\n"
        f"$EasyResProcessId = {int(process_id)}\n"
    )
    return header + INSTALL_SCRIPT_BODY


INSTALL_SCRIPT_BODY = r'''$ErrorActionPreference = "Stop"
$downloadDir = Split-Path -Parent $Download
$backup = "$Target.old"
$log = "$Target.update-error.log"

try {
    Wait-Process -Id $EasyResProcessId -Timeout 15 -ErrorAction Stop
} catch {
    $runningProcess = Get-Process -Id $EasyResProcessId -ErrorAction SilentlyContinue
    if ($runningProcess) {
        Stop-Process -Id $EasyResProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

for ($attempt = 0; $attempt -lt 80; $attempt++) {
    if (-not (Test-Path -LiteralPath $Download)) { break }
    try {
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        Move-Item -LiteralPath $Target -Destination $backup -Force
        Move-Item -LiteralPath $Download -Destination $Target -Force
        $installedHash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($installedHash -ne $ExpectedSha256) { throw "Installed update failed SHA-256 verification." }
        $newProcess = Start-Process -FilePath $Target -WorkingDirectory (Split-Path -Parent $Target) -PassThru
        Start-Sleep -Seconds 2
        if ($newProcess.HasExited) { throw "Updated EasyRes exited during startup." }
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
        Remove-Item -LiteralPath $downloadDir -Recurse -Force -ErrorAction SilentlyContinue
        exit 0
    } catch {
        if (Test-Path -LiteralPath $backup) {
            if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue }
            Move-Item -LiteralPath $backup -Destination $Target -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 250
    }
}

"EasyRes update failed after repeated replacement attempts." | Set-Content -LiteralPath $log
if (Test-Path -LiteralPath $Target) {
    Start-Process -FilePath $Target -WorkingDirectory (Split-Path -Parent $Target)
}
Remove-Item -LiteralPath $downloadDir -Recurse -Force -ErrorAction SilentlyContinue
exit 1
'''
