#!/usr/bin/env bash
# Start de Snackspert Trendradar. De eerste keer worden de packages geïnstalleerd.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Eerste keer: virtuele omgeving aanmaken en packages installeren…"
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Leeg .env-bestand aangemaakt (demomodus). Vul je sleutels in om echte data op te halen."
fi
exec .venv/bin/python -m trendradar "$@"
