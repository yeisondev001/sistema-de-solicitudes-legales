#!/usr/bin/env bash
# Build de Render para la app nueva (Build Command: bash render-build.sh).
# Instala lo de Python y arma las pantallas de React en web/dist, que servidor.py entrega.
# Arranque (Start Command): uvicorn servidor:app --host 0.0.0.0 --port $PORT
set -euo pipefail

pip install -r requirements.txt

cd web
node --version
npm ci
npm run build
