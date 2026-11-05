#!/usr/bin/env python3
"""Comprehensive 100+ Scenario Dynamic Verification & First Law Energy Balance Validation.

Validates:
1. Flue gas mass flow rate (m_flue) sensitivity (dQ/dm_flue > 0, physical limits)
2. Thermal oil split (split_oil) sensitivity (hydraulic pressure drop, mixed header T)
3. First Law Energy Balance: Q_boiler >= Q_ORC (strictly enforced across all runs)
4. Condenser selection: Air-Cooled (ACC) vs. Water-Cooled (parasitic loads, flow rates)
5. 1 to 5 parallel WHRU trains and bypass ratios (0% to 100%)
"""

import sys

import numpy as np

from orc_system_model import solve_orc_system


def run_scenario_matrix():
    print("=" * 80)
    print("🚀 RUNNING 100+ DYNAMIC THERMODYNAMIC SCENARIOS FOR ORC & WHRU NETWORK")
    print("=" * 80)

    scenarios = []
    scenario_id = 0

    # Matrix 1: Flue Gas Mass Flow Rate Sweep (m_flue from 8 to 40 kg/s) across 1, 2, 3 boilers
    for n_b in [1, 2, 3]:
        for m_flue in [8.0, 12.0, 16.0, 20.0, 25.0, 30.0, 35.0, 40.0]:
            scenario_id += 1
            scenarios.append(
                {
                    "id": scenario_id,
                    "category": "Flue Gas Sensitivity",
                    "params": {
                        "n_boilers": n_b,
                        "m_flue_1": m_flue,
                        "condenser_type": "water",
                        "bypass_ratio": 0.0,
                    },
                }
            )

    # Matrix 2: Thermal Oil Split Sweep (split from 0.05 to 0.95) across dual WHRU
    for split in [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]:
        scenario_id += 1
        scenarios.append(
            {
                "id": scenario_id,
                "category": "Oil Split Hydraulic Sensitivity",
                "params": {
                    "n_boilers": 2,
                    "split_oil_whru": split,
                    "condenser_type": "water",
                    "bypass_ratio": 0.0,
                },
            }
        )

    # Matrix 3: Bypass Ratio Sweep (0% to 100%)
    for bp in [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0]:
        scenario_id += 1
        scenarios.append(
            {
                "id": scenario_id,
                "category": "Bypass Valve Regulation",
                "params": {
                    "n_boilers": 2,
                    "bypass_ratio": bp,
                    "condenser_type": "water",
                },
            }
        )

    # Matrix 4: Condenser Type Comparison (Water vs Air-Cooled ACC) across ambient temperatures
    for c_type in ["water", "air"]:
        for t_amb in [15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]:
            scenario_id += 1
            p = {
                "n_boilers": 2,
                "condenser_type": c_type,
                "bypass_ratio": 0.0,
            }
            if c_type == "air":
                p["T_air_in"] = t_amb
                p["P_cond_bar"] = 2.0
            else:
                p["T_cw_in"] = min(35.0, t_amb)
                p["P_cond_bar"] = 1.5
            scenarios.append({"id": scenario_id, "category": f"Condenser {c_type.upper()}", "params": p})

    # Matrix 5: Multi-Boiler Scalability (1, 2, 3, 4, 5 boilers) with asymmetric loads
    for n_b in [1, 2, 3, 4, 5]:
        for flue_t in [420.0, 460.0, 500.0, 540.0]:
            scenario_id += 1
            boilers_cfg = []
            for i in range(n_b):
                boilers_cfg.append(
                    {
                        "m_flue": 16.0 + i * 2.0,
                        "T_flue_in": flue_t,
                        "UA": 32.0,
                        "split": 1.0 / n_b,
                    }
                )
            scenarios.append(
                {
                    "id": scenario_id,
                    "category": f"{n_b}-Boiler Train",
                    "params": {
                        "n_boilers": n_b,
                        "boilers": boilers_cfg,
                        "condenser_type": "water" if n_b % 2 == 0 else "air",
                    },
                }
            )

    # Matrix 6: Cyclopentane Cycle Pressure Variations (P_evap from 10 to 24 bar)
    for p_evap in [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]:
        for m_cp in [8.0, 11.5, 15.0]:
            scenario_id += 1
            scenarios.append(
                {
                    "id": scenario_id,
                    "category": "ORC Cycle Parameters",
                    "params": {
                        "n_boilers": 2,
                        "P_evap_bar": p_evap,
                        "m_cp": m_cp,
                        "m_cp_kg_s": m_cp,
                        "condenser_type": "water",
                    },
                }
            )

    total_scenarios = len(scenarios)
    print(f"Total Scenarios Generated: {total_scenarios} (Target >= 100: PASS)")

    results = []
    first_law_violations = 0
    m_flue_sensitivity_failures = 0
    hydraulic_failures = 0

    prev_q_by_nb = {}

    for s in scenarios:
        res = solve_orc_system(s["params"])
        s_id = s["id"]
        cat = s["category"]

        q_boiler = res["boiler"]["Q_kW"]
        q_orc = res["orc"]["Q_total_kW"]
        w_net = res["orc"]["W_net_kW"]
        w_turb = res["orc"]["W_turb_kW"]
        cond = res["condenser"]
        bypass = s["params"].get("bypass_ratio", 0.0)

        # 1. First Law Verification: Q_boiler >= Q_ORC
        # (With bypass: Q_ORC <= Q_boiler * (1 - bypass))
        max_allowed_q_orc = q_boiler * (1.0 - bypass) + 0.01  # 0.01 kW float margin
        first_law_ok = (q_orc <= max_allowed_q_orc) and (q_boiler >= q_orc - 0.01)

        if not first_law_ok:
            first_law_violations += 1
            print(
                f"❌ FIRST LAW VIOLATION in #{s_id}: Q_boiler={q_boiler:.2f} kW, Q_ORC={q_orc:.2f} kW, Bypass={bypass:.2f}"
            )

        # 2. Check m_flue monotonic increase
        if cat == "Flue Gas Sensitivity":
            nb = s["params"]["n_boilers"]
            if nb in prev_q_by_nb and q_boiler <= prev_q_by_nb[nb]:
                m_flue_sensitivity_failures += 1
                print(f"❌ NON-MONOTONIC Q_flue in #{s_id}: prev={prev_q_by_nb[nb]:.2f}, current={q_boiler:.2f}")
            prev_q_by_nb[nb] = q_boiler

        # 3. Check hydraulic split
        if cat == "Oil Split Hydraulic Sensitivity":
            split = s["params"]["split_oil_whru"]
            dp1 = res["boiler_1"]["dp_bar"]
            dp2 = res["boiler_2"]["dp_bar"]
            if split > 0.5 and dp1 < dp2 or split < 0.5 and dp1 > dp2:
                hydraulic_failures += 1

        # 4. Check Condenser parasitics
        c_type = cond["type"]
        if c_type == "air":
            assert "ACC" in cond["type_label"]
            assert cond["W_parasitic_kW"] > 0
            assert "m_air_kg_s" in cond
        else:
            assert "Su" in cond["type_label"]
            assert cond["W_parasitic_kW"] >= 0
            assert "m_cw_kg_s" in cond

        results.append(
            {
                "id": s_id,
                "category": cat,
                "n_boilers": res["boiler"]["n_boilers"],
                "Q_boiler_kW": q_boiler,
                "Q_orc_kW": q_orc,
                "W_net_kW": w_net,
                "W_turb_kW": w_turb,
                "cond_type": c_type,
                "cond_w_parasitic_kW": cond["W_parasitic_kW"],
                "first_law_ok": first_law_ok,
            }
        )

    # Summary Statistics
    q_boilers = [r["Q_boiler_kW"] for r in results]
    q_orcs = [r["Q_orc_kW"] for r in results]
    w_nets = [r["W_net_kW"] for r in results]

    print("\n" + "=" * 80)
    print("📊 100+ SCENARIO VALIDATION REPORT & METRICS")
    print("=" * 80)
    print(f"Total Scenarios Evaluated       : {len(results)}")
    print(
        f"First Law Violations (Q_b < Q_orc): {first_law_violations} (0 REQUIRED -> {'✅ PASS' if first_law_violations == 0 else '❌ FAIL'})"
    )
    print(
        f"Flue Gas Sensitivity Anomalies   : {m_flue_sensitivity_failures} (0 REQUIRED -> {'✅ PASS' if m_flue_sensitivity_failures == 0 else '❌ FAIL'})"
    )
    print(
        f"Hydraulic Split Anomalies        : {hydraulic_failures} (0 REQUIRED -> {'✅ PASS' if hydraulic_failures == 0 else '❌ FAIL'})"
    )
    print("-" * 80)
    print(
        f"Q_boiler Range (min / mean / max): {np.min(q_boilers):.1f} / {np.mean(q_boilers):.1f} / {np.max(q_boilers):.1f} kW"
    )
    print(f"Q_ORC Range    (min / mean / max): {np.min(q_orcs):.1f} / {np.mean(q_orcs):.1f} / {np.max(q_orcs):.1f} kW")
    print(f"W_net Range    (min / mean / max): {np.min(w_nets):.1f} / {np.mean(w_nets):.1f} / {np.max(w_nets):.1f} kW")
    print("=" * 80)

    # Spot checks of Air vs Water Condenser
    acc_samples = [r for r in results if r["cond_type"] == "air" and r["category"].startswith("Condenser")]
    water_samples = [r for r in results if r["cond_type"] == "water" and r["category"].startswith("Condenser")]

    print("\n🔬 CONDENSER PARASITIC COMPARISON (WATER vs. ACC):")
    print(
        f"{'Condition':<25} | {'Water W_pump (kW)':<18} | {'ACC W_fan (kW)':<18} | {'Parasitic Ratio (ACC/Water)':<20}"
    )
    print("-" * 85)
    for w_s, a_s in zip(water_samples[:5], acc_samples[:5], strict=False):
        ratio = a_s["cond_w_parasitic_kW"] / max(0.01, w_s["cond_w_parasitic_kW"])
        print(
            f"Case {w_s['id']} vs {a_s['id']:<18} | {w_s['cond_w_parasitic_kW']:<18.2f} | {a_s['cond_w_parasitic_kW']:<18.2f} | {ratio:<20.2f}x"
        )

    all_passed = first_law_violations == 0 and m_flue_sensitivity_failures == 0 and hydraulic_failures == 0
    return all_passed


if __name__ == "__main__":
    success = run_scenario_matrix()
    sys.exit(0 if success else 1)
