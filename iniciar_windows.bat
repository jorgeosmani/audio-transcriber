@echo off
chcp 65001 >nul
title Transcriptor de audios
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
    echo y marca la casilla "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Primera ejecucion: preparando el entorno, esto tarda unos minutos...
    python -m venv .venv || (pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)

start "" ".venv\Scripts\pythonw.exe" app.py
