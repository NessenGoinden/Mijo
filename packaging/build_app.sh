#!/bin/bash
# Construit Nourriture.app et un .dmg prêt à partager (macOS, architecture de la machine courante).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "→ installation de uv (gestionnaire Python gratuit)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

VERSION=$(uv run --no-sync python -c "import nourriture; print(nourriture.__version__)" 2>/dev/null || .venv/bin/python -c "import nourriture; print(nourriture.__version__)")
ARCH=$(uname -m)
echo "→ Nourriture $VERSION ($ARCH)"

echo "→ dépendances…"
uv sync --group dev --python 3.12

echo "→ icône…"
.venv/bin/python packaging/make_icon.py

echo "→ PyInstaller…"
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/nourriture.spec

echo "→ signature ad hoc…"
codesign --force --deep --sign - "dist/Nourriture.app" 2>/dev/null || true

echo "→ image disque…"
rm -rf dist/dmg && mkdir -p dist/dmg
cp -R "dist/Nourriture.app" dist/dmg/
ln -s /Applications dist/dmg/Applications
cp packaging/LISEZ-MOI.txt dist/dmg/
DMG="dist/Nourriture-$VERSION-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "Nourriture" -srcfolder dist/dmg -ov -format UDZO "$DMG" >/dev/null
rm -rf dist/dmg

echo
echo "✅ Terminé :"
echo "   dist/Nourriture.app"
echo "   $DMG  ($(du -h "$DMG" | cut -f1))"
