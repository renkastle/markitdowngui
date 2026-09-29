#!/usr/bin/env bash
# Builds "dist/MarkItDown GUI.app" and "dist/MarkItDownGUI-<version>.dmg" on macOS.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

rm -rf build dist
pyinstaller --noconfirm packaging/MarkItDownGUI.spec

APP="dist/MarkItDown GUI.app"
# Quick check that the bundle can convert without opening a window.
printf '<h1>ok</h1>' > build/check.html
"$APP/Contents/MacOS/MarkItDownGUI" --cli build/check.html | grep -q '# ok'

# Ad-hoc signature so Gatekeeper shows "unidentified developer" instead of "damaged".
codesign --force --deep --sign - "$APP"

VERSION="$(python -c 'import markitdowngui; print(markitdowngui.__version__)')"
DMG="dist/MarkItDownGUI-${VERSION}-$(uname -m).dmg"
STAGING="$(mktemp -d)"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "MarkItDown GUI" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
rm -rf "$STAGING"
echo "Listo: $APP"
echo "Listo: $DMG"
