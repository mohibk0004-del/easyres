@echo off
echo Building EasyRes (Python Native)...
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_config_var('BINDIR') + '\\python' + sysconfig.get_python_version().replace('.', '') + '.dll')"') do set PYTHON_DLL=%%i
if exist assets (
    pyinstaller --clean --noupx --noconsole --onefile --uac-admin --icon icon.png --add-data "icon.png;." --add-data "assets;assets" --add-binary "%PYTHON_DLL%;." main.py --name EasyRes
) else (
    pyinstaller --clean --noupx --noconsole --onefile --uac-admin --icon icon.png --add-data "icon.png;." --add-binary "%PYTHON_DLL%;." main.py --name EasyRes
)
if %errorlevel% neq 0 (
    echo Build failed.
    exit /b %errorlevel%
)
echo Build succeeded!
echo Exe is located in dist\EasyRes.exe
