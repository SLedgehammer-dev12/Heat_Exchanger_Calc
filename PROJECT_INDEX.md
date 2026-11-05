# Repository Index: Heat Exchanger Calculation & Sizing Suite

## 1. Project Overview & Architecture
`Heat_Exchanger_Calc` is an industrial-grade engineering calculation, design, and rating software suite for finned-tube, shell-and-tube, and double-pipe heat exchangers. It adheres to **TEMA Standards (10th Edition)**, **ASME Section VIII Division 1**, and **API 661 (Air-Cooled Heat Exchangers)**.

- **Primary Languages**: Python 3.10+ (tested on Python 3.10, 3.12, 3.13)
- **Frameworks**: Streamlit (Web App), PyQt5 (Desktop GUI - frozen), CoolProp / IAPWS-IF97 (Thermodynamic EOS), SciPy & NumPy (Numerics), ReportLab & openpyxl (Reporting), Three.js (WebGL 3D Visualizers)
- **Active Tests**: **264 passed** (100% passing rate) + **104/104 dynamic scenarios validated**
- **Code Quality**: Clean (`ruff` zero warnings/errors, strict Ponytail minimal-diff philosophy)

---

## 2. Directory & Module Map

### 2.1 Core Engineering & Thermodynamics
- [`heat_exchanger.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/heat_exchanger.py): Main heat exchanger model (`FinTubeHeatExchanger`, `Fluid`), $\epsilon$-NTU solvers, LMTD numerical solvers, multi-zone phase change models, 1D segmented finite-volume solver, TEMA RCB-4.62 entrance nozzle momentum flux ($\rho v^2$) impingement checks, and Bell-Delaware / Kern shell-side hydraulic correlations.
- [`correlations.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/correlations.py): Bowman-Mueller LMTD correction factors ($F$) with widened $R \to 1.0$ L'Hôpital threshold ($10^{-4}$), crossflow mixed/unmixed analytical effectiveness relations, and Zukauskas tube-bank crossflow Nusselt numbers.
- [`mechanical.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/mechanical.py): ASME UG-27 ($R_{corroded} = R + CA$), ASME UG-32 formed heads (2:1 ellipsoidal and torispherical), ASME UG-34 (flat covers), ASME UG-99(b) temperature-derated hydro test pressure ($1.3 \times MAWP \times S_{test}/S_{design}$), TEMA RCB-7.13 (tubesheet thickness & absolute minimum thickness floor), TEMA Table RCB-3.13 (minimum shell thickness), TEMA Section 5 Flow-Induced Vibration (FIV), and API 661 air-cooled fan sizing & acoustics.
- [`standards.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/standards.py): TEMA mechanical classes (R, C, B), BWG standard tube geometries, fouling resistance tables, and API 661 fin attachment standards.
- [`fluids_db.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/fluids_db.py): Thermodynamic property database wrapping CoolProp HEOS, IAPWS-IF97, ChEDL, Andrade exponential viscosity correlations ($\mu = \exp(A + B/T)$), and multi-component gas mixtures with strict positive-property validation.
- [`reporting.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/reporting.py): ReportLab PDF datasheets, CSV data tables, 1D profile exports, and `openpyxl` live formula Excel (.xlsx) export.

### 2.2 User Interfaces & Presentation
- [`app_web.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/app_web.py): Streamlit web application with reactive controls, real-time geometry validation, cached PDF/Excel generation, cleanly detached logger lifecycle handlers, ASME Sec VIII / TEMA mechanical verification cards, 3-zone condenser duty distribution, and embedded 2D/3D visualizers.
- [`app_desktop.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/app_desktop.py): PyQt5 desktop application (development frozen in favor of web app) providing calculation dashboards, solver cross-check comparisons, system logs, live ORC simulation launcher, 3D visualizer launcher, and Excel/PDF export dialogs.

### 2.3 Interactive Visualizers & Subsystems
- [`tubesheet_component.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/tubesheet_component.py): Procedural 2D SVG generator for TEMA tubesheet tube bundles (30°, 45°, 60°, 90° pitch) with multi-pass partition lanes, sanitized layout angle parsing, and $P/D_o < 1.25$ clearance warnings.
- [`exchanger_3d_component.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/exchanger_3d_component.py): Interactive Three.js / WebGL 3D teardown simulation with exploded view controls, component isolation, cutaways, flow animation, and XSS-safe HTML/JSON script tag escaping.
- [`orc_schematic_component.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/orc_schematic_component.py): Interactive SVG/DOM Organic Rankine Cycle and thermal oil network P&ID with multi-WHRU boilers, manifold headers, live flow animation, 3-way valve simulation, Darcy-Weisbach friction, and closed-loop static head cancellation.
- [`orc_3d_plant_component.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/orc_3d_plant_component.py): Interactive Three.js 3D Digital Twin plant visualizer for waste heat recovery ORC with turbines, boilers, condensers, and feed pumps.
- [`orc_system_model.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/orc_system_model.py): Thermodynamic cycle simulator for waste-heat recovery ORC with 1 to 5 parallel WHRU boilers, flow split balancing, series heat exchanger network (Superheater, Evaporator, Preheater), acid dew point protection, and real fluid Cyclopentane / Therminol 66 EOS.

---

## 3. Critical Files & Entry Points
1. **Desktop Entry Point**: [`app_desktop.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/app_desktop.py) (`python -m app_desktop` or `./build_macos.sh`)
2. **Web Entry Point**: [`app_web.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/app_web.py) (`streamlit run app_web.py`)
3. **Core Thermal Library**: [`heat_exchanger.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/heat_exchanger.py)
4. **Mechanical Codes & Standards**: [`mechanical.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/mechanical.py)
5. **Thermodynamic Cycle Simulator**: [`orc_system_model.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/orc_system_model.py)

---

## 4. Verification & Testing Matrix
- Total Tests: **264 automated unit and property-based tests** (100% passing)
- Dynamic Scenarios: **104/104 matrix evaluations passing** with 0 First Law violations and 0 anomalies
- Test Suites:
  - [`test_changes.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_changes.py): Phases 0 through 9 regression testing
  - [`test_phase1_fixes.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_phase1_fixes.py): ASME and hydraulic checks
  - [`test_phase2_correlations.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_phase2_correlations.py): Thermal-hydraulic correlations & 1D segmented solver
  - [`test_phase3_validation.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_phase3_validation.py): Solver consistency and energy balance
  - [`test_phase4_deliverables.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_phase4_deliverables.py): Reporting and export deliverables
  - [`test_phase5_engineering.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_phase5_engineering.py): TEMA Bowman, ASME corroded radius, tubesheet & cover mechanics
  - [`test_orc_system_model.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_orc_system_model.py): ORC thermodynamic cycle, NPSH, and series exchanger network
  - [`test_property_based.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_property_based.py): Hypothesis property-based tests for physical invariants
  - [`test_visualizers.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/test_visualizers.py): 3D teardown, ORC schematic, live formula Excel export, TEMA FIV, API 661 fan checks, and script escaping
  - [`verify_100_scenarios.py`](file:///Users/macbook/Documents/Kodlama/Heat_Exchanger_Calc/verify_100_scenarios.py): 104-case dynamic operational scenario stress test
