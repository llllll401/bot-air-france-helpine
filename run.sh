#!/bin/bash
set -e
if [ ! -f config.json ]; then
  echo "⚠️  config.json manquant"
  echo "Crée ton config.json à partir du modèle fourni et mets ton DISCORD_TOKEN"
  cat config.json 2>/dev/null || echo "Aucun modèle trouvé"
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
