@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Nie znaleziono interpretera Python w PATH.
    echo Zainstaluj Python 3.11+ i dodaj go do PATH, a nastepnie uruchom ten plik ponownie.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --noconsole --name WindowsCaptureStudio app_advanced.py

echo.
echo -------------------------------
echo Gotowy plik EXE zostal wygenerowany w katalogu dist
echo -------------------------------
if exist "dist\WindowsCaptureStudio.exe" (
    echo Znaleziono: dist\WindowsCaptureStudio.exe
) else (
    echo Nie znaleziono pliku exe. Sprawdz, czy kompilacja zakonczyla sie poprawnie.
)
echo.
pause
