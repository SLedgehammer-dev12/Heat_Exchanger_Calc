# Heat Exchanger Calc

Fin-tube heat exchanger calculator with desktop and web interfaces.

## Features

- Epsilon-NTU and LMTD based calculations
- Cross-check with `ht` and PyChemEngg
- CoolProp and ChEDL (`fluids`, `thermo`, `ht`) property support
- Manual and correlation based thermal oil data
- Geometric U calculation with fouling resistance, Gnielinski internal-flow correlation, and selectable fin geometry
- Temperature profile plot and schematic with inlet/outlet temperatures
- Detailed engineering report export as TXT/PDF
- Save/load input data as JSON
- GitHub release update check and in-app package download

## Run from source

```powershell
pip install -r requirements.txt
python app_desktop.py
streamlit run app_web.py
```

## Windows build

```powershell
.\build_windows.ps1
```

The build script adds the app icon, Windows version metadata, ChEDL/`ht` data files, and excludes common unused notebook/interactive modules to reduce package size.

Before packaging, run:

```powershell
python -m unittest discover -s . -p "test*.py" -v
```

Unsigned executables may still trigger reputation warnings on locked-down Windows environments. For enterprise deployment, code-sign the final executables with a trusted certificate:

```powershell
.\build_windows.ps1 -CertificateThumbprint "<certificate-thumbprint>"
```
