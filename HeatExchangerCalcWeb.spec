# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = [('data', 'data'), ('app_web.py', '.'), ('locale', 'locale')]
binaries = []
hiddenimports = [
    'scipy._cyutility', 'engineering_utils', 'reportlab',
    'app_web', 'fluids_db', 'heat_exchanger', 'reporting', 'updater',
    'version', 'logging_config', 'engineering_utils',
    'config', 'units', 'model_types', 'i18n', 'pint', 'iapws',
    'exceptions', 'helpers', 'correlations', 'plot_theme',
]
datas += collect_data_files('chemicals')
datas += collect_data_files('thermo')
datas += collect_data_files('fluids')
datas += collect_data_files('ht')
datas += collect_data_files('pint')
datas += collect_data_files('iapws')
datas += copy_metadata('streamlit')
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('streamlit')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

icon_path = 'app_icon.icns' if sys.platform == 'darwin' else 'app_icon.ico'


a = Analysis(
    ['run_web.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'notebook', 'jupyter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='HeatExchangerCalcWeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=[icon_path],
)
