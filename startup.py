"""Run-at-logon support.

EasyRes requires administrator rights, and Windows silently skips elevated
programs listed under the HKCU Run key. A Task Scheduler logon task with the
highest run level is the supported way to start it elevated without a UAC
prompt.
"""

import os
import subprocess
import sys

from sysutil import schtasks_path

TASK_NAME = "EasyRes"
LEGACY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def is_supported() -> bool:
    return os.name == "nt" and bool(getattr(sys, "frozen", False))


def _run(args):
    return subprocess.run(
        [schtasks_path()] + args,
        capture_output=True, text=True, creationflags=_NO_WINDOW, timeout=20,
    )


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        return _run(["/Query", "/TN", TASK_NAME]).returncode == 0
    except Exception:
        return False


def _remove_legacy_run_entry():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LEGACY_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, TASK_NAME)
    except OSError:
        pass


def set_enabled(enabled: bool):
    """Returns (ok, message)."""
    if not is_supported():
        return False, "Start at login is available in the packaged EasyRes.exe build."
    _remove_legacy_run_entry()
    try:
        if enabled:
            user = os.environ.get("USERNAME", "")
            domain = os.environ.get("USERDOMAIN", "")
            account = f"{domain}\\{user}" if domain else user
            args = [
                "/Create", "/TN", TASK_NAME,
                "/TR", f'"{os.path.abspath(sys.executable)}"',
                "/SC", "ONLOGON", "/RL", "HIGHEST", "/F",
            ]
            if account:
                args += ["/RU", account, "/IT"]
            result = _run(args)
        else:
            if not is_enabled():
                return True, ""
            result = _run(["/Delete", "/TN", TASK_NAME, "/F"])
    except Exception as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "Task Scheduler refused the change.").strip()
    return True, ""
