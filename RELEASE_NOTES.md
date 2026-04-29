# Heat Exchanger Calc v0.1.5

Patch release.

## Highlights

- Fixes Windows packaged executables failing at startup with `ModuleNotFoundError: No module named 'scipy._cyutility'`.
- Adds explicit PyInstaller hidden import collection for `scipy._cyutility`, required by the SciPy build used in the release environment.
- Fixes the Streamlit web executable failing at runtime with `ModuleNotFoundError: No module named 'fluids_db'`.
- Adds explicit PyInstaller hidden imports for the local application modules used by `app_web.py`.
- Adds editable exhaust gas composition on both hot and cold fluid sides.
- Supports mole-percent and mass-percent exhaust gas composition, with mixture properties calculated from the selected composition.
- Keeps viscosity and conductivity entry fields editable only for the explicit custom manual fluid option.
- Fixes packaged ChEDL/thermo fallback failures caused by missing `chemicals` identifier data files.
- Adds persistent rotating file logs under `%LOCALAPPDATA%\HeatExchangerCalc\logs\heat_exchanger_calc.log`.
- Desktop error popups now include the log path, and the Help menu can open the log folder.
- Update checks can now download the matching release zip directly from the app instead of opening the GitHub release page.
- Desktop update download uses a folder picker; web update download writes to the user-provided local folder path.
- Fixes desktop startup UI construction after the log-folder menu addition; the main input panel now initializes correctly.
- Fixes saved-data loading error caused by missing desktop form widgets.
- Desktop PyQt5 interface and Streamlit web interface.
- Save and load user input data as JSON.
- Startup and manual GitHub release update checks.
- Epsilon-NTU and LMTD calculations with engineering warnings.
- Cross-check support with `ht` and PyChemEngg.
- CoolProp and ChEDL (`fluids`, `thermo`, `ht`) property support.
- Detailed engineering report export with user inputs, selected methods, formulas, calculation steps, results, and warnings.
- Standalone Windows onedir builds for desktop and web launchers.

## Windows Assets

- `HeatExchangerCalcDesktop-v0.1.5-windows-x64.zip`
- `HeatExchangerCalcWeb-v0.1.5-windows-x64.zip`
- `SHA256SUMS.txt`

The executables are built with PyInstaller `--onedir --noupx`. They are not code-signed; some enterprise environments may still require allow-listing or a trusted code-signing certificate.
