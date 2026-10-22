#!/usr/bin/env bash
# Start de Snackspert Trendradar. De eerste keer worden de packages geïnstalleerd.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Eerste keer: virtuele omgeving aanmaken en packages installeren…"
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
fi
# Nieuwe packages na een update (git pull) worden vanzelf bijgeïnstalleerd.
REQ_HASH="$(cksum requirements.txt | cut -d' ' -f1)"
if [ "$(cat .venv/.requirements-hash 2>/dev/null)" != "$REQ_HASH" ]; then
  echo "Packages installeren of bijwerken…"
  .venv/bin/pip install --quiet -r requirements.txt
  echo "$REQ_HASH" > .venv/.requirements-hash
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Leeg .env-bestand aangemaakt (demomodus). Vul je sleutels in om echte data op te halen."
fi
exec .venv/bin/python -m trendradar "$@"
