#!/usr/bin/env bash
set -e
pip install -r requirements.txt
playwright install --with-deps chromium
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
