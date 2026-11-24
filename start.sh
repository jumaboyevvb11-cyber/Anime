#!/usr/bin/env bash
# Linux/macOS: python3 -m venv + o'rnatish + ishga tushirish
set -e
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python main.py
