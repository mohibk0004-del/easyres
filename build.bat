@echo off
echo Building EasyRes (Python Native)...
pyinstaller --noconsole --onefile --uac-admin main.py --name EasyRes
if %errorlevel% neq 0 (
    echo Build failed.
    exit /b %errorlevel%
)
echo Build succeeded!
echo Exe is located in dist\EasyRes.exe
