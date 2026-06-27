# Heat Exchanger Calc v0.1.7

Robustness, test coverage and visual overhaul release.

## Code Robustness

- **Custom Exception Hierarchy** — `exceptions.py` introduces `HeatExchangerError`, `InvalidInputError`, `InvalidFlowTypeError`, `InvalidExchangerTypeError`, `InvalidGeometryError`, `FluidPropertyError`, `ConvergenceError`, `MissingDependencyError`, `UpdaterError`. Replaced 39 bare `raise ValueError(...)` / `raise ImportError(...)` across the codebase. Most new types inherit from `ValueError` so existing test assertions pass unchanged.
- **Module Split** — `heat_exchanger.py` core extracted into `helpers.py` (utility functions) and `correlations.py` (Bowman LMTD factor), reducing the main file from ~1321 to ~1207 lines.
- **Input Validation** — `GeometryInput.validate()` checks `D_o>0`, `D_i>0`, `D_i<D_o`, `L>0`, `N_tubes>=1`, `k_wall>0`, `baffle_cut 0.0-0.5`.
- **Dead Code Removed** — `plot_schematic` (uncalled) removed from `heat_exchanger.py`. `FALLBACK_NU_ANNULUS_LAMINAR` removed from `config.py`.

## Testing

- **Coverage Measurement** (`pytest-cov`) — Added to dev dependencies and CI. HTML coverage report uploaded on ubuntu+py3.12.
- **Property-Based Tests** (Hypothesis) — 8 tests in `test_property_based.py` covering NTU/LMTD NaN/Inf checks, F-factor bounds, energy balance diff `<15%`, fluid construct/reject.
- **Integration Pipeline Tests** — `TestIntegration_FullPipeline` in `test_changes.py` with 4 tests: snapshot→compute→text/PDF report for shell-and-tube, double-pipe, finned-tube, geometric mode.
- 110 total tests pass.

## Visual Overhaul

- **`plot_theme.py`** — New centralised matplotlib theme module: `apply_theme()` sets `seaborn-v0_8` base style with custom rcParams (Inter/SF Pro fonts, 15pt title, 13pt labels, slate/grid palette). `PALETTE` dict with Tailwind-inspired colours (`hot_in=#ef4444`, `cold_in=#3b82f6`, `body_fill=#f8fafc`, etc.). `SCHEMATIC_SIZE=(10,5)`, `TEMP_PROFILE_SIZE=(9,4.5)`.
- **`plot_enhanced_schematic`** — Completely rewritten: `FancyBboxPatch` with `Shadow`, rounded corners, staggered tube bundle, temperature badges with white bbox, exchanger name subtitle, gradient arrow styling.
- **`plot_temperature_profile`** — Rewritten with thicker lines (lw=3), per-point temperature annotations with leader arrows, external legend, `°C` symbol.
- **Streamlit CSS** — `app_web.py` adds inline `<style>` with rounded/shadowed containers for plots, tables, metrics; custom tab styling.
- **Ruff Format + Lint** — 11 files auto-formatted, 42 fixable lint issues auto-fixed.

## Build Infrastructure Fixes

- **`run_desktop.py`** — New launcher for PyInstaller-packaged desktop app (pattern matches existing `run_web.py`).
- **`pyproject.toml`** — Console scripts fixed: `heat-exchanger-desktop` now points to `run_desktop:main`, `heat-exchanger-web` to `run_web:main`.
- **Hidden Imports** — `exceptions`, `helpers`, `correlations`, `plot_theme` added to all build configs (`.spec` files, `build_macos.sh`, `build_windows.ps1`).
- **CI `build-test`** — Expanded with explicit import checks for all new modules.
- **Headless Backend** — `plot_theme.py` auto-selects `Agg` matplotlib backend when no display is available.
- **Windows Standalone `.exe`** — Windows builds now use `--onefile` mode, producing a single standalone `.exe` (no dependency folder). Both Desktop and Web versions are distributed as a single executable file.
- **PyInstaller Specs** — Updated to `--onefile` mode and new entry points (`run_desktop.py`, `run_web.py`).

## Release Assets

### Windows
- `HeatExchangerCalcDesktop-v0.1.7-windows-x64.exe`
- `HeatExchangerCalcWeb-v0.1.7-windows-x64.exe`

### macOS
- `HeatExchangerCalcDesktop-v0.1.7-macos-arm64.dmg`
- `HeatExchangerCalcWeb-v0.1.7-macos-arm64.dmg`

### All platforms
- `SHA256SUMS.txt`

---

# Heat Exchanger Calc v0.2.0

Major engineering accuracy and code quality release.

