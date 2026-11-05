"""Unit tests for the ORC and Thermal Oil Network Thermodynamic Model (orc_system_model.py)."""

import unittest

from orc_system_model import (
    cyclopentane_hfg,
    cyclopentane_tsat,
    solve_orc_system,
    therminol66_cp,
    therminol66_density,
)


class TestOrcSystemModel(unittest.TestCase):
    """Verify thermodynamic equations, series heat exchanger network and bypass valve behavior."""

    def test_therminol66_properties(self):
        cp_100 = therminol66_cp(100.0)
        cp_300 = therminol66_cp(300.0)
        self.assertGreater(cp_300, cp_100)
        self.assertGreater(cp_100, 1500.0)

        rho_100 = therminol66_density(100.0)
        rho_300 = therminol66_density(300.0)
        self.assertLess(rho_300, rho_100)
        self.assertGreater(rho_300, 750.0)

    def test_cyclopentane_saturation(self):
        t_sat_10 = cyclopentane_tsat(10.0)
        t_sat_20 = cyclopentane_tsat(20.0)
        self.assertGreater(t_sat_20, t_sat_10)
        self.assertAlmostEqual(t_sat_10, 140.0, delta=10.0)

        hfg_140 = cyclopentane_hfg(140.0)
        hfg_180 = cyclopentane_hfg(180.0)
        self.assertGreater(hfg_140, hfg_180)
        self.assertGreater(hfg_140, 200000.0)

    def test_nominal_orc_solve(self):
        res = solve_orc_system()
        # Verify component keys
        self.assertIn("boiler", res)
        self.assertIn("superheater", res)
        self.assertIn("preheater", res)
        self.assertIn("pump", res)
        self.assertIn("bypass_valve", res)
        self.assertIn("orc", res)

        # Series connection check:
        # Oil enters superheater at boiler supply temp
        self.assertAlmostEqual(res["superheater"]["T_oil_in_C"], res["boiler"]["T_oil_out_C"], delta=0.5)
        # Oil enters evaporator at superheater exit temp
        self.assertAlmostEqual(res["evaporator"]["T_oil_in_C"], res["superheater"]["T_oil_out_C"], delta=0.5)
        # Oil enters preheater at evaporator exit temp
        self.assertAlmostEqual(res["preheater"]["T_oil_in_C"], res["evaporator"]["T_oil_out_C"], delta=0.5)

        # Thermal hierarchy: T_oil_supply > T_oil_mid > T_oil_ret
        self.assertGreater(res["boiler"]["T_oil_out_C"], res["superheater"]["T_oil_out_C"])
        self.assertGreater(res["superheater"]["T_oil_out_C"], res["preheater"]["T_oil_out_C"])

        # Heat and power values positive
        self.assertGreater(res["boiler"]["Q_kW"], 1000.0)
        self.assertGreater(res["orc"]["W_net_kW"], 100.0)
        self.assertGreater(res["pump"]["W_el_kW"], 5.0)

    def test_bypass_valve_behavior(self):
        # 0% bypass: full heat transferred to ORC
        res_0 = solve_orc_system({"bypass_ratio": 0.0})
        # 50% bypass: lower active flow, lower ORC heat
        res_50 = solve_orc_system({"bypass_ratio": 0.5})
        # 100% bypass: no oil to ORC, ORC heat zero
        res_100 = solve_orc_system({"bypass_ratio": 1.0})

        self.assertGreater(res_0["orc"]["Q_total_kW"], res_50["orc"]["Q_total_kW"])
        self.assertEqual(res_100["orc"]["Q_total_kW"], 0.0)
        self.assertEqual(res_100["superheater"]["Q_kW"], 0.0)
        self.assertEqual(res_100["preheater"]["Q_kW"], 0.0)
        self.assertAlmostEqual(res_100["boiler"]["T_oil_in_C"], res_100["boiler"]["T_oil_out_C"], delta=2.0)

    def test_cyclopentane_superheat(self):
        res = solve_orc_system({"P_evap_bar": 15.0})
        t_sat = res["orc"]["T_sat_C"]
        t_sup = res["orc"]["T_sup_C"]
        self.assertGreater(t_sup, t_sat)
        self.assertGreater(t_sat, 140.0)

    def test_cyclopentane_properties_real_fluid(self):
        from orc_system_model import cyclopentane_properties

        props = cyclopentane_properties(14.0, t_sup_c=210.0, t_in_c=45.0, p_cond_bar=1.5)
        self.assertAlmostEqual(props["T_sat_C"], 160.0, delta=1.5)
        self.assertGreater(props["h_fg"], 200000.0)
        self.assertGreater(props["dh_is"], 80000.0)
        self.assertIn("engine", props)

    def test_orc_3zone_and_pinch_point(self):
        res = solve_orc_system()
        # Verify 3-zone structure
        self.assertIn("evaporator", res)
        evap = res["evaporator"]
        ph = res["preheater"]
        sh = res["superheater"]
        orc = res["orc"]

        # Heat balance: Q_orc == Q_sh + Q_evap + Q_sensible
        q_sum = round(sh["Q_kW"] + evap["Q_kW"] + ph["Q_sensible_kW"], 1)
        self.assertAlmostEqual(orc["Q_total_kW"], q_sum, delta=0.5)

        # Thermal cascade: T_oil_supply > T_oil_mid > T_oil_evap_out > T_oil_ret
        self.assertGreater(sh["T_oil_in_C"], sh["T_oil_out_C"])
        self.assertGreater(sh["T_oil_out_C"], evap["T_oil_out_C"])
        self.assertGreater(evap["T_oil_out_C"], ph["T_oil_out_C"])

        # Healthy nominal pinch point
        self.assertGreater(orc["delta_T_pinch_C"], 15.0)
        self.assertFalse(orc["pinch_warning"])
        self.assertIn("thermo_engine", orc)

    def test_pinch_point_violation_detection(self):
        # Low flue temperature and high evaporation pressure to trigger pinch limit
        res_pinched = solve_orc_system(
            {
                "T_flue_in": 340.0,
                "P_evap_bar": 28.0,
                "m_oil": 20.0,
                "UA_ph_kW_K": 80.0,
            }
        )
        self.assertLess(res_pinched["orc"]["delta_T_pinch_C"], 5.0)
        self.assertTrue(res_pinched["orc"]["pinch_warning"])

    def test_orc_condenser_and_npsh(self):
        res = solve_orc_system()
        # Verify Condenser
        self.assertIn("condenser", res)
        cond = res["condenser"]
        self.assertGreater(cond["Q_kW"], 1000.0)
        self.assertGreater(cond["subcooling_K"], 5.0)
        self.assertGreater(cond["m_cw_kg_s"], 10.0)

        # First Law Thermal Balance: Q_orc - W_turb_mech == Q_cond
        self.assertAlmostEqual(res["orc"]["Q_total_kW"] - res["orc"]["W_turb_mech_kW"], cond["Q_kW"], delta=0.5)

        # Verify Pump NPSH
        self.assertIn("feed_pump", res)
        p_oil = res["pump"]
        p_cp = res["feed_pump"]
        self.assertGreater(p_oil["NPSH_margin_m"], 5.0)
        self.assertFalse(p_oil["cavitation_warning"])
        self.assertGreater(p_cp["NPSH_margin_m"], 2.0)
        self.assertFalse(p_cp["cavitation_warning"])

    def test_feed_pump_cavitation_on_lost_subcooling(self):
        # Feed liquid enters at 61.5 C (virtually at Tsat of 1.5 bar)
        res_loss = solve_orc_system({"T_cp_in": 61.5})
        # Lost subcooling dramatically lowers suction pressure margin
        self.assertLess(res_loss["feed_pump"]["NPSH_margin_m"], 1.5)

    def test_dual_whru_solve(self):
        # 1. Symmetric 50/50 Dual WHRU solve
        res_sym = solve_orc_system({"enable_dual_whru": True})
        self.assertTrue(res_sym["boiler"]["dual_whru"])
        self.assertIn("boiler_1", res_sym)
        self.assertIn("boiler_2", res_sym)

        b1 = res_sym["boiler_1"]
        b2 = res_sym["boiler_2"]
        b_comb = res_sym["boiler"]

        # Combined heat matches sum of individual boilers
        self.assertAlmostEqual(b_comb["Q_kW"], b1["Q_kW"] + b2["Q_kW"], delta=0.1)
        self.assertGreater(b1["Q_kW"], 500.0)
        self.assertGreater(b2["Q_kW"], 500.0)
        self.assertAlmostEqual(b1["m_oil_kg_s"], b2["m_oil_kg_s"], delta=0.1)
        self.assertAlmostEqual(b1["T_oil_out_C"], b2["T_oil_out_C"], delta=0.5)
        self.assertAlmostEqual(b_comb["T_oil_out_C"], b1["T_oil_out_C"], delta=0.5)

        # Hydraulic friction & balancing
        self.assertIn("dp_parallel_bar", b_comb)
        self.assertIn("dp_bar", b1)
        self.assertIn("dp_bar", b2)
        self.assertGreater(b1["dp_bar"], 0.1)
        self.assertGreater(b2["dp_bar"], 0.1)
        self.assertAlmostEqual(b1["dp_bar"], b2["dp_bar"], delta=0.05)
        self.assertAlmostEqual(b_comb["dp_balance_diff_bar"], 0.0, delta=0.05)

        # 2. Asymmetric flow split (70% WHRU-1 / 30% WHRU-2)
        res_asym = solve_orc_system({"enable_dual_whru": True, "split_oil_whru": 0.70})
        b1_asym = res_asym["boiler_1"]
        b2_asym = res_asym["boiler_2"]
        self.assertGreater(b1_asym["m_oil_kg_s"], b2_asym["m_oil_kg_s"])
        self.assertAlmostEqual(b1_asym["split_oil_pct"], 70.0, delta=0.5)
        self.assertAlmostEqual(b2_asym["split_oil_pct"], 30.0, delta=0.5)
        self.assertGreater(b1_asym["dp_bar"], b2_asym["dp_bar"])
        self.assertGreater(res_asym["boiler"]["dp_balance_diff_bar"], 0.1)

        m1 = b1_asym["m_oil_kg_s"]
        m2 = b2_asym["m_oil_kg_s"]
        t_mix_expected = (m1 * b1_asym["T_oil_out_C"] + m2 * b2_asym["T_oil_out_C"]) / (m1 + m2)
        self.assertAlmostEqual(res_asym["boiler"]["T_oil_out_C"], t_mix_expected, delta=0.2)

        # 3. Isolation of Boiler 2 for maintenance (100% WHRU-1)
        res_iso = solve_orc_system({"enable_dual_whru": True, "split_oil_whru": 1.0})
        self.assertEqual(res_iso["boiler_2"]["Q_kW"], 0.0)
        self.assertEqual(res_iso["boiler_2"]["m_oil_kg_s"], 0.0)
        self.assertEqual(res_iso["boiler_2"]["dp_bar"], 0.0)
        self.assertAlmostEqual(res_iso["boiler"]["Q_kW"], res_iso["boiler_1"]["Q_kW"], delta=0.1)

    def test_n_boilers_scaling(self):
        # Test 3-Boiler configuration
        res_3 = solve_orc_system({"n_boilers": 3})
        self.assertEqual(res_3["boiler"]["n_boilers"], 3)
        self.assertEqual(len(res_3["boilers"]), 3)
        sum_q_3 = sum(b["Q_kW"] for b in res_3["boilers"])
        self.assertAlmostEqual(res_3["boiler"]["Q_kW"], sum_q_3, delta=0.2)
        self.assertGreater(res_3["orc"]["W_net_kW"], 400.0)

        # Test 5-Boiler configuration
        res_5 = solve_orc_system({"n_boilers": 5})
        self.assertEqual(res_5["boiler"]["n_boilers"], 5)
        self.assertEqual(len(res_5["boilers"]), 5)
        sum_q_5 = sum(b["Q_kW"] for b in res_5["boilers"])
        self.assertAlmostEqual(res_5["boiler"]["Q_kW"], sum_q_5, delta=0.2)
        # Symmetrical split by default: oil flow per boiler = 32 / 5 = 6.4 kg/s
        for b in res_5["boilers"]:
            self.assertAlmostEqual(b["m_oil_kg_s"], 32.0 / 5.0, delta=0.01)
            self.assertGreater(b["Q_kW"], 500.0)

    def test_schematic_html_equipment_nodes(self):
        import orc_schematic_component

        html = orc_schematic_component.get_orc_schematic_html()
        self.assertIn('viewBox="0 0 1520 620"', html)
        self.assertIn("node_boiler_1", html)
        self.assertIn("node_boiler_2", html)
        self.assertIn("node_boiler_3", html)
        self.assertIn("node_boiler_4", html)
        self.assertIn("node_boiler_5", html)
        self.assertIn("WHRU-1", html)
        self.assertIn("WHRU-2", html)
        self.assertIn("WHRU-3", html)
        self.assertIn("btn_mode_single", html)
        self.assertIn("btn_mode_dual", html)
        self.assertIn("btn_add_whru", html)
        self.assertIn("btn_remove_whru", html)
        self.assertIn("whru2-element", html)
        self.assertIn("whru3-element", html)
        self.assertIn("badge_hydraulics", html)
        self.assertIn("setBoilerMode", html)
        self.assertIn("setBoilerCount", html)
        self.assertIn("pipe_cold_manifold", html)
        self.assertIn("pipe_oil_sup_b1", html)
        self.assertIn("node_valve", html)
        self.assertIn("node_sh", html)
        self.assertIn("node_ph", html)
        self.assertIn("node_pump", html)
        self.assertIn("node_turbine", html)
        self.assertIn("node_condenser", html)
        self.assertIn("node_cp_pump", html)
        self.assertIn("Serpantini", html)
        self.assertIn("TEMA Shell &amp; Tube", html)
        self.assertIn("Kettle Reboiler", html)
        self.assertIn("txt_oil_sup_fluid", html)
        self.assertIn("txt_oil_mid_fluid", html)
        self.assertIn("txt_oil_ret_fluid", html)
        self.assertIn("txt_cp_sup_fluid", html)
        self.assertIn("txt_cp_vap_fluid", html)
        self.assertIn("txt_cw_fluid", html)
        self.assertIn("param-num-input", html)
        self.assertIn("param-slider", html)
        self.assertIn("onParamInput", html)

    def test_exchanger_3d_component_generation(self):
        from exchanger_3d_component import get_exchanger_3d_html

        geom_input = {
            "D_o_mm": 25.4,
            "D_i_mm": 21.1,
            "L_m": 3.0,
            "N_tubes": 80,
            "D_shell_mm": 350.0,
            "baffle_spacing_mm": 150.0,
            "tube_material": "Karbon Çelik (k=45)",
            "is_finned": False,
        }
        html = get_exchanger_3d_html(geom_input)
        self.assertIn("canvas3d", html)
        self.assertIn("rng_explode", html)
        self.assertIn("setCutawayMode", html)
        self.assertIn("toggleFlow", html)
        self.assertIn("onExplodeChange", html)
        self.assertIn("25.4", html)
        self.assertIn("350.0", html)
        self.assertIn("Karbon Çelik", html)
        self.assertGreater(len(html), 5000)

    def test_100_dynamic_scenarios_and_first_law(self):
        """Execute >= 100 parametric scenarios verifying flue gas sensitivity, hydraulic split, and Q_boiler >= Q_ORC."""
        from verify_100_scenarios import run_scenario_matrix

        success = run_scenario_matrix()
        self.assertTrue(success, "At least one thermodynamic check failed in the 100+ scenario matrix")

    def test_condenser_selection_acc_vs_water(self):
        """Verify Air-Cooled Condenser vs Water-Cooled Condenser inputs, outputs and parasitics."""
        # Water-Cooled
        res_water = solve_orc_system({"condenser_type": "water", "T_cw_in": 25.0, "P_cond_bar": 1.5})
        cond_w = res_water["condenser"]
        self.assertEqual(cond_w["type"], "water")
        self.assertIn("Su", cond_w["type_label"])
        self.assertGreater(cond_w["m_cw_kg_s"], 0.0)
        self.assertEqual(cond_w["W_fan_kW"], 0.0)
        self.assertGreater(cond_w["W_cw_pump_kW"], 0.0)

        # Air-Cooled (ACC)
        res_acc = solve_orc_system({"condenser_type": "air", "T_air_in": 32.0, "P_cond_bar": 2.0})
        cond_a = res_acc["condenser"]
        self.assertEqual(cond_a["type"], "air")
        self.assertIn("ACC", cond_a["type_label"])
        self.assertGreater(cond_a["m_air_kg_s"], 0.0)
        self.assertGreater(cond_a["W_fan_kW"], 0.0)
        self.assertEqual(cond_a["W_cw_pump_kW"], 0.0)
        self.assertGreater(cond_a["fan_count"], 0)

        # Energy balance: Q_boiler >= Q_ORC in both
        self.assertGreaterEqual(res_water["boiler"]["Q_kW"], res_water["orc"]["Q_total_kW"] - 0.01)
        self.assertGreaterEqual(res_acc["boiler"]["Q_kW"], res_acc["orc"]["Q_total_kW"] - 0.01)

    def test_superheater_oil_inlet_override_and_pipe_loss(self):
        """Verify SH thermal oil manual inlet temperature override and pipeline heat loss calculations."""
        # 1. Base automatic mode: pipe loss = 0, T_oil_sh_in == T_oil_supply
        res_auto = solve_orc_system({"n_boilers": 2, "bypass_ratio": 0.0})
        t_supply_auto = res_auto["boiler"]["T_oil_out_C"]
        self.assertAlmostEqual(res_auto["superheater"]["T_oil_in_C"], t_supply_auto, delta=0.5)
        self.assertEqual(res_auto["superheater"]["delta_T_pipe_loss_C"], 0.0)
        self.assertEqual(res_auto["superheater"]["Q_pipe_loss_kW"], 0.0)

        # 2. Manual SH inlet temperature override: T_oil_sh_in = 275.0 °C (< T_supply ~295 °C)
        res_manual = solve_orc_system({"n_boilers": 2, "bypass_ratio": 0.0, "T_oil_sh_in_C": 275.0})
        self.assertAlmostEqual(res_manual["superheater"]["T_oil_in_C"], 275.0, delta=0.1)
        self.assertGreater(res_manual["superheater"]["delta_T_pipe_loss_C"], 5.0)
        self.assertGreater(res_manual["superheater"]["Q_pipe_loss_kW"], 100.0)
        # Superheater heat duty must be lower due to cooler oil entering SH
        self.assertLess(res_manual["superheater"]["Q_kW"], res_auto["superheater"]["Q_kW"])
        # First Law with line loss: Q_boiler >= Q_ORC + Q_pipe_loss
        self.assertGreaterEqual(
            res_manual["boiler"]["Q_kW"],
            res_manual["orc"]["Q_total_kW"] + res_manual["superheater"]["Q_pipe_loss_kW"] - 0.2,
        )

        # 3. Pipeline temperature drop mode: delta_T_pipe_loss_C = 8.0 °C
        res_loss = solve_orc_system({"n_boilers": 2, "bypass_ratio": 0.0, "delta_T_pipe_loss_C": 8.0})
        t_supply_loss = res_loss["boiler"]["T_oil_out_C"]
        self.assertAlmostEqual(res_loss["superheater"]["T_oil_in_C"], t_supply_loss - 8.0, delta=0.2)
        self.assertAlmostEqual(res_loss["superheater"]["delta_T_pipe_loss_C"], 8.0, delta=0.1)
        self.assertGreater(res_loss["superheater"]["Q_pipe_loss_kW"], 200.0)

    def test_multi_whru_manifold_and_flow_visualizations(self):
        """Verify multi-WHRU cold distribution and hot collection manifolds in SVG and interactive controls."""
        import orc_schematic_component

        html = orc_schematic_component.get_orc_schematic_html(
            {
                "n_boilers": 3,
                "T_oil_sh_in_C": 280.0,
                "delta_T_pipe_loss_C": 10.0,
            }
        )
        # Check hot collection manifold header (y=80) and risers
        self.assertIn("pipe_oil_sup_manifold", html)
        self.assertIn("pipe_oil_sup_b1", html)
        self.assertIn("pipe_hot_b2_group", html)
        self.assertIn("pipe_hot_b3_group", html)
        # Check cold distribution manifold header (y=275) and risers
        self.assertIn("pipe_cold_header_base", html)
        self.assertIn("pipe_cold_b1_group", html)
        self.assertIn("pipe_cold_b2_group", html)
        self.assertIn("pipe_cold_b3_group", html)
        # Check upward flow animations and SH inlet badge
        self.assertIn("badge_line_sh_in", html)
        self.assertIn("setShInletMode", html)
        self.assertIn("pipe-flow", html)


if __name__ == "__main__":
    unittest.main()
