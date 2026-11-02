#!/usr/bin/env bash
# Start Morph on macOS or Linux:   ./start-mac-linux.sh
cd "$(dirname "$0")" || exit 1

PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo
  echo "  Python isn't installed."
  echo "  Mac:   install it from https://www.python.org/downloads/  (or: brew install python)"
  echo "  Linux: sudo apt install python3 python3-venv"
  echo
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo
  echo "  Setting up Morph for the first time. This takes a few minutes..."
  echo
  "$PY" -m venv .venv || { echo "  Couldn't create the environment. On Linux run: sudo apt install python3-venv"; exit 1; }
  .venv/bin/python -m pip install --upgrade pip
  if ! .venv/bin/python -m pip install -r requirements.txt; then
    echo
    echo "  Installing the packages didn't finish. Check your internet connection and run this again."
    rm -rf .venv
    exit 1
  fi
fi

echo "  Checking for YouTube downloader updates..."
.venv/bin/python -m pip install -q --upgrade "yt-dlp[default]" >/dev/null 2>&1

exec .venv/bin/python app.py
