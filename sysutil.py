"""Helpers for locating trusted Windows system binaries.

EasyRes runs elevated, so it must never resolve tools by bare name: the
executable's own folder and the user's PATH come before System32 in the
search order and are usually writable without admin rights.
"""

import os


def system_root() -> str:
    return os.environ.get("SystemRoot") or r"C:\Windows"


def system32_path(*parts: str) -> str:
    return os.path.join(system_root(), "System32", *parts)


def pnputil_path() -> str:
    return system32_path("pnputil.exe")


def powershell_path() -> str:
    return system32_path("WindowsPowerShell", "v1.0", "powershell.exe")


def cmd_path() -> str:
    return system32_path("cmd.exe")


def schtasks_path() -> str:
    return system32_path("schtasks.exe")
