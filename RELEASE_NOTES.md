# Heat Exchanger Calc v0.1.1

Patch release.

## Highlights

- Fixes Windows packaged executables failing at startup with `ModuleNotFoundError: No module named 'scipy._cyutility'`.
- Adds explicit PyInstaller hidden import collection for `scipy._cyutility`, required by the SciPy build used in the release environment.
- Desktop PyQt5 interface and Streamlit web interface.
- Save and load user input data as JSON.
- Startup and manual GitHub release update checks.
- Epsilon-NTU and LMTD calculations with engineering warnings.
- Cross-check support with `ht` and PyChemEngg.
- CoolProp and ChEDL (`fluids`, `thermo`, `ht`) property support.
- Detailed engineering report export with user inputs, selected methods, formulas, calculation steps, results, and warnings.
- Standalone Windows onedir builds for desktop and web launchers.

## Windows Assets

- `HeatExchangerCalcDesktop-v0.1.1-windows-x64.zip`
- `HeatExchangerCalcWeb-v0.1.1-windows-x64.zip`
- `SHA256SUMS.txt`

The executables are built with PyInstaller `--onedir --noupx`. They are not code-signed; some enterprise environments may still require allow-listing or a trusted code-signing certificate.