## Engineering Accuracy

- **LMTD Correction Factor** — Replaced `F ≈ 1 − 0.25·P·R` crude approximation with the industry-standard Bowman/Mueller algebraic formula (TEMA 1-N shell-and-tube). F < 0.5 triggers a design warning.
- **External Nusselt Correlations** — Upgraded bare-tube bank `Nu = 0.33·Re⁰·⁶` to Grimison tube-bank correlation (`ht.conv_tube_bank.Nu_Grimison_tube_bank`) with Zukauskas fallback and tube-row correction.
- **Annulus Nusselt** — Replaced internal-pipe correlation for double-pipe shell-side with proper Petukhov-Roizen laminar/turbulent annulus model using diameter ratio `r*`.
- **Pressure Drop (ΔP)** — Added Darcy-Weisbach tube-side and Briggs-Young/Zukauskas shell-side pressure drop calculation. Results included in geometric-U output and reports.
- **Phase Change Guard** — CoolProp fluids now detect `T_crit` and `T_sat`; ε-NTU/LMTD single-phase validity warnings issued when operating near or across saturation.
- **Midpoint Temperature Iteration** — Fluid properties now iteratively refined at `(T_in + T_out)/2` (2 passes), replacing single-inlet-temperature lookup.
- **Fin Efficiency Bessel Fallback** — Annular fins now fall back to Bessel-function efficiency (`I₀,I₁,K₀,K₁`) when Kern-Kraus fails, instead of incorrectly using the rectangular formula.
- **Quadratic Thermal Oil Model** — Thermal oil `cp(T)` upgraded from linear `cp_a + cp_b·T` to quadratic `cp_a + cp_b·T + cp_c·T²`. Optional `μ(T)` and `k(T)` linear correlation fields added.
- **Segmented Solver** — New `solve_segmented()` method reports segment-averaged midpoint temperatures for cross-check.

## Library Integrations

- **pint** — All unit conversions (`kg/s`, `°C`, `°F`, `CFM`, etc.) now handled by `pint.UnitRegistry` instead of manual math with Unicode hacks.
- **IAPWS-IF97** — Optional water/steam property backend via `iapws.IAPWS97` with CoolProp transport property fallback. Selectable as "Su (IAPWS-IF97)" in the fluid database.
- **Briggs-Young Validity** — Reynolds number range check (`1100 ≤ Re ≤ 18000`) added before applying finned-tube correlation.

## Code Architecture

- `config.py` — Centralised engineering constants (material catalog, correlation limits, roughness, log settings).
- `model_types.py` — `GeometryInput` and `CalcResult` dataclasses for structured data exchange.
- `units.py` — Clean pint-based unit module, replacing the encoding-hack `engineering_utils` functions (backward-compatible re-export kept).
- `i18n.py` — `gettext` infrastructure with `locale/tr/` message catalog for Turkish/English.
- `__init__.py` — Proper Python package public API with explicit `__all__`.
- `pyproject.toml` — Modern project configuration with `ruff`, `mypy`, `pytest`, and setuptools build backend.
- **Type annotations** — `from __future__ import annotations` and full type hints on all core engine functions.
- Cross-platform `os.startfile` replaced with `subprocess` (macOS: `open`, Linux: `xdg-open`).

## CI/CD

- **GitHub Actions** — `ci.yml` (lint, typecheck, test on ubuntu/windows/macos, Python 3.10/3.12) and `release.yml` (build + publish on `v*` tags).
- **Pre-commit** — `ruff`, `mypy`, trailing-whitespace hooks configured.
- **macOS Build** — New `build_macos.sh` script with `.app` bundle and `.dmg` packaging.
- **Windows Build** — Updated `build_windows.ps1` with new module imports and auto-release zip/SHA256 packaging.

## Release Assets

### Windows
- `HeatExchangerCalcDesktop-v0.2.0-windows-x64.zip`
- `HeatExchangerCalcWeb-v0.2.0-windows-x64.zip`

### macOS
- `HeatExchangerCalcDesktop-v0.2.0-macos-arm64.dmg`
- `HeatExchangerCalcWeb-v0.2.0-macos-arm64.dmg`

### All platforms
- `SHA256SUMS.txt`

## Upgrade Notes

- `pint` and `iapws` are new required dependencies — add to your environment with `pip install pint iapws`.
- Thermal oil JSON entries now support optional `cp_c`, `mu_a`, `mu_b`, `k_a`, `k_b` correlation fields.
- `engineering_utils` unit functions still work but delegate to `units.py` internally; new code should import from `units` directly.
- The `.spec` PyInstaller files are now version-controlled (removed from `.gitignore`).
