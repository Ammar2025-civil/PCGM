@echo off
rem Builds a single VoidVanguard.exe with PyInstaller.
cd /d "%~dp0void_vanguard"
echo Installing / updating PyInstaller and pygame-ce...
python -m pip install --upgrade pyinstaller pygame-ce
if errorlevel 1 goto fail
echo.
echo Building the .exe (this takes a minute)...
python -m PyInstaller --noconfirm --onefile --windowed --name VoidVanguard main.py
if errorlevel 1 goto fail
echo.
echo Done! Your game is here:
echo   %~dp0void_vanguard\dist\VoidVanguard.exe
pause
exit /b 0

:fail
echo.
echo Something went wrong. Make sure Python is installed and "python --version" works.
pause
exit /b 1
