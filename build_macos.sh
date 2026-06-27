#!/bin/bash
set -euo pipefail

VERSION="0.1.7"
ARCH=$(uname -m)

echo "=== Heat Exchanger Calc v${VERSION} macOS Build ==="

# Clean previous builds
rm -rf build dist release .venv
mkdir -p release

# Python virtual environment
echo "[1/5] Setting up virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt pyinstaller --quiet

HIDDEN_IMPORTS=(
    --hidden-import scipy._cyutility
    --hidden-import engineering_utils
    --hidden-import reportlab
    --hidden-import config
    --hidden-import units
    --hidden-import model_types
    --hidden-import i18n
    --hidden-import pint
    --hidden-import iapws
    --hidden-import exceptions
    --hidden-import helpers
    --hidden-import correlations
    --hidden-import plot_theme
)

COLLECT_ARGS=(
    --collect-data chemicals
    --collect-data thermo
    --collect-data fluids
    --collect-data ht
    --collect-data pint
    --collect-data iapws
    --collect-all reportlab
)

EXCLUDES=(
    --exclude-module tkinter
    --exclude-module IPython
    --exclude-module notebook
    --exclude-module jupyter
)

DATA_DIRS=(
    --add-data "data:data"
    --add-data "locale:locale"
)

PYINSTALLER_BASE=(
    --noconfirm
    --onedir
    "${HIDDEN_IMPORTS[@]}"
    "${COLLECT_ARGS[@]}"
    "${EXCLUDES[@]}"
    "${DATA_DIRS[@]}"
)

# Desktop App
echo "[2/6] Building Desktop app..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --windowed \
    --name HeatExchangerCalcDesktop \
    --icon app_icon.icns \
    --osx-bundle-identifier com.heat.exchanger.calc.desktop \
    --codesign-identity - \
    run_desktop.py

# Web Launcher
echo "[3/6] Building Web launcher..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --console \
    --name HeatExchangerCalcWeb \
    --icon app_icon.icns \
    --hidden-import app_web \
    --hidden-import fluids_db \
    --hidden-import heat_exchanger \
    --hidden-import reporting \
    --hidden-import updater \
    --hidden-import version \
    --hidden-import logging_config \
    --codesign-identity - \
    --collect-all streamlit \
    --copy-metadata streamlit \
    --add-data "app_web.py:." \
    run_web.py

# Deep code-sign all frameworks inside the bundle
echo "[4/6] Deep code-signing frameworks..."

# Desktop: .app bundle — --deep signs everything inside
if [[ -d "dist/HeatExchangerCalcDesktop.app" ]]; then
    codesign --force --deep -s - "dist/HeatExchangerCalcDesktop.app"
    codesign -v "dist/HeatExchangerCalcDesktop.app" && echo "  ✅ Desktop .app signed"
fi

# Web: regular folder — sign every .framework and .dylib individually
if [[ -d "dist/HeatExchangerCalcWeb/_internal" ]]; then
    echo "  Signing Python.framework..."
    find "dist/HeatExchangerCalcWeb/_internal" -name "Python.framework" -maxdepth 2 -type d 2>/dev/null | while read -r fw; do
        codesign --force --deep -s - "$fw" 2>/dev/null || true
    done
    echo "  Signing .dylib and .so libraries..."
    find "dist/HeatExchangerCalcWeb/_internal" \( -name "*.dylib" -o -name "*.so" \) 2>/dev/null | while read -r lib; do
        codesign --force -s - "$lib" 2>/dev/null || true
    done
    echo "  Signing main executable..."
    codesign --force -s - "dist/HeatExchangerCalcWeb/HeatExchangerCalcWeb" 2>/dev/null || true
    echo "  ✅ Web binary signed"
fi

# Create DMG
echo "[5/6] Creating DMG images..."
hdiutil create -volname "HeatExchangerCalcDesktop" \
    -srcfolder "dist/HeatExchangerCalcDesktop.app" \
    -ov -format UDZO \
    "release/HeatExchangerCalcDesktop-v${VERSION}-macos-${ARCH}.dmg"

hdiutil create -volname "HeatExchangerCalcWeb" \
    -srcfolder "dist/HeatExchangerCalcWeb" \
    -ov -format UDZO \
    "release/HeatExchangerCalcWeb-v${VERSION}-macos-${ARCH}.dmg"

# Checksums
echo "[6/6] Generating SHA256 checksums..."
cd release && shasum -a 256 *.dmg > SHA256SUMS.txt && cd ..

echo ""
echo "=== ✅ macOS release built successfully ==="
ls -lh release/
echo ""
cat release/SHA256SUMS.txt
