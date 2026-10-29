#!/usr/bin/env bash
# Lanzador para macOS y Linux. Uso:  ./iniciar_mac_linux.sh
set -e
cd "$(dirname "$0")"

PY=python3
command -v $PY >/dev/null 2>&1 || { echo "No se encontró python3. Instálalo primero."; exit 1; }

if ! $PY -c "import tkinter" 2>/dev/null; then
  echo "Falta tkinter. En Ubuntu/Debian:  sudo apt install python3-tk"
  echo "En macOS con Homebrew:            brew install python-tk"
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Primera ejecución: preparando el entorno, esto tarda unos minutos..."
  $PY -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python app.py
