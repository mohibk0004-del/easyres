@echo off
echo Building EasyRes (Python Native)...
if exist assets (
    pyinstaller --noconsole --onefile --uac-admin --icon icon.png --add-data "icon.png;." --add-data "assets;assets" main.py --name EasyRes
) else (
    pyinstaller --noconsole --onefile --uac-admin --icon icon.png --add-data "icon.png;." main.py --name EasyRes
)
if %errorlevel% neq 0 (
    echo Build failed.
    exit /b %errorlevel%
)
echo Build succeeded!
echo Exe is located in dist\EasyRes.exe
