#!/bin/bash
set -euo pipefail

VERSION="0.1.7"
ARCH=$(uname -m)

echo "=== Heat Exchanger Calc v${VERSION} macOS Build ==="

# Clean previous builds
rm -rf build dist release .venv
mkdir -p release

# Python virtual environment
echo "[1/6] Setting up virtual environment..."
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
    --collect-all numpy
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

# Desktop App (.app bundle)
echo "[2/6] Building Desktop app..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --windowed \
    --name HeatExchangerCalcDesktop \
    --icon app_icon.icns \
    --osx-bundle-identifier com.heat.exchanger.calc.desktop \
    --codesign-identity - \
    app_desktop.py

# Desktop Debug (--console, terminal output for troubleshooting)
echo "[3/6] Building Desktop Debug (console)..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --console \
    --name HeatExchangerCalcDesktopDebug \
    --icon app_icon.icns \
    app_desktop.py

# Web Launcher (.app bundle)
echo "[4/6] Building Web launcher..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --windowed \
    --name HeatExchangerCalcWeb \
    --icon app_icon.icns \
    --osx-bundle-identifier com.heat.exchanger.calc.web \
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

# Web Debug (--console, terminal output for troubleshooting)
echo "[5/6] Building Web Debug (console)..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --console \
    --name HeatExchangerCalcWebDebug \
    --icon app_icon.icns \
    --hidden-import app_web \
    --hidden-import fluids_db \
    --hidden-import heat_exchanger \
    --hidden-import reporting \
    --hidden-import updater \
    --hidden-import version \
    --hidden-import logging_config \
    --collect-all streamlit \
    --copy-metadata streamlit \
    --add-data "app_web.py:." \
    run_web.py

# Code-sign .app bundles + console binaries
echo "[6/6] Code-signing + packaging..."
declare -a SIGN_TARGETS=(
    "dist/HeatExchangerCalcDesktop.app"
    "dist/HeatExchangerCalcDesktopDebug/HeatExchangerCalcDesktopDebug"
    "dist/HeatExchangerCalcWeb.app"
    "dist/HeatExchangerCalcWebDebug/HeatExchangerCalcWebDebug"
)
for target in "${SIGN_TARGETS[@]}"; do
    if [[ -e "$target" ]]; then
        if [[ -d "$target" ]]; then
            codesign --force --deep -s - "$target"
            codesign -v --deep "$target" && echo "  ✅ $(basename "$target") signed"
        else
            codesign --force -s - "$target"
            codesign -v "$target" && echo "  ✅ $(basename "$target") signed"
        fi
    fi
done

# DMG: Desktop .app
hdiutil create -volname "HeatExchangerCalcDesktop" \
    -srcfolder "dist/HeatExchangerCalcDesktop.app" \
    -ov -format UDZO \
    "release/HeatExchangerCalcDesktop-v${VERSION}-macos-${ARCH}.dmg"

# DMG: Desktop Debug – pack folder into a temp layout then DMG
mkdir -p release-tmp-desktop
cp -R "dist/HeatExchangerCalcDesktopDebug" release-tmp-desktop/
hdiutil create -volname "HeatExchangerCalcDesktopDebug" \
    -srcfolder release-tmp-desktop \
    -ov -format UDZO \
    "release/HeatExchangerCalcDesktopDebug-v${VERSION}-macos-${ARCH}.dmg"
rm -rf release-tmp-desktop

# DMG: Web .app
hdiutil create -volname "HeatExchangerCalcWeb" \
    -srcfolder "dist/HeatExchangerCalcWeb.app" \
    -ov -format UDZO \
    "release/HeatExchangerCalcWeb-v${VERSION}-macos-${ARCH}.dmg"

# DMG: Web Debug
mkdir -p release-tmp-web
cp -R "dist/HeatExchangerCalcWebDebug" release-tmp-web/
hdiutil create -volname "HeatExchangerCalcWebDebug" \
    -srcfolder release-tmp-web \
    -ov -format UDZO \
    "release/HeatExchangerCalcWebDebug-v${VERSION}-macos-${ARCH}.dmg"
rm -rf release-tmp-web

# Checksums
cd release && shasum -a 256 *.dmg > SHA256SUMS.txt && cd ..

echo ""
echo "=== ✅ macOS release built successfully ==="
ls -lh release/
echo ""
cat release/SHA256SUMS.txt
