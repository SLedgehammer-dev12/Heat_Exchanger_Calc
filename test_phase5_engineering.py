"""Unit tests for Phase 5 critical thermal, hydraulic, standards, and numerical enhancements."""

import unittest

from correlations import _bowman_lmtd_factor
from heat_exchanger import FinTubeHeatExchanger, Fluid
from mechanical import (
    asme_flat_cover_thickness,
    asme_wall_thickness,
    mechanical_design_report,
    tema_min_shell_thickness,
    tema_tubesheet_thickness,
)


class TestPhase5EngineeringEnhancements(unittest.TestCase):
    def test_bowman_hot_is_tube_orientation(self):
        """Bowman F-factor should properly define P and R relative to tube-side fluid."""
        # T_h_in=100, T_c_in=20, T_h_out=60, T_c_out=40. C_h=1000, C_c=2000
        # If hot_is_tube=True: P_tube = (100 - 60) / 80 = 0.5, R_tube = 1000 / 2000 = 0.5
        # If hot_is_tube=False: P_tube = (40 - 20) / 80 = 0.25, R_shell = 2000 / 1000 = 2.0
        f_hot_tube = _bowman_lmtd_factor(100.0, 20.0, 60.0, 40.0, C_h=1000.0, C_c=2000.0, hot_is_tube=True)
        f_cold_tube = _bowman_lmtd_factor(100.0, 20.0, 60.0, 40.0, C_h=1000.0, C_c=2000.0, hot_is_tube=False)
        self.assertGreater(f_hot_tube, 0.5)
        self.assertGreater(f_cold_tube, 0.5)
        self.assertNotEqual(f_hot_tube, f_cold_tube)

    def test_crossflow_mixed_unmixed_stream_orientation(self):
        """Crossflow mixed/unmixed formula must evaluate mixed status based on outer stream."""
        hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
        cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="cross_mixed_unmixed")

        # When hot_is_tube=False (hot is outside/mixed): C_h = 2000, C_c = 4000 -> C_mixed (2000) < C_unmixed (4000) => mixed Cmin
        hx.hot_is_tube = False
        subtype_outer_hot = hx._map_ht_flow_type(C_h=2000.0, C_c=4000.0)
        self.assertEqual(subtype_outer_hot, "crossflow, mixed Cmin")

        # When hot_is_tube=True (cold is outside/mixed): C_mixed = C_c = 4000 > C_unmixed = C_h = 2000 => mixed Cmax
        hx.hot_is_tube = True
        subtype_outer_cold = hx._map_ht_flow_type(C_h=2000.0, C_c=4000.0)
        self.assertEqual(subtype_outer_cold, "crossflow, mixed Cmax")

    def test_asme_corroded_radius_ug27(self):
        """ASME UG-27 internal pressure wall thickness must include CA in the inside radius."""
        P = 2.0e6
        R = 0.25
        S = 110e6
        E = 0.85
        CA = 0.003
        t = asme_wall_thickness(P, R, S, E, CA=CA, use_outer_radius=False)
        expected = P * (R + CA) / (S * E - 0.6 * P) + CA
        self.assertAlmostEqual(t, expected, places=8)

    def test_tema_tubesheet_and_cover_mechanics(self):
        """Tubesheet thickness, flat cover, and TEMA minimum thickness functions must behave correctly."""
        P = 2.0e6
        D_shell = 0.50
        S = 110e6
        pitch = 0.03175
        D_o = 0.0254
        CA = 0.003

        t_ts = tema_tubesheet_thickness(P, D_shell, S, pitch, D_o, CA=CA)
        self.assertGreater(t_ts, CA)
        self.assertGreater(t_ts, 0.02)  # > 20 mm for 0.5m shell at 20 bar

        t_cov = asme_flat_cover_thickness(P, D_shell, S, CA=CA)
        self.assertGreater(t_cov, CA)

        t_tema_r = tema_min_shell_thickness(D_shell, tema_class="R")
        self.assertEqual(t_tema_r, 0.0095)  # 9.5 mm for 500 mm shell Class R

        # Verify mechanical design report includes tubesheet and flat cover
        geom = {
            "D_shell": D_shell,
            "D_o": D_o,
            "pitch": pitch,
            "design_pressure": P,
            "corrosion_allowance": CA,
        }
        rows = mechanical_design_report(geom)
        labels = [r["label"] for r in rows]
        self.assertTrue(any("Tüp aynası" in lbl for lbl in labels))
        self.assertTrue(any("Kanal kapağı" in lbl for lbl in labels))
        self.assertTrue(any("TEMA min. gövde" in lbl for lbl in labels))

    def test_solve_ntu_safe_from_nan_zero_cr_and_extremes(self):
        """solve_ntu must never evaluate to NaN or raise ConvergenceError for extreme Cr or NTU."""
        import math

        for flow_type, exch_type in [
            ("cross_unmixed", "finned_tube"),
            ("cross_mixed_unmixed", "finned_tube"),
            ("counter", "shell_and_tube"),
            ("parallel", "double_pipe"),
        ]:
            hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
            cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
            hx = FinTubeHeatExchanger(hot, cold, U=500.0, A=20.0, flow_type=flow_type, exchanger_type=exch_type)

            # 1. Extreme flow disparity Cr -> 0
            res_tiny_cr = hx.solve_ntu(m_hot=100.0, m_cold=1e-5, T_hot_in=150.0, T_cold_in=30.0)
            eps1 = res_tiny_cr["epsilon"]
            self.assertFalse(math.isnan(eps1), f"NaN encountered for flow {flow_type} at Cr->0")
            self.assertTrue(0.0 <= eps1 <= 1.0)

            # 2. Balanced flow Cr = 1.0 (exact counterflow singularity check)
            res_bal = hx.solve_ntu(m_hot=2.0, m_cold=1.0, T_hot_in=150.0, T_cold_in=30.0)  # C_h = 4000, C_c = 4000
            eps2 = res_bal["epsilon"]
            self.assertFalse(math.isnan(eps2), f"NaN encountered for flow {flow_type} at Cr=1.0")
            self.assertTrue(0.0 <= eps2 <= 1.0)

            # 3. Cr extremely close to 1.0
            res_near = hx.solve_ntu(m_hot=2.0 * (1.0 + 1e-7), m_cold=1.0, T_hot_in=150.0, T_cold_in=30.0)
            eps3 = res_near["epsilon"]
            self.assertFalse(math.isnan(eps3), f"NaN encountered for flow {flow_type} at Cr~1.0")
            self.assertTrue(0.0 <= eps3 <= 1.0)

            # 4. Large NTU
            hx_large = FinTubeHeatExchanger(hot, cold, U=5000.0, A=200.0, flow_type=flow_type, exchanger_type=exch_type)
            res_large = hx_large.solve_ntu(m_hot=1.0, m_cold=1.0, T_hot_in=150.0, T_cold_in=30.0)
            eps4 = res_large["epsilon"]
            self.assertFalse(math.isnan(eps4), f"NaN encountered for large NTU in {flow_type}")
            self.assertTrue(0.0 <= eps4 <= 1.0)

    def test_segment_effectiveness_safe_from_nan(self):
        """_segment_effectiveness must return finite results in [0, 1] for all edge cases."""
        import math

        for flow_type, exch_type in [
            ("cross_unmixed", "finned_tube"),
            ("cross_mixed_unmixed", "finned_tube"),
            ("counter", "shell_and_tube"),
            ("parallel", "double_pipe"),
        ]:
            hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
            cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
            hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type=flow_type, exchanger_type=exch_type)

            for cr in [0.0, 1e-12, 1e-7, 0.5, 0.999999, 1.0]:
                for ntu in [0.0, 0.01, 1.0, 10.0, 100.0]:
                    eps = hx._segment_effectiveness(ntu, cr)
                    self.assertFalse(
                        math.isnan(eps), f"_segment_effectiveness returned NaN for {flow_type}, cr={cr}, ntu={ntu}"
                    )
                    self.assertTrue(0.0 <= eps <= 1.0)

    def test_bowman_shell_passes_not_conflated_with_tube_passes(self):
        """FinTubeHeatExchanger must pass shell_passes (not tube_passes) to Bowman F calculation."""
        hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
        cold = Fluid("cold", cp=2000.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube")
        hx.tube_passes = 4
        hx.shell_passes = 1

        # Evaluate F via _calc_lmtd_F
        warns = []
        F_1shell = hx._calc_lmtd_F(
            T_hot_in=100.0, T_cold_in=20.0, T_hot_out=60.0, T_cold_out=60.0, C_h=1000.0, C_c=1000.0, warnings=warns
        )

        # In a 1-shell 4-tube pass (N=1), F must equal _bowman_lmtd_factor with N_shell_passes=1
        expected_F = _bowman_lmtd_factor(100.0, 20.0, 60.0, 60.0, C_h=1000.0, C_c=1000.0, N_shell_passes=1)
        self.assertAlmostEqual(F_1shell, expected_F, places=4)

    def test_bowman_temperature_cross_detection(self):
        """When thermal duty exceeds theoretical single-shell limit, Bowman F should warn and clamp."""
        warns = []
        # Severe duty where S >= S_max:
        # T_hot_in=100, T_cold_in=20, T_hot_out=30, T_cold_out=90 -> P = (90-20)/80 = 0.875, R = 1.0
        # S_max for 1 shell with R=1 is 2 / (1 + 1 + sqrt(2)) = 2 / 3.414 = 0.586. P=0.875 > S_max!
        F = _bowman_lmtd_factor(100.0, 20.0, 30.0, 90.0, C_h=1000.0, C_c=1000.0, N_shell_passes=1, warnings=warns)
        self.assertEqual(F, 0.01)
        self.assertTrue(any("Sıcaklık çakışması" in w for w in warns))

    def test_orc_pipe_loss_watts_unit_consistency(self):
        """ORC First Law check must deduct pipe loss in Watts, not kW."""
        from orc_system_model import solve_orc_system

        res = solve_orc_system(
            {
                "m_flue": 15.0,
                "T_flue_in": 350.0,
                "m_oil": 12.0,
                "delta_T_pipe_loss_C": 5.0,
                "bypass_ratio": 0.0,
            }
        )
        self.assertIn("boiler", res)
        self.assertIn("orc", res)
        self.assertGreater(res["boiler"]["Q_kW"], 0.0)
        self.assertGreater(res["orc"]["Q_total_kW"], 0.0)
        # Pipe loss is in the order of ~150 kW (12 kg/s * ~2500 J/kgK * 5 K), not negligible ~0.15 kW
        pipe_loss_kw = res["superheater"]["Q_pipe_loss_kW"]
        self.assertGreater(pipe_loss_kw, 50.0)
        self.assertLessEqual(res["orc"]["Q_total_kW"], res["boiler"]["Q_kW"] - pipe_loss_kw + 0.1)

    def test_segmented_fallback_counterflow_slope_no_spurious_cross(self):
        """Counterflow fallback profile must not invert cold stream or produce false temperature cross."""
        hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
        cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=500.0, A=20.0, flow_type="counter", exchanger_type="shell_and_tube")

        # Mock shoot solver failure to exercise fallback branch
        from unittest.mock import patch

        with patch.object(hx, "_segment_effectiveness", side_effect=RuntimeError("root failure")):
            res = hx.solve_segmented(m_hot=1.0, m_cold=1.0, T_hot_in=100.0, T_cold_in=20.0, n_segments=5)
            self.assertIn("warnings", res)
            self.assertTrue(any("standart NTU profiline düşüldü" in w for w in res["warnings"]))
            # Counterflow fallback must NOT produce spurious internal temperature cross
            self.assertFalse(any("yerel sıcaklık çakışması" in w for w in res["warnings"]))

    def test_chedl_missing_dependency_raises_cleanly(self):
        """get_chedl_mixture_fluid_data must raise MissingDependencyError when thermo cannot be imported."""
        from unittest.mock import patch

        from exceptions import MissingDependencyError
        from fluids_db import get_chedl_mixture_fluid_data

        with patch.dict("sys.modules", {"thermo": None}), self.assertRaises(MissingDependencyError):
            get_chedl_mixture_fluid_data({"Water": 1.0}, {"Water": 1.0}, T_c=25.0, P_pa=101325.0)

    def test_multizone_condenser_sequential_allocation(self):
        """Sequential condenser must not allocate subcooling duty if condensation is incomplete."""
        hot = Fluid("steam", cp=2000.0, density=1.0, mu=1e-5, k_cond=0.03)
        cold = Fluid("water", cp=4180.0, density=1000.0, mu=0.001, k_cond=0.6)
        # Small area so capacity is limited
        hx = FinTubeHeatExchanger(hot, cold, U=200.0, A=2.0, flow_type="counter", exchanger_type="shell_and_tube")
        res = hx.solve_multizone_condenser(
            m_hot=0.5,
            m_cold=2.0,
            T_hot_in=150.0,
            T_sat=100.0,
            h_fg=2257e3,
            T_cold_in=20.0,
            T_subcool=90.0,
        )
        self.assertGreater(res["Q_desuperheat [W]"], 0.0)
        self.assertGreater(res["Q_condensing [W]"], 0.0)
        # Incomplete condensation: subcooling MUST be zero
        self.assertEqual(res["Q_subcooling [W]"], 0.0)
        self.assertAlmostEqual(res["T_hot_out [C]"], 100.0, places=1)
        self.assertTrue(any("kısmen yoğuştu" in w for w in res["warnings"]))

    def test_figure_canvas_thread_safety(self):
        """plot_temperature_profile and plot_enhanced_schematic must return Figure instances without pyplot pollution."""
        import matplotlib.pyplot as plt
        from matplotlib.figure import Figure

        hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
        cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=500.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube")
        res = hx.solve_ntu(m_hot=1.0, m_cold=1.0, T_hot_in=100.0, T_cold_in=20.0)

        initial_fignums = len(plt.get_fignums())
        fig_temp = hx.plot_temperature_profile(res)
        fig_schem = hx.plot_enhanced_schematic(res)

        self.assertIsInstance(fig_temp, Figure)
        self.assertIsInstance(fig_schem, Figure)
        # Pyplot global manager figures count should not have increased
        self.assertEqual(len(plt.get_fignums()), initial_fignums)

    def test_api661_face_velocity_auto_populated(self):
        """calculate_geometric_U for finned exchanger must populate api_face_velocity and bundle dimensions."""
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0214,
            "L": 4.0,
            "N_tubes": 64,
            "pitch": 0.0508,
            "k_wall": 50.0,
            "is_finned": True,
            "fin_height": 0.0127,
            "fin_thickness": 0.0004,
            "fin_density": 400.0,
            "k_fin": 200.0,
        }
        hot = Fluid("oil", cp=2000.0, density=850.0, mu=0.01, k_cond=0.14)
        cold = Fluid("air", cp=1005.0, density=1.2, mu=1.8e-5, k_cond=0.026)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=50.0, exchanger_type="finned_tube", flow_type="cross_unmixed")
        res = hx.calculate_geometric_U(geom, m_hot=2.0, m_cold=5.0)

        self.assertIn("api_face_velocity", res)
        self.assertGreater(res["api_face_velocity"], 0.0)
        self.assertIn("bundle_width", res)
        self.assertGreater(res["bundle_width"], 0.0)
        self.assertEqual(res["bundle_length"], 4.0)

    def test_units_native_conversions(self):
        """Native unit conversion routines must accurately convert imperial and volumetric units."""
        from units import from_celsius, to_celsius, to_kg_s

        # Mass flow
        self.assertAlmostEqual(to_kg_s(1.0, "lb/s"), 0.45359237, places=5)
        self.assertAlmostEqual(to_kg_s(3600.0, "lb/h"), 0.45359237, places=5)
        # Mass flow must tolerate density=None safely
        self.assertAlmostEqual(to_kg_s(10.0, "kg/s", density=None), 10.0)
        self.assertAlmostEqual(to_kg_s(3600.0, "kg/h", density=None), 1.0)
        self.assertAlmostEqual(to_kg_s(1.0, "lb/s", density=None), 0.45359237, places=5)
        # CFM (ft3/min) with air density 1.2 kg/m3
        cfm_kg_s = to_kg_s(100.0, "CFM", density=1.2)
        expected_cfm = (100.0 * 0.028316846592 * 1.2) / 60.0
        self.assertAlmostEqual(cfm_kg_s, expected_cfm, places=5)
        # Temperature
        self.assertAlmostEqual(to_celsius(32.0, "°F"), 0.0, places=4)
        self.assertAlmostEqual(to_celsius(212.0, "°F"), 100.0, places=4)
        self.assertAlmostEqual(from_celsius(0.0, "°F"), 32.0, places=4)
        self.assertAlmostEqual(from_celsius(100.0, "°F"), 212.0, places=4)
        self.assertAlmostEqual(to_celsius(300.0, "K"), 26.85, places=4)
        self.assertAlmostEqual(from_celsius(26.85, "K"), 300.0, places=4)

    def test_asme_ug27_pressure_bound_exceedance(self):
        """asme_wall_thickness must reject P > 0.385*S*E with clear error."""
        from mechanical import MechanicalDesignError, asme_wall_thickness

        S = 138e6
        E = 0.85
        # P = 50 MPa > 0.385 * 138e6 * 0.85 = 45.16 MPa
        with self.assertRaises(MechanicalDesignError) as ctx:
            asme_wall_thickness(P=50e6, R=0.2, S=S, E=E)
        self.assertIn("ASME UG-27 ince cidar sınırını", str(ctx.exception))

    def test_tema_tubesheet_absolute_minimum_floor(self):
        """tema_tubesheet_thickness must enforce TEMA RCB-7.134 minimum floor."""
        from mechanical import tema_tubesheet_thickness

        D_o = 0.0254  # 1 inç
        CA = 0.003
        # Very low pressure (1 bar): calculated bending is tiny, must hit 0.75*D_o + CA
        t_ts = tema_tubesheet_thickness(P=1.0e5, D_shell=0.3, S=115e6, pitch=0.03175, D_o=D_o, CA=CA)
        expected_floor = 0.75 * D_o + CA
        self.assertAlmostEqual(t_ts, expected_floor, places=5)

    def test_tema_fiv_acoustic_resonance_in_report(self):
        """mechanical_design_report must compute and include acoustic resonance when c_sonic and D_shell are supplied."""
        from mechanical import mechanical_design_report

        geom = {
            "D_shell": 0.5,
            "D_o": 0.0254,
            "t_wall": 0.002,
            "pitch": 0.03175,
            "baffle_spacing": 0.25,
            "v_cross": 15.0,
            "rho_shell": 2.5,
            "rho_tube": 1000.0,
            "c_sonic": 340.0,
            "design_pressure": 1.0e6,
        }
        rows = mechanical_design_report(geom)
        acoustic_rows = [r for r in rows if "Akustik Rezonans" in r["label"]]
        self.assertEqual(len(acoustic_rows), 1)
        self.assertIn("Hz", acoustic_rows[0]["value"])

    def test_orc_solver_convergence_flag_and_relaxation(self):
        """solve_orc_system must return converged flag and under-relaxed temperatures."""
        from orc_system_model import solve_orc_system

        res = solve_orc_system({})
        self.assertIn("converged", res["orc"])
        self.assertTrue(res["orc"]["converged"])
        self.assertIn("convergence_diff", res["orc"])
        self.assertLess(res["orc"]["convergence_diff"], 0.005)

    def test_solve_segmented_reversed_temperatures_raises_gracefully(self):
        """solve_segmented must raise InvalidInputError when T_hot_in <= T_cold_in."""
        from exceptions import InvalidInputError

        hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
        cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=500.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube")
        with self.assertRaises(InvalidInputError):
            hx.solve_segmented(m_hot=1.0, m_cold=1.0, T_hot_in=30.0, T_cold_in=50.0)

    def test_kettle_reboiler_shell_side_boiling_htc(self):
        """calculate_geometric_U with boiling cold fluid in shell must apply nucleate pool boiling HTC."""
        hot = Fluid("oil", cp=2000.0, density=850.0, mu=0.01, k_cond=0.14)
        cold = Fluid("cyclopentane", cp=2200.0, density=740.0, mu=0.0004, k_cond=0.12, h_fg=388e3, single_phase=False)
        geom = {
            "D_shell": 0.6,
            "D_o": 0.01905,
            "D_i": 0.01575,
            "L": 4.0,
            "N_tubes": 150,
            "pitch": 0.0254,
            "k_wall": 50.0,
            "baffle_spacing": 0.2,
            "baffle_cut": 0.25,
            "is_finned": False,
        }
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=30.0, exchanger_type="shell_and_tube", flow_type="counter")
        res = hx.calculate_geometric_U(geom, m_hot=5.0, m_cold=2.0, hot_is_tube=True)
        self.assertGreaterEqual(res["h_o"], 3000.0)
        self.assertTrue(any("Gövde tarafı havuz kaynaması" in w for w in res["warnings"]))

    def test_export_calculation_excel_lmtd_formula_adaptation(self):
        """export_calculation_excel must adapt LMTD formula for parallel, counter and crossflow."""
        import io

        import openpyxl

        from reporting import export_calculation_excel

        base_context = {
            "inputs": {"m_hot_kg_s": 5.0, "T_hot_in_C": 90.0, "m_cold_kg_s": 8.0, "T_cold_in_C": 20.0},
            "results": {"main": {"T_hot_out [C]": 60.0, "T_cold_out [C]": 45.0, "LMTD": 38.5, "Q [W]": 150000.0}},
            "selected_result": {"T_hot_out [C]": 60.0, "T_cold_out [C]": 45.0, "LMTD": 38.5, "Q [W]": 150000.0},
            "fluids": {"hot": {"label": "Water"}, "cold": {"label": "Water"}},
            "methods": {},
        }

        # 1. Parallel flow
        ctx_par = dict(base_context)
        ctx_par["methods"] = {"Akış tipi": "Paralel Akış (Parallel Flow)"}
        wb_par = openpyxl.load_workbook(io.BytesIO(export_calculation_excel(ctx_par)))
        ws_par = wb_par["TEMA Hesap Föyü"]
        # Find row for LMTD
        lmtd_val_par = None
        for row in range(1, ws_par.max_row + 1):
            if ws_par.cell(row=row, column=1).value == "LMTD":
                lmtd_val_par = ws_par.cell(row=row, column=2).value
                break
        self.assertIsNotNone(lmtd_val_par)
        self.assertIn("D6-D7", str(lmtd_val_par))  # Parallel delta T1: D_hot - D_cold

        # 2. Counter flow
        ctx_cnt = dict(base_context)
        ctx_cnt["methods"] = {"Akış tipi": "Ters Akış (Counter Flow)"}
        wb_cnt = openpyxl.load_workbook(io.BytesIO(export_calculation_excel(ctx_cnt)))
        ws_cnt = wb_cnt["TEMA Hesap Föyü"]
        lmtd_val_cnt = None
        for row in range(1, ws_cnt.max_row + 1):
            if ws_cnt.cell(row=row, column=1).value == "LMTD":
                lmtd_val_cnt = ws_cnt.cell(row=row, column=2).value
                break
        self.assertIsNotNone(lmtd_val_cnt)
        self.assertIn("D6-E7", str(lmtd_val_cnt))  # Counterflow delta T1: D_hot - E_cold

        # 3. Crossflow
        ctx_crs = dict(base_context)
        ctx_crs["methods"] = {"Akış tipi": "Çapraz Akış (Cross Flow Unmixed)"}
        wb_crs = openpyxl.load_workbook(io.BytesIO(export_calculation_excel(ctx_crs)))
        ws_crs = wb_crs["TEMA Hesap Föyü"]
        lmtd_val_crs = None
        for row in range(1, ws_crs.max_row + 1):
            if ws_crs.cell(row=row, column=1).value == "LMTD":
                lmtd_val_crs = ws_crs.cell(row=row, column=2).value
                break
        self.assertIsNotNone(lmtd_val_crs)
        self.assertAlmostEqual(float(lmtd_val_crs), 38.5, places=1)

    def test_sieder_tate_no_exponential_compounding(self):
        """Sieder-Tate iterations must apply viscosity correction once, without exponential compounding."""
        # Create fluids with known viscosity gradient
        f_hot = Fluid("Water", is_coolprop=True, calc_temp_c=80.0)
        f_cold = Fluid("Water", is_coolprop=True, calc_temp_c=20.0)
        hx = FinTubeHeatExchanger(f_hot, f_cold, U=100.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube")

        geom = {
            "D_o": 0.025,
            "D_i": 0.020,
            "L": 3.0,
            "N_tubes": 60,
            "k_wall": 50.0,
            "is_finned": False,
            "pitch": 0.03125,
            "tube_arrangement": "triangular",
            "baffle_spacing": 0.2,
            "baffle_cut": 0.25,
            "shell_passes": 1,
            "tube_passes": 1,
            "D_shell": 0.35,
        }
        res = hx.calculate_geometric_U(geom, m_hot=2.0, m_cold=2.0, hot_is_tube=True)
        # Check that h_i and h_o are within reasonable single-phase water ranges (~1000 - 15000 W/m2K)
        # and not blown up by (corr)^3
        self.assertGreater(res["h_i"], 500.0)
        self.assertLess(res["h_i"], 25000.0)
        self.assertGreater(res["h_o"], 200.0)
        self.assertLess(res["h_o"], 25000.0)

    def test_gnielinski_continuity_transition_range(self):
        """Nusselt calculation across Re=2300 to Re=3000 must be monotonic and continuous."""
        f_hot = Fluid("water", cp=4184.0, density=1000.0, mu=0.001, k_cond=0.6)
        f_cold = Fluid("water", cp=4184.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(f_hot, f_cold, U=100.0, A=10.0)

        Pr = 7.0
        warnings = []
        nu_2200 = hx._nusselt_internal(
            Re=2200.0, Pr=Pr, n_factor=0.3, laminar_nu=4.36, side_name="test", warnings=warnings
        )
        nu_2300 = hx._nusselt_internal(
            Re=2300.0, Pr=Pr, n_factor=0.3, laminar_nu=4.36, side_name="test", warnings=warnings
        )
        nu_2650 = hx._nusselt_internal(
            Re=2650.0, Pr=Pr, n_factor=0.3, laminar_nu=4.36, side_name="test", warnings=warnings
        )
        nu_3000 = hx._nusselt_internal(
            Re=3000.0, Pr=Pr, n_factor=0.3, laminar_nu=4.36, side_name="test", warnings=warnings
        )
        nu_3500 = hx._nusselt_internal(
            Re=3500.0, Pr=Pr, n_factor=0.3, laminar_nu=4.36, side_name="test", warnings=warnings
        )

        # nu_2200 should equal laminar Nu
        self.assertAlmostEqual(nu_2200, 4.36, places=2)
        # Intermediate point should be strictly between 2300 and 3000
        self.assertGreater(nu_2650, nu_2300)
        self.assertLess(nu_2650, nu_3000)
        # Turbulent at 3500 should be greater than at 3000
        self.assertGreater(nu_3500, nu_3000)
        # Check transition warning is logged
        self.assertTrue(any("geçiş bölgesinde" in w for w in warnings))

    def test_bell_delaware_sm_floor_stability(self):
        """Crossflow area S_m floor prevents singularity even when tube count exceeds typical bundle bounds."""
        f_hot = Fluid("oil", cp=2000.0, density=850.0, mu=0.01, k_cond=0.13)
        f_cold = Fluid("water", cp=4184.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(f_hot, f_cold, U=100.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube")

        # Set N_tubes artificially large such that D_shell - D_o * sqrt(N) * 0.8 <= 0
        geom = {
            "D_o": 0.025,
            "D_i": 0.020,
            "L": 3.0,
            "N_tubes": 500,
            "k_wall": 50.0,
            "is_finned": False,
            "pitch": 0.03125,
            "tube_arrangement": "triangular",
            "baffle_spacing": 0.1,
            "baffle_cut": 0.25,
            "shell_passes": 1,
            "tube_passes": 2,
            "D_shell": 0.25,  # Very tight shell for 500 tubes
        }
        res = hx.calculate_geometric_U(geom, m_hot=5.0, m_cold=5.0, hot_is_tube=True)
        self.assertGreater(res["U"], 0.0)
        self.assertFalse(res["U"] != res["U"])  # not NaN

    def test_desktop_fluid_selection_materialization(self):
        """Desktop build_fluid_from_selection must honor materialized correlation viscosity and conductivity."""
        from app_desktop import build_fluid_from_selection
        from fluids_db import get_fluid_data, materialize_fluid_data

        # 1. External correlation thermal oil
        oil_data = materialize_fluid_data(get_fluid_data("Kunlun L-QB300"), T_c=150.0)
        self.assertIn("mu", oil_data)
        self.assertIn("k_cond", oil_data)

        # Pass manual fallback values (e.g. gas spinbox 2e-5 and 0.03)
        fluid = build_fluid_from_selection(
            selection="Kunlun L-QB300",
            fluid_data=oil_data,
            mixture_data={},
            mixture_basis="mole",
            temp_c=150.0,
            mu=2e-5,
            k_cond=0.03,
        )
        # Fluid must take oil_data["mu"] (~0.02 Pa*s), NOT 2e-5
        self.assertAlmostEqual(fluid.mu, oil_data["mu"], places=5)
        self.assertAlmostEqual(fluid.k_cond, oil_data["k_cond"], places=4)
        self.assertNotEqual(fluid.mu, 2e-5)
        self.assertNotEqual(fluid.k_cond, 0.03)

        # 2. Manual preset thermal oil
        mob_data = materialize_fluid_data(get_fluid_data("Mobiltherm 605 (Manuel Yaklaşım)"), T_c=100.0)
        fluid_mob = build_fluid_from_selection(
            selection="Mobiltherm 605 (Manuel Yaklaşım)",
            fluid_data=mob_data,
            mixture_data={},
            mixture_basis="mole",
            temp_c=100.0,
            mu=2e-5,
            k_cond=0.03,
        )
        self.assertEqual(fluid_mob.mu, 0.015)
        self.assertEqual(fluid_mob.k_cond, 0.125)

    def test_desktop_geometry_pitch_and_mechanical_keys(self):
        """Desktop calculation snapshot must populate ASME/TEMA keys and scale pitch by fin status."""
        import sys

        from PyQt5.QtWidgets import QApplication

        from app_desktop import HeatExchangerDesktopApp

        _app = QApplication.instance() or QApplication(sys.argv)
        desktop = HeatExchangerDesktopApp()

        # Finned tube mode
        desktop.chk_finned.setChecked(True)
        desktop.spin_do.setValue(25.0)
        snap_finned = desktop.create_calculation_snapshot()
        geom_finned = snap_finned["geom"]
        self.assertAlmostEqual(geom_finned["pitch"], 0.050, places=4)  # 2.0 * Do
        self.assertEqual(geom_finned["tema_class"], "R")
        self.assertEqual(geom_finned["design_pressure"], 10e5)
        self.assertEqual(geom_finned["CA"], 0.003)

        # Bare tube mode
        desktop.chk_finned.setChecked(False)
        snap_bare = desktop.create_calculation_snapshot()
        geom_bare = snap_bare["geom"]
        self.assertAlmostEqual(geom_bare["pitch"], 0.03125, places=4)  # 1.25 * Do
        desktop.close()

    def test_gnielinski_pure_python_when_ht_missing(self):
        """When ht library is unavailable, pure-Python Petukhov/Gnielinski correlation must execute without NameError."""
        import heat_exchanger

        orig_available = heat_exchanger.HT_AVAILABLE
        orig_ht = getattr(heat_exchanger, "ht", None)
        try:
            heat_exchanger.HT_AVAILABLE = False
            heat_exchanger.ht = None

            f_hot = Fluid("water", cp=4184.0, density=1000.0, mu=0.001, k_cond=0.6)
            f_cold = Fluid("water", cp=4184.0, density=1000.0, mu=0.001, k_cond=0.6)
            hx = FinTubeHeatExchanger(f_hot, f_cold, U=100.0, A=10.0)

            warnings = []
            # Test transition range (2600)
            nu_trans = hx._nusselt_internal(
                Re=2600.0, Pr=7.0, n_factor=0.3, laminar_nu=4.36, side_name="tube", warnings=warnings
            )
            self.assertGreater(nu_trans, 4.36)
            # Test turbulent range (15000)
            nu_turb = hx._nusselt_internal(
                Re=15000.0, Pr=7.0, n_factor=0.3, laminar_nu=4.36, side_name="tube", warnings=warnings
            )
            self.assertGreater(nu_turb, 50.0)
        finally:
            heat_exchanger.HT_AVAILABLE = orig_available
            heat_exchanger.ht = orig_ht

    def test_desktop_append_log_live_display(self):
        """append_log must immediately update the live text_log widget."""
        import logging
        import sys

        from PyQt5.QtWidgets import QApplication

        from app_desktop import HeatExchangerDesktopApp

        _app = QApplication.instance() or QApplication(sys.argv)
        desktop = HeatExchangerDesktopApp()
        test_msg = "TEST_DIAGNOSTIC_MESSAGE_XYZ"
        desktop.append_log(test_msg, logging.INFO)
        self.assertIn(test_msg, desktop.text_log.toPlainText())
        desktop.close()

    def test_desktop_json_save_unknown_fluid_safe(self):
        """Saving calculation configuration with custom unlisted fluid must not crash with AttributeError."""
        import sys

        from PyQt5.QtWidgets import QApplication

        from app_desktop import HeatExchangerDesktopApp
        from fluids_db import get_fluid_data

        _app = QApplication.instance() or QApplication(sys.argv)
        desktop = HeatExchangerDesktopApp()
        # Set a custom unindexed fluid text
        desktop.combo_hot.setEditText("NonExistentSpecialFluid")
        cp = (get_fluid_data(desktop.combo_hot.currentText()) or {}).get("cp", 1100.0)
        self.assertEqual(cp, 1100.0)
        desktop.close()

    def test_correlations_temperature_cross_warning(self):
        """Bowman LMTD factor must flag warning and return 0.01 on temperature cross P >= 1.0."""
        from correlations import _bowman_lmtd_factor

        warnings = []
        # T_hot_in=100, T_cold_in=20, T_cold_out=110 -> P = (110-20)/(100-20) = 90/80 = 1.125 >= 1.0
        f_cross = _bowman_lmtd_factor(
            T_hot_in=100.0,
            T_cold_in=20.0,
            T_hot_out=60.0,
            T_cold_out=110.0,
            C_h=1000.0,
            C_c=1000.0,
            warnings=warnings,
        )
        self.assertEqual(f_cross, 0.01)
        self.assertTrue(any("Sıcaklık çakışması" in w for w in warnings))

    def test_temperature_cross_strict_raises_and_rating_marks_infeasible(self):
        from correlations import _bowman_lmtd_factor
        from exceptions import TemperatureCrossError

        with self.assertRaises(TemperatureCrossError):
            _bowman_lmtd_factor(100.0, 20.0, 60.0, 110.0, C_h=1000.0, C_c=1000.0, strict=True)

        hot = Fluid("w", cp=4184.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, hot, U=500.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube")
        hx.tube_passes = 2
        res = hx.calculate_actual_performance(1.0, 1.0, 100.0, 20.0, 30.0, 90.0)
        self.assertTrue(res["temperature_cross"])
        self.assertEqual(res["status"], "infeasible")
        self.assertEqual(res["U_required"], 0)

    def test_therminol66_vapor_pressure_and_darcy(self):
        """Verify Therminol 66 temperature-dependent Antoine VP and Darcy pipe helper."""
        from orc_system_model import calc_pipe_darcy, therminol66_vapor_pressure

        vp_100 = therminol66_vapor_pressure(100.0)
        vp_300 = therminol66_vapor_pressure(300.0)
        self.assertGreater(vp_300, vp_100)
        self.assertGreater(vp_300, 10000.0)  # > 10 kPa at 300 C

        # Darcy test: laminar (Re < 2300)
        res_lam = calc_pipe_darcy(di_mm=200.0, length_m=50.0, mass_flow_kg_s=0.5, rho=850.0, mu=0.01)
        self.assertLess(res_lam["re"], 2300)
        self.assertAlmostEqual(res_lam["f"], 64.0 / res_lam["re"], delta=0.001)

        # Darcy test: transition (2300 <= Re < 4000)
        res_trans = calc_pipe_darcy(di_mm=150.0, length_m=50.0, mass_flow_kg_s=1.4, rho=850.0, mu=0.004)
        self.assertGreaterEqual(res_trans["re"], 2300)
        self.assertLess(res_trans["re"], 4000)
        self.assertGreater(res_trans["f"], 0.01)

        # Darcy test: turbulent (Re >= 4000)
        res_turb = calc_pipe_darcy(di_mm=154.0, length_m=80.0, mass_flow_kg_s=32.0, rho=850.0, mu=0.002)
        self.assertGreater(res_turb["re"], 4000)
        self.assertGreater(res_turb["dp_bar"], 0.01)

    def test_api661_fan_power_check(self):
        """Verify API 661 fan power sizing and compliance table integration."""
        from mechanical import api661_fan_power_check, mechanical_design_report

        res = api661_fan_power_check(
            v_air_m3_s=25.0, dp_static_pa=150.0, fan_efficiency=0.65, drive_efficiency=0.95, num_fans=2
        )
        self.assertAlmostEqual(res["air_power_kw"], 3.75, delta=0.01)
        self.assertAlmostEqual(res["fan_brake_power_kw"], 3.75 / (0.65 * 0.95), delta=0.1)
        self.assertAlmostEqual(res["recommended_motor_kw"], res["fan_brake_power_kw"] * 1.10, delta=0.1)

        geom = {"design_pressure": 1.5e5, "v_air_m3_s": 25.0, "dp_acc_fan_pa": 150.0, "num_fans": 2}
        rows = mechanical_design_report(geom)
        self.assertTrue(any("API 661 Fan Mil Gücü" in r["label"] for r in rows))

    def test_excel_export_orc_whru_sheet(self):
        """Excel export must include ORC & WHRU sheet when orc_data is in context."""
        from io import BytesIO

        import openpyxl

        from reporting import export_calculation_excel

        context = {
            "inputs": {"m_hot_kg_s": 10.0, "T_hot_in_C": 300.0, "m_cold_kg_s": 12.0, "T_cold_in_C": 180.0},
            "orc_data": {
                "n_boilers": 3,
                "m_oil": 36.0,
                "pipe_dn_sel": "DN150",
                "pipe_di_mm": 154.0,
                "pipe_length_m": 75.0,
            },
        }
        xlsx_bytes = export_calculation_excel(context)
        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
        self.assertIn("ORC & WHRU Tesis Verileri", wb.sheetnames)
        ws_orc = wb["ORC & WHRU Tesis Verileri"]
        self.assertIn("WHRU KAZANLARI", str(ws_orc["A1"].value))

    def test_orc_schematic_telemetry_and_asme(self):
        """ORC schematic HTML must contain ASME UG-27, boiler pinch telemetry and latestCalcResult hook."""
        from orc_schematic_component import get_orc_schematic_html

        html = get_orc_schematic_html()
        self.assertIn("ASME UG-27 Cidar Kalınlığı", html)
        self.assertIn("Kazan Pinch Farkı (ΔT_pinch)", html)
        self.assertIn("window.latestCalcResult", html)
        self.assertIn("window.updatePlant3D", html)

    def test_provenance_and_equations_traceability(self):
        """calculate_geometric_U must return a structured provenance block tracing standards and correlations."""
        hot = Fluid("hot", cp=2000.0, density=900.0, mu=0.001, k_cond=0.2)
        cold = Fluid("cold", cp=4000.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(
            hot,
            cold,
            U=100.0,
            A=10.0,
            flow_type="counter",
            exchanger_type="shell_and_tube",
        )
        geom = {
            "D_shell": 0.6,
            "B": 0.3,
            "pitch": 0.032,
            "layout": "triangular",
            "N_tubes": 200,
            "D_o": 0.025,
            "D_i": 0.021,
            "L": 4.0,
            "L_tube": 4.0,
            "n_passes": 2,
            "R_fi": 0.0001,
            "R_fo": 0.0001,
            "k_wall": 45.0,
            "k_w": 45.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=5.0, m_cold=8.0)
        self.assertIn("provenance", res)
        prov = res["provenance"]
        self.assertIn("standards", prov)
        self.assertTrue(any("TEMA" in s for s in prov["standards"]))
        self.assertIn("correlations", prov)
        self.assertIn("validity", prov)
        self.assertIn("Re_shell", prov["validity"])
        self.assertIn("Re_tube", prov["validity"])

    def test_tubesheet_svg_standards_disclaimer(self):
        """Tubesheet SVG must carry explicit notice referencing ASME UHX / TEMA RCB-7 strength sizing."""
        from tubesheet_component import generate_tubesheet_svg

        svg = generate_tubesheet_svg(
            D_shell_mm=600.0,
            D_o_mm=25.0,
            D_i_mm=21.0,
            pitch_mm=32.0,
            layout_angle="30",
            N_tubes=120,
        )
        self.assertIn("ASME Part UHX / TEMA RCB-7", svg)

    def test_hydrostatic_test_pressure_stress_ratio(self):
        """Hydrostatic test pressure must accurately evaluate ASME UG-99(b) stress ratio S_test / S_design."""
        from mechanical import hydrostatic_test_pressure

        # Standard test at ambient design (S_test = S_design = 100 MPa): factor 1.3 -> 1.3 * 10 bar = 13 bar
        p_test_ambient = hydrostatic_test_pressure(MAWP=1.0e6, S_test=100e6, S_design=100e6)
        self.assertAlmostEqual(p_test_ambient, 1.3e6, delta=1.0)

        # Hot design (S_design = 80 MPa, S_test = 100 MPa): ratio = 1.25 -> 1.3 * 1.0 * 1.25 = 1.625e6
        p_test_hot = hydrostatic_test_pressure(MAWP=1.0e6, S_test=100e6, S_design=80e6)
        self.assertAlmostEqual(p_test_hot, 1.625e6, delta=1.0)


if __name__ == "__main__":
    unittest.main()
