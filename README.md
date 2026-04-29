# Heat Exchanger Calc

Fin-tube heat exchanger calculator with desktop and web interfaces.

## Features

- Epsilon-NTU and LMTD based calculations
- Cross-check with `ht` and PyChemEngg
- CoolProp and ChEDL (`fluids`, `thermo`, `ht`) property support
- Manual and correlation based thermal oil data
- Detailed engineering report export
- Save/load input data as JSON
- GitHub release update check

## Run from source

```powershell
pip install -r requirements.txt
python app_desktop.py
streamlit run app_web.py
```

## Windows build

Desktop:

```powershell
pyinstaller --noconfirm --clean --onedir --noupx --windowed --name HeatExchangerCalcDesktop --hidden-import scipy._cyutility --collect-data chemicals --collect-data thermo --collect-data fluids --add-data "data;data" app_desktop.py
```

Web launcher:

```powershell
pyinstaller --noconfirm --clean --onedir --noupx --console --name HeatExchangerCalcWeb --hidden-import scipy._cyutility --hidden-import app_web --hidden-import fluids_db --hidden-import heat_exchanger --hidden-import reporting --hidden-import updater --hidden-import version --hidden-import logging_config --collect-all streamlit --copy-metadata streamlit --collect-data chemicals --collect-data thermo --collect-data fluids --add-data "app_web.py;." --add-data "data;data" run_web.py
```

Unsigned executables may still trigger reputation warnings on locked-down Windows environments. For enterprise deployment, code-sign the final executables with a trusted certificate.
