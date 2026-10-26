#!/bin/bash
set -e
if [ ! -f .env ]; then
  echo "⚠️  .env manquant -> copie .env.example"
  cp .env.example .env
  echo "Edite .env avec ton DISCORD_TOKEN puis relance ./run.sh"
  exit 1
fi
# venv auto si pas docker
if command -v python3 &> /dev/null; then
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  pip install -r requirements.txt
  python bot.py
else
  docker compose up --build -d
  docker logs -f airfrance-helpine
fi
