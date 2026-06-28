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
    --hidden-import fluids_db
    --hidden-import heat_exchanger
    --hidden-import logging_config
    --hidden-import reporting
    --hidden-import updater
    --hidden-import version
    --hidden-import scipy._external.array_api_compat.numpy.fft
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
    --collect-submodules scipy._external
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
    --paths .
    "${HIDDEN_IMPORTS[@]}"
    "${COLLECT_ARGS[@]}"
    "${EXCLUDES[@]}"
    "${DATA_DIRS[@]}"
)

# Desktop App (.app bundle)
echo "[2/4] Building Desktop app..."
pyinstaller \
    "${PYINSTALLER_BASE[@]}" \
    --windowed \
    --name HeatExchangerCalcDesktop \
    --icon app_icon.icns \
    --osx-bundle-identifier com.heat.exchanger.calc.desktop \
    --codesign-identity - \
    app_desktop.py

# Web Launcher (.app bundle)
echo "[3/4] Building Web launcher..."
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

# Deep code-sign each .app bundle with single ad-hoc identity
echo "[4/4] Code-signing + packaging..."
for app in "dist/HeatExchangerCalcDesktop.app" "dist/HeatExchangerCalcWeb.app"; do
    if [[ -d "$app" ]]; then
        codesign --force --deep -s - "$app"
        codesign -v --deep "$app" && echo "  ✅ $(basename "$app") signed"
    else
        echo "  ❌ $app not found!"
        exit 1
    fi
done

# DMG: Desktop .app
hdiutil create -volname "HeatExchangerCalcDesktop" \
    -srcfolder "dist/HeatExchangerCalcDesktop.app" \
    -ov -format UDZO \
    "release/HeatExchangerCalcDesktop-v${VERSION}-macos-${ARCH}.dmg"

# DMG: Web .app
hdiutil create -volname "HeatExchangerCalcWeb" \
    -srcfolder "dist/HeatExchangerCalcWeb.app" \
    -ov -format UDZO \
    "release/HeatExchangerCalcWeb-v${VERSION}-macos-${ARCH}.dmg"

# Checksums
cd release && shasum -a 256 *.dmg > SHA256SUMS.txt && cd ..

echo ""
echo "=== ✅ macOS release built successfully ==="
ls -lh release/
echo ""
cat release/SHA256SUMS.txt
