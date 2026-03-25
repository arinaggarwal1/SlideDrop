#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="SlideDrop"
DMG_STAGING_DIR="dist/${APP_NAME}-dmg"
DMG_PATH="dist/${APP_NAME}.dmg"
FRONTEND_OUT="frontend/out"
FRONTEND_DIST="frontend_dist"

if [ -d "backend/venv" ]; then
    source backend/venv/bin/activate
fi

python3 - <<'PY'
import importlib

for module in ("webview", "PyInstaller"):
    importlib.import_module(module)
PY

export SLIDEDROP_DESKTOP_BUILD=1

cd frontend
npm ci
npm run build
cd "$SCRIPT_DIR"

rm -rf "$FRONTEND_DIST"
mkdir -p "$FRONTEND_DIST"
cp -R "$FRONTEND_OUT"/. "$FRONTEND_DIST"/

python3 -m PyInstaller SlideDrop.spec --noconfirm --clean

APP_DIR="dist/${APP_NAME}.app"
mkdir -p "${APP_DIR}/Contents/Resources"
rm -rf "${APP_DIR}/Contents/Resources/frontend_dist"
cp -R "$FRONTEND_DIST" "${APP_DIR}/Contents/Resources/frontend_dist"

rm -rf "$DMG_STAGING_DIR"
mkdir -p "$DMG_STAGING_DIR"
cp -R "$APP_DIR" "$DMG_STAGING_DIR/"
ln -s /Applications "$DMG_STAGING_DIR/Applications"

rm -f "$DMG_PATH"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGING_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

rm -rf "$DMG_STAGING_DIR"
