@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Brak Pythona w PATH.
    echo Zainstaluj Python 3.11+ i dodaj go do PATH, nastepnie uruchom ten plik.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install pillow pyinstaller
python -m PyInstaller --onefile --noconsole --name ScreenCaptureSimple app_simple.py

echo.
echo Gotowy plik EXE zostal wygenerowany w katalogu dist
if exist "dist\ScreenCaptureSimple.exe" (
    echo Znalazlem: dist\ScreenCaptureSimple.exe
) else (
    echo Nie znaleziono pliku exe.
)
echo.
pause
