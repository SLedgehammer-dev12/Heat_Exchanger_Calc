---
name: senior-thermodynamic-engineer
description: >
  Thermodynamic and heat transfer audit: Industrial heat exchanger rating
  (LMTD Bowman F-factor, temperature cross prevention, epsilon-NTU solvers, 1D finite-volume),
  Organic Rankine Cycle (ORC) power loops (real fluid Helmholtz EOS, multi-zone superheater/evaporator/preheater,
  flow scaling, Carnot limits), multi-WHRU boiler trains, and Darcy-Weisbach hydraulics.
  Use for "thermodynamic audit", "ORC cycle", "WHRU calculation", "LMTD check", "pinch analysis",
  /senior-thermodynamic-engineer.
argument-hint: "[cycle|hx|whru|hydraulics]"
license: MIT
---

# Senior Thermodynamic Engineering Skill

Provides deep thermodynamic, heat transfer, and cycle analysis across industrial heat exchangers, WHRU waste heat recovery boilers, Organic Rankine Cycles (ORC), and closed hydraulic circuits.

## Capabilities

1. **Heat Exchanger Thermal Rating & Crosscheck:**
   - Evaluates LMTD with Bowman-Mueller correction factor $F$.
   - Strictly flags and prevents thermodynamic temperature crosses ($P \ge 1.0, S \ge 1.0$).
   - $\varepsilon$-NTU effectiveness models across diverse flow topologies with zero phantom duty at $UA \to 0$.
   - 1D numerical segmented finite-volume solver cross-checks.

2. **Organic Rankine Cycle (ORC) Power Simulation:**
   - Helmholtz energy real-fluid EOS via CoolProp (Cyclopentane, Pentane, Butane, R245fa, Toluene).
   - Multi-stage heat addition: Sensible superheating, pool boiling kettle evaporation, and liquid preheating.
   - Enforces First Law mass flow scaling:
     $$m_{cp,actual} = \min(m_{cp}, Q_{orc} / \Delta h_{req})$$
   - Turbine expansion power ($W_{mech}, W_{el}$) with Second Law Carnot limits:
     $$W_{turb} \le Q_{orc} \cdot \eta_{carnot} \cdot 0.85$$

3. **Multi-WHRU Waste Heat Recovery Trains:**
   - Hydraulic balancing and heat distribution across 1 to 5 parallel boilers.
   - Acid dew point safety ($T_{flue,out} > 130-140^\circ\text{C}$).
   - Live flue-to-oil pinch evaluation: $\Delta T_{pinch} = T_{flue,out} - T_{oil,in} \ge 15^\circ\text{C}$.

4. **Hydraulics & Cavitation Prevention:**
   - Darcy-Weisbach and Swamee-Jain head loss across pipe networks with smooth transition zone ($2300 \le Re < 4000$).
   - Circulation pump $NPSHa$ vs $NPSHr$ margin calculation using dynamic Eastman vapor pressure correlations.

## How to Use

Invoke this skill when optimizing cycle efficiency, troubleshooting heat transfer bottlenecks, verifying energy conservation, or analyzing multi-stage heat recovery systems.
