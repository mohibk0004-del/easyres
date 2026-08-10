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

It was engineered from the ground up to guarantee compatibility with kernel-level anti-cheats such as Vanguard, making it the safest and most efficient tool for achieving "True Stretch" in competitive titles.

## Key Features

* **True Stretched Resolutions:** Bypass heavy driver control panels (NVIDIA/AMD) and switch to popular competitive resolutions like 1440x1080 or 1280x960 instantly.
* **Native API Interfacing:** Utilizes Windows `ChangeDisplaySettingsEx` and `DEVMODE` structures for pure, unadulterated hardware instructions.
* **Vanguard & Anti-Cheat Safe:** Runs entirely in userspace using standard Windows binaries without injecting memory or violating Terms of Service.
* **Hardware Monitor Toggling:** Includes a built-in toggle to programmatically disable/enable integrated monitors via `pnputil`, a mandatory step for triggering hardware-level True Stretch on modern gaming laptops.
* **System Tray Quick-Switch:** Operates quietly in the background. Right-click the system tray icon to swap resolutions instantly without opening the interface.
* **Premium User Interface:** Built with PyQt6 featuring a sleek monochrome and amber aesthetic, hardware-accelerated transparency, and Apple-inspired physics/spring animations.
* **Single Instance Lock:** Uses a native Windows Mutex to ensure lightweight operation and prevent duplicate background processes.

## Requirements

* Windows 10 or Windows 11 (64-bit)
* Administrator Privileges (Required strictly for the `pnputil` hardware toggle feature)
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

## Technical Architecture

* **Frontend:** PyQt6 with completely custom painted widgets, frameless window resizing hooks (`WM_NCHITTEST`), and `QPropertyAnimation`.
* **Backend Core:** `ctypes` bindings to `user32.dll` and `kernel32.dll`.
* **Display Parsing:** Extracts valid EDID bounds via `EnumDisplaySettingsW` and synthesizes clean `DEVMODE` memory blocks to prevent driver-padding rejection.

## Disclaimer

The Custom Resolution feature is marked as Experimental. While EasyRes ensures safe validation via `CDS_TEST` before pushing a registry update, forcing display timings completely unsupported by your monitor's EDID can result in out-of-range black screens. Use standard competitive presets when possible.
