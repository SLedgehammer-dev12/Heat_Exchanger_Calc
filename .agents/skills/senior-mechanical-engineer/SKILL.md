---
name: senior-mechanical-engineer
description: >
  Mechanical engineering review & design verification: ASME Section VIII Div 1
  pressure vessel calculations (UG-27 shell thickness, UG-32/34 heads, UG-99 hydrostatic test),
  TEMA 10th Ed (tubesheets, baffle spacing, rho-v2 impingement, FIV vibration),
  API 661 air-cooled heat exchangers (face velocity, tip speed, fan power BHP, motor sizing),
  and process piping standards. Use for "mechanical review", "ASME check", "TEMA compliance",
  "API 661", "tubesheet thickness", "vibration analysis", /senior-mechanical-engineer.
argument-hint: "[module|equation|design]"
license: MIT
---

# Senior Mechanical Engineering Skill

Provides comprehensive mechanical engineering verification and code compliance for heat exchangers, waste heat boilers (WHRU), pressure vessels, and piping systems.

## Capabilities

1. **ASME Section VIII Div 1 UG-27 Shell Thickness:**
   - Evaluates minimum wall thickness under design pressure:
     $$t_{min} = \frac{P \cdot (R + CA)}{S \cdot E - 0.6 \cdot P} + CA$$
   - Verifies thin-shell applicability ($P \le 0.385 \cdot S \cdot E$).

2. **TEMA Class R/C/B Mechanical Standards:**
   - Tubesheet thickness under bending and shear stresses.
   - Baffle spacing, unsupported tube span, and impingement plate necessity ($\rho v^2$ kinetic energy).
   - Flow-Induced Vibration (FIV): Natural frequency ($f_n$), vortex shedding ($f_v$), acoustic resonance ($f_a$), and fluidelastic instability threshold ($v_{crit}$).

3. **API 661 Air-Cooled Heat Exchangers (ACHE):**
   - Air face velocity ($\le 3.5\text{ m/s}$) and fan blade tip speed ($\le 60\text{ m/s}$).
   - Fan plenum coverage ($A_{fan}/A_{face} \ge 0.40$).
   - Aerodynamic air power and fan shaft brake power (BHP).
   - Electric motor driver sizing with minimum 110% safety margin (Clause 7.2.3).
   - Noise level estimation (PWL and SPL @ 1 m).

4. **Process Piping & Darcy-Weisbach:**
   - DN schedule sizing, thermal expansion, and velocity bounds ($1.2 - 2.6\text{ m/s}$).

## How to Use

Invoke this skill whenever evaluating structural integrity, pressure vessel safety, nozzle loadings, tubesheet thickness, vibration risk, or API 661 fan selections.
