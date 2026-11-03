@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -m venv .venv || goto :error
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt pyinstaller || goto :error
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "R4sGate-Wallpaper-Studio" main.py || goto :error

echo.
echo Build finished: dist\R4sGate-Wallpaper-Studio.exe
exit /b 0

:error
echo.
echo Build failed.
exit /b 1
