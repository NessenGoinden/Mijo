#!/bin/bash
# Installation « sans .dmg » : copie les sources dans ~/Library/Application Support/Nourriture/app,
# installe Python et les dépendances avec uv (gratuit), puis crée Nourriture.app dans /Applications.
# Usage : double-cliquez sur install.command, ou dans le Terminal :  bash install.sh
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Library/Application Support/Nourriture/app"
echo "🍲 Installation de Nourriture"

if [ ! -x "$HOME/.local/bin/uv" ] && ! command -v uv >/dev/null 2>&1; then
  echo "→ installation de uv (gestionnaire Python, gratuit et open source)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

echo "→ copie des fichiers…"
mkdir -p "$APP_DIR"
rsync -a --delete --exclude .venv --exclude build --exclude dist --exclude .git --exclude "__pycache__" "$SRC/" "$APP_DIR/"

echo "→ Python 3.12 et dépendances (quelques minutes la première fois)…"
cd "$APP_DIR"
uv sync --python 3.12
.venv/bin/python packaging/make_icon.py >/dev/null
chmod +x packaging/launch.sh

echo "→ création de /Applications/Nourriture.app…"
LAUNCHER="$APP_DIR/packaging/launch.sh"
rm -rf "/Applications/Nourriture.app"
osacompile -o "/Applications/Nourriture.app" -e "do shell script \"nohup '$LAUNCHER' >/dev/null 2>&1 &\""
cp "$APP_DIR/packaging/Nourriture.icns" "/Applications/Nourriture.app/Contents/Resources/applet.icns"
touch "/Applications/Nourriture.app"

if [ ! -d /Applications/Ollama.app ] && ! command -v ollama >/dev/null 2>&1; then
  echo
  echo "⚠️  Ollama (moteur d'IA locale, gratuit) n'est pas installé."
  echo "    Téléchargez-le sur https://ollama.com/download puis ouvrez-le une fois."
  open "https://ollama.com/download" || true
fi

echo
echo "✅ Nourriture est installée : ouvrez-la depuis le dossier Applications (ou Spotlight)."
