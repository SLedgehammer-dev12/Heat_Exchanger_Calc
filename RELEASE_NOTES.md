# Heat Exchanger Calc v0.1.2

Patch release.

## Highlights

- Fixes Windows packaged executables failing at startup with `ModuleNotFoundError: No module named 'scipy._cyutility'`.
- Adds explicit PyInstaller hidden import collection for `scipy._cyutility`, required by the SciPy build used in the release environment.
- Fixes the Streamlit web executable failing at runtime with `ModuleNotFoundError: No module named 'fluids_db'`.
- Adds explicit PyInstaller hidden imports for the local application modules used by `app_web.py`.
- Adds editable exhaust gas composition on both hot and cold fluid sides.
- Supports mole-percent and mass-percent exhaust gas composition, with mixture properties calculated from the selected composition.
- Keeps viscosity and conductivity entry fields editable only for the explicit custom manual fluid option.
- Desktop PyQt5 interface and Streamlit web interface.
- Save and load user input data as JSON.
- Startup and manual GitHub release update checks.
- Epsilon-NTU and LMTD calculations with engineering warnings.
- Cross-check support with `ht` and PyChemEngg.
- CoolProp and ChEDL (`fluids`, `thermo`, `ht`) property support.
- Detailed engineering report export with user inputs, selected methods, formulas, calculation steps, results, and warnings.
- Standalone Windows onedir builds for desktop and web launchers.

## Windows Assets

- `HeatExchangerCalcDesktop-v0.1.2-windows-x64.zip`
- `HeatExchangerCalcWeb-v0.1.2-windows-x64.zip`
- `SHA256SUMS.txt`

The executables are built with PyInstaller `--onedir --noupx`. They are not code-signed; some enterprise environments may still require allow-listing or a trusted code-signing certificate.
