# Heat Exchanger Calc v0.1.0

Initial public release.

## Highlights

- Desktop PyQt5 interface and Streamlit web interface.
- Save and load user input data as JSON.
- Startup and manual GitHub release update checks.
- Epsilon-NTU and LMTD calculations with engineering warnings.
- Cross-check support with `ht` and PyChemEngg.
- CoolProp and ChEDL (`fluids`, `thermo`, `ht`) property support.
- Detailed engineering report export with user inputs, selected methods, formulas, calculation steps, results, and warnings.
- Standalone Windows onedir builds for desktop and web launchers.

## Windows Assets

- `HeatExchangerCalcDesktop-v0.1.0-windows-x64.zip`
- `HeatExchangerCalcWeb-v0.1.0-windows-x64.zip`
- `SHA256SUMS.txt`

The executables are built with PyInstaller `--onedir --noupx`. They are not code-signed; some enterprise environments may still require allow-listing or a trusted code-signing certificate.
