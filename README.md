<div align="center">

# EasyRes

<img src="https://img.shields.io/badge/Platform-Windows_10%20%7C%2011-blue?style=for-the-badge&logo=windows&logoColor=white" alt="Windows Support" />
<img src="https://img.shields.io/badge/Language-Python_3.12+-yellow?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/Framework-PyQt6-green?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6" />
<img src="https://img.shields.io/badge/Status-Experimental-red?style=for-the-badge" alt="Experimental" />

**A premium, lightweight Windows utility to instantly switch to custom and stretched resolutions natively.**

</div>

---

## Overview

EasyRes is a high-performance resolution manager designed specifically for competitive gamers and power users. Unlike traditional software that relies on injected driver settings (which can cause input lag or be blocked by strict anti-cheat software), EasyRes interacts directly with the lowest levels of the Windows Display API to force instantaneous, lag-free resolution swapping.

It only uses documented Windows display APIs and never touches game processes. Anti-cheat policies are set by each game publisher, so check your game's rules before use.

## Key Features

* **True Stretched Resolutions:** Bypass heavy driver control panels (NVIDIA/AMD) and switch to popular competitive resolutions like 1440x1080 or 1280x960 instantly.
* **Native API Interfacing:** Utilizes Windows `ChangeDisplaySettingsEx` and `DEVMODE` structures for pure, unadulterated hardware instructions.
* **No Game Injection:** Runs entirely in userspace using standard Windows APIs and binaries; it never reads or writes game memory.
* **Safe Switching:** Every resolution change made in the window offers a 15-second keep-or-revert countdown, and `Ctrl+Shift+F12` restores native resolution from anywhere.
* **Hardware Monitor Toggling:** Includes a built-in toggle to programmatically disable/enable integrated monitors via `pnputil`, a mandatory step for triggering hardware-level True Stretch on modern gaming laptops.
* **System Tray Quick-Switch:** Operates quietly in the background. Right-click the system tray icon to swap resolutions instantly without opening the interface.
* **Focused Interface:** PyQt6 with a black, graphite and blurple theme, keyboard navigation, and motion that respects the Windows "Animation effects" setting.
* **Single Instance Lock:** Uses a native Windows Mutex to ensure lightweight operation and prevent duplicate background processes.

## Requirements

* Windows 10 or Windows 11 (64-bit)
* Administrator Privileges (required for the `pnputil` monitor toggle, EDID overrides, and driver restarts)
* Display drivers that natively expose custom timing parameters

## Build Instructions

If you wish to compile the application from source rather than running the raw Python scripts, you can use the included PyInstaller build script.

1. Install Python 3.10+
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the automated build script:
   ```cmd
   .\build.bat
   ```
4. The standalone, portable executable will be generated in the `dist/` directory as `EasyRes.exe`.

Optional: place `Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf` and `Inter-Bold.ttf` (SIL Open Font License) in `assets/fonts/` to bundle Inter. Without them EasyRes uses Segoe UI.

Run the tests with `python -m unittest discover -s tests`.

### Publishing Updates

Bump `CURRENT_VERSION` in `updater.py`, then attach the packaged binary to each stable GitHub release with the exact asset name `EasyRes.exe`. Packaged builds use that asset for in-app updates. The GitHub SHA-256 asset digest is required: EasyRes verifies it and the file size, then replaces and restarts itself with rollback protection. Releases without a digest are refused.

## Technical Architecture

* **Frontend:** PyQt6 sidebar + pages shell (`ui/app_window.py`, `ui/pages/`) driven by a widget-free `AppController` (`ui/controller.py`). Native Windows chrome via DWM (`ui/native_chrome.py`: real shadow, Win11 rounded corners, Snap Layouts), in-window sheets, a single property-driven stylesheet (`theme/styles.py`), and background workers for every blocking system call. Set `EASYRES_QT_FRAME=1` to fall back to a Qt-only frame.
* **Backend Core:** `ctypes` bindings to `user32.dll` and `kernel32.dll`.
* **Display Parsing:** Extracts valid EDID bounds via `EnumDisplaySettingsW` and synthesizes clean `DEVMODE` memory blocks to prevent driver-padding rejection.

## Disclaimer

The Custom Resolution feature is marked as Experimental. While EasyRes ensures safe validation via `CDS_TEST` before pushing a registry update, forcing display timings completely unsupported by your monitor's EDID can result in out-of-range black screens. Use standard competitive presets when possible.
