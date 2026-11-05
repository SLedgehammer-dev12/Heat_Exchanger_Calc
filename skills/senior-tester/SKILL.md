---
name: senior-tester
description: >
  QA verification & test automation: Property-based testing (Hypothesis),
  thermodynamic and mechanical physical invariant checks, 100+ scenario matrix validation,
  numerical stability, edge-case coverage, and client-side WebGL script checks.
  Use for "run tests", "verify equations", "test coverage", "numerical stability",
  "regression check", /senior-tester.
argument-hint: "[suite|invariants|edge-cases]"
license: MIT
---

# Senior Test Engineer Skill

Automates rigorous thermodynamic, mechanical, hydraulic, and numerical test suites across Python backend and client-side WebGL simulation runtimes.

## Capabilities

1. **Automated Test Execution & Reporting:**
   - Runs `pytest` suites with full test execution, timing, and failure analysis.
   - Measures statement and branch test coverage (`pytest-cov`).

2. **Thermodynamic Physical Invariants:**
   - Energy conservation (First Law $\sum Q_{in} = \sum Q_{out} + W_{net}$).
   - Second Law consistency ($\varepsilon \le 1.0, \eta_{thermal} \le \eta_{carnot}$).
   - Monotonicity checks ($dQ/dm \ge 0, dQ/dA \ge 0$).
   - Boundary checks ($m \to 0, UA \to 0, \text{Bypass} = 1.0$).

3. **Mechanical Standards Verification:**
   - ASME UG-27 stress and thickness limits.
   - TEMA acoustic and vortex shedding resonance bands.
   - API 661 velocity, tip speed, and motor power margins.

4. **100+ Dynamic Scenario Matrix Testing:**
   - Automated parametric sweeps across 1-5 WHRU boilers, fluid pairings, and pressure levels via `verify_100_scenarios.py`.

5. **Client-Side / WebGL Validation:**
   - Validates Three.js and SVG DOM JavaScript syntax using `node --check`.

## How to Use

Invoke this skill whenever changes are made to physics, geometry, or calculation algorithms to prevent regressions and prove numerical stability.
