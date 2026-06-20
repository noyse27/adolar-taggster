@echo off
python "%~dp0tagger.py"
if errorlevel 1 (
    echo.
    echo Fehler beim Starten. Bitte zuerst installieren:
    echo pip install PyQt6 mutagen requests Pillow
    pause
)
