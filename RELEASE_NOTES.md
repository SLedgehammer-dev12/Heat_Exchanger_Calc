# Heat Exchanger Calc v0.2.0

Major engineering accuracy and industrial scope release.

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

## Cross-Flow, Shell-and-Tube & Two-Phase Accuracy

- **Cross-Flow Correction Factor Fix** — `_calc_crossflow_F` for the `cross_mixed_unmixed` (finned tube) configuration now branches on `C_h ≥ C_c` (Cmax-mixed) vs `C_h < C_c` (Cmin-mixed), matching the `solve_ntu` effectiveness implementation and eliminating a previously inconsistent F-factor path.
- **Tube Passes → Bowman LMTD F** — New `tube_passes` geometry input (default 2 = TEMA 1-2) is passed as `N_shell_passes` into the Bowman/Mueller F-factor. A single tube pass now correctly yields F = 1.0 for counterflow (the previous N=1 fallthrough incorrectly produced F < 1).
- **TEMA Baffle-Cut Validation** — `baffle_cut` outside the TEMA 15–45 % range raises a design warning; `shell_passes > 1` flags the E/F-shell LMTD approximation.
- **Laminar Thermal Entrance Region** — Optional `LAMINAR_ENTRANCE_MODEL` applies the Hausen correction `Nu = Nu_∞ + 0.0668·Gz/(1 + 0.04·Gz^(2/3))` using the local Graetz number `Gz = Re·Pr·D_i/L`. Tube-side laminar `h_i` rises up to ~40 % for short tubes.
- **Condenser / Evaporator Solvers** — New `solve_condenser()` and `solve_evaporator()` implement the phase-change limit (Cr = 0, ε = 1 − e^(−NTU)) driven by latent heat `h_fg` (new optional `Fluid.h_fg` field), with a latent-heat-capacity cap so partial condensation/boiling is reported via a status warning.

## Industrial Pressure Drop, Pumping & Standards

- **Pump & Fan Power** — `pump_power_tube`/`pump_power_shell` now apply the correct efficiency: `PUMP_EFFICIENCY` (0.70) for liquids, `FAN_EFFICIENCY` (0.60) for gases (density < 100 kg/m³), and are reported in TXT/PDF reports.
- **Multi-Pass Local Losses** — Local (fitting) pressure losses scale with pass count: `4 · N_pass · ρ·v²/2` (`LOCAL_LOSS_VELOCITY_HEADS_PER_PASS = 4.0`).
- **TEMA Vibration Pre-Check** — Shell-side impingement warning when `ρ·v² > 1500` (`TEMA_RHO_V2_LIMIT`) and unsupported-tube-span warning when `baffle_spacing > 60 · D_o` (`MAX_UNSUPPORTED_SPAN_FACTOR`).
- **`standards.py`** — New module with BWG wall-thickness / tube OD presets (`tube_preset_options()`, 12 presets) and the TEMA fouling-factor table (`fouling_preset_options()`), wired into both the desktop combo boxes and the web selectboxes.
- **Schmidt Plate-Fin Efficiency** — `_fin_efficiency` supports `fin_type="plate"` via the Schmidt (1949) equivalent-radius model `r_eq = 1.28·ψ·√(β − 0.2)·r_o` with rectangular-fin pitch inputs.

## Reporting, UX & Localisation

- **Images Embedded in PDF** — The PDF report now embeds the flow schematic and temperature-profile figures as native reportlab `Image` flowables (desktop: PNG buffers; web: matplotlib buffers) under a new "Akış Şeması ve Sıcaklık Profili" section.
- **TEMA Designation Selector** — New `combo_tema` (BEM, AEL, AES, …) with `TEMA_DESIGNATIONS` in config; shell-specific geometry fields (baffle spacing/cut, layout angle, shell/tube passes, TEMA) are shown only for shell-and-tube exchangers.
- **`_()` i18n Wiring** — Report titles and section headers now pass through the `gettext` `_()` function wired to the existing `locale/tr/` catalog.
- **Shell Geometry UI** — New `spin_baffle_spacing`, `spin_baffle_cut`, `combo_layout_angle`, `spin_shell_passes`, `spin_tube_passes` controls on desktop with full snapshot/save/load persistence.

## Code Quality & Two-Phase Extensions

- **`run_solvers()`** — The four-solver cross-check sequence (custom NTU, custom LMTD, HT NTU, HT LMTD) is now encapsulated in one method, eliminating duplicated solver blocks in desktop, web and `cross_check`.
- **Two-Phase Fluid Field** — `Fluid.h_fg` optional latent-heat field supports the new condenser/evaporator solvers.
- **Cleanup** — Removed dead code, duplicate config constant, "Gnielowski"→"Gnielinski" typo, and added missing `GEOMETRY_LABELS` entries (`pitch_parallel`, `tube_arrangement`, `baffle_spacing`, `baffle_cut`, `tube_layout_angle`, `shell_passes`, `tube_passes`, `tema_designation`).
- **Test Coverage** — 21 new tests (131 total, up from 110) covering cross-flow branch consistency, Bowman tube-passes, laminar entrance, `GeometryInput` round-trips, pump-power keys, multi-pass ΔP increase, vibration warnings, Schmidt plate fins, standards presets, `run_solvers`, and the two-phase solvers. A 12-scenario physical sanity sweep (ε ∈ [0,1], energy-balance, temperature-cross) verified all exchanger/flow/geometry combinations.

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

---

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