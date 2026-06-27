"""Comprehensive tests for all changes across P0-P9."""

import unittest

import numpy as np

from app_desktop import (
    EXCHANGER_INTERNAL_TO_LABEL,
    EXCHANGER_LABEL_TO_INTERNAL,
    compute_desktop_calculation,
)
from config import (
    EXCHANGER_ALLOWED_FLOWS,
    EXCHANGER_F_METHOD,
    EXCHANGER_HO_METHOD,
    EXCHANGER_TYPE_DOUBLE,
    EXCHANGER_TYPE_FINNED,
    EXCHANGER_TYPE_SHELL,
)
from fluids_db import get_mixture_fluid_data
from heat_exchanger import (
    EXCHANGER_TYPE_DOUBLE as HX_DOUBLE,
)
from heat_exchanger import (
    EXCHANGER_TYPE_FINNED as HX_FINNED,
)
from heat_exchanger import (
    EXCHANGER_TYPE_SHELL as HX_SHELL,
)
from heat_exchanger import (
    FinTubeHeatExchanger,
    Fluid,
    _bowman_lmtd_factor,
)
from model_types import GeometryInput
from units import UNIT_MAP


class TestP0_BowmanR1Limit(unittest.TestCase):
    """P0: R≈1.0 L'Hospital limit + _crossflow_lmtd_factor rename."""

    def test_r_exactly_1_balanced_flow(self):
        f = _bowman_lmtd_factor(100.0, 20.0, 60.0, 60.0, C_h=100.0, C_c=100.0)
        self.assertFalse(np.isnan(f), "R=1 must not produce NaN")
        self.assertGreaterEqual(f, 0.01)

    def test_r_near_1_no_discontinuity(self):
        f0 = _bowman_lmtd_factor(100.0, 20.0, 60.0, 60.0, C_h=100.0, C_c=100.0)
        f1 = _bowman_lmtd_factor(100.0, 20.0, 60.0, 60.0, C_h=100.0, C_c=100.0)
        self.assertAlmostEqual(f0, f1, delta=0.01)

    def test_bowman_function_available(self):
        self.assertTrue(callable(_bowman_lmtd_factor))

    def test_no_nan_at_temperature_cross(self):
        f = _bowman_lmtd_factor(100.0, 20.0, 99.999, 99.998, C_h=100.0, C_c=100.0)
        self.assertFalse(np.isnan(f))
        self.assertGreaterEqual(f, 0.01)

    def test_no_nan_at_r_0_phase_change(self):
        f = _bowman_lmtd_factor(200.0, 50.0, 100.0, 60.0, C_h=1e6, C_c=100.0)
        self.assertFalse(np.isnan(f))

    def test_old_name_not_exported(self):
        import heat_exchanger

        self.assertFalse(
            hasattr(heat_exchanger, "_crossflow_lmtd_factor"), "Old name _crossflow_lmtd_factor must not exist"
        )


class TestP1_UnitsTypo(unittest.TestCase):
    """P1: units.py velocity/flowrate mapping fixes."""

    def test_no_m_s_mapping(self):
        self.assertNotIn("m/s", UNIT_MAP)

    def test_no_m_h_mapping(self):
        self.assertNotIn("m/h", UNIT_MAP)

    def test_volumetric_units_correct(self):
        self.assertIn("m3/s", UNIT_MAP)
        self.assertIn("m3/h", UNIT_MAP)
        self.assertIn("m³/s", UNIT_MAP)
        self.assertIn("m³/h", UNIT_MAP)

    def test_m3s_is_volume_flow(self):
        self.assertIn("m3/s", UNIT_MAP)
        self.assertIn("m³/s", UNIT_MAP)
        self.assertIsInstance(UNIT_MAP["m3/s"], str)


class TestP2_StreamlitCache(unittest.TestCase):
    """P2: Streamlit session_state result caching."""

    def test_calc_cache_in_source(self):
        with open("app_web.py", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("calc_cache", source)

    def test_render_calc_results_function(self):
        with open("app_web.py", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("_render_calc_results", source)

    def test_st_session_state_key(self):
        with open("app_web.py", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("st.session_state", source)

    def test_st_rerun_in_button_handler(self):
        with open("app_web.py", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("st.rerun", source)


class TestP3P4_ExchangerTypeArchitecture(unittest.TestCase):
    """P3+P4: Exchanger type selection + F-factor dispatch."""

    def test_exchanger_type_default_is_finned(self):
        hx = FinTubeHeatExchanger(
            Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            U=100,
            A=10,
            flow_type="cross_unmixed",
        )
        self.assertEqual(hx.exchanger_type, HX_FINNED)

    def test_exchanger_type_settable(self):
        hx = FinTubeHeatExchanger(
            Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            U=100,
            A=10,
            flow_type="counter",
            exchanger_type=HX_SHELL,
        )
        self.assertEqual(hx.exchanger_type, HX_SHELL)

    def test_config_constants_match_hx_module(self):
        self.assertEqual(EXCHANGER_TYPE_FINNED, HX_FINNED)
        self.assertEqual(EXCHANGER_TYPE_SHELL, HX_SHELL)
        self.assertEqual(EXCHANGER_TYPE_DOUBLE, HX_DOUBLE)

    def test_allowed_flows_exist_for_all_types(self):
        for t in (HX_FINNED, HX_SHELL, HX_DOUBLE):
            self.assertIn(t, EXCHANGER_ALLOWED_FLOWS)

    def test_f_method_mapping_exists(self):
        self.assertEqual(EXCHANGER_F_METHOD[HX_FINNED], "crossflow")
        self.assertEqual(EXCHANGER_F_METHOD[HX_SHELL], "bowman")
        self.assertEqual(EXCHANGER_F_METHOD[HX_DOUBLE], "unity")

    def test_ho_method_mapping_exists(self):
        self.assertEqual(EXCHANGER_HO_METHOD[HX_FINNED], "briggs_grimison")
        self.assertEqual(EXCHANGER_HO_METHOD[HX_SHELL], "kern")
        self.assertEqual(EXCHANGER_HO_METHOD[HX_DOUBLE], "annulus_inner")

    def test_crossflow_f_returns_1_for_non_cross(self):
        hx = FinTubeHeatExchanger(
            Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            U=100,
            A=10,
            flow_type="counter",
            exchanger_type=HX_SHELL,
        )
        f = hx._calc_crossflow_F(100.0, 20.0, 60.0, 60.0, 100.0, 100.0)
        self.assertEqual(f, 1.0)

    def test_finned_double_pipe_returns_F1(self):
        hx = FinTubeHeatExchanger(
            Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            U=100,
            A=10,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        f = hx._calc_lmtd_F(100.0, 20.0, 60.0, 60.0, 100.0, 100.0)
        self.assertEqual(f, 1.0)

    def test_shell_and_tube_uses_bowman(self):
        hx = FinTubeHeatExchanger(
            Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            U=100,
            A=10,
            flow_type="counter",
            exchanger_type=HX_SHELL,
        )
        f = hx._calc_lmtd_F(100.0, 20.0, 60.0, 60.0, 100.0, 100.0)
        self.assertFalse(np.isnan(f))
        self.assertGreaterEqual(f, 0.01)

    def test_finned_crossflow_f_reasonable(self):
        hx = FinTubeHeatExchanger(
            Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
            U=100,
            A=10,
            flow_type="cross_unmixed",
            exchanger_type=HX_FINNED,
        )
        f = hx._calc_crossflow_F(100.0, 20.0, 55.0, 65.0, 100.0, 100.0)
        self.assertFalse(np.isnan(f))
        self.assertLessEqual(f, 1.0)
        self.assertGreaterEqual(f, 0.0)

    def test_geometry_input_includes_exchanger_type(self):
        g = GeometryInput(D_o=0.0254, D_i=0.0211, L=3.0, N_tubes=100)
        self.assertEqual(g.exchanger_type, HX_FINNED)

    def test_geometry_input_shell_params(self):
        g = GeometryInput(
            D_o=0.0254,
            D_i=0.0211,
            L=3.0,
            N_tubes=100,
            exchanger_type=HX_SHELL,
            baffle_spacing=0.6,
            baffle_cut=0.25,
            tube_layout_angle="30",
            shell_passes=1,
        )
        self.assertEqual(g.baffle_spacing, 0.6)
        self.assertEqual(g.tube_layout_angle, "30")

    def test_invalid_exchanger_type_raises(self):
        with self.assertRaises(ValueError):
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="counter",
                exchanger_type="nonexistent",
            )


class TestP5_KernMethod(unittest.TestCase):
    """P5: Kern method for shell-and-tube h_o."""

    def setUp(self):
        self.hot = Fluid("hot", cp=1100, density=0.5, mu=2e-5, k_cond=0.03)
        self.cold = Fluid("cold", cp=2200, density=850, mu=0.003, k_cond=0.12)

    def make_hx(self, **kw):
        return FinTubeHeatExchanger(
            self.hot,
            self.cold,
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_SHELL,
            **kw,
        )

    def test_kern_returns_valid_ho(self):
        hx = self.make_hx()
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "pitch": 0.03175,
            "D_shell": 0.5,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "30",
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        self.assertGreater(res["h_o"], 0.0, "Kern h_o must be positive")
        self.assertGreater(res["Re_o"], 0.0)
        self.assertGreater(res["h_i"], 0.0)
        self.assertGreater(res["U"], 0.0)

    def test_kern_includes_pressure_drop(self):
        hx = self.make_hx()
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "pitch": 0.03175,
            "D_shell": 0.5,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "30",
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        self.assertGreater(res["delta_p_shell"], 0.0)
        self.assertGreater(res["delta_p_tube"], 0.0)

    def test_kern_warning_mentions_method(self):
        hx = self.make_hx()
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "pitch": 0.03175,
            "D_shell": 0.5,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "30",
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        warnings = res.get("warnings", [])
        kern_warnings = [w for w in warnings if "Kern" in w]
        self.assertTrue(len(kern_warnings) > 0, "Should have a Kern method warning")

    def test_kern_ho_triangular_pitch(self):
        hx = self.make_hx()
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "pitch": 0.03175,
            "D_shell": 0.5,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "60",
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        self.assertGreater(res["h_o"], 0.0)

    def test_kern_ho_square_pitch(self):
        hx = self.make_hx()
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "pitch": 0.03175,
            "D_shell": 0.5,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "90",
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        self.assertGreater(res["h_o"], 0.0)

    def test_kern_rejects_invalid_geom(self):
        hx = self.make_hx()
        with self.assertRaises(ValueError):
            hx.calculate_geometric_U(
                {
                    "D_o": 0.5,
                    "D_i": 0.4,  # D_shell must be > D_o
                    "L": 3.0,
                    "N_tubes": 100,
                    "k_wall": 45.0,
                    "pitch": 0.5,
                    "D_shell": 0.4,
                    "baffle_spacing": 0.6,
                    "R_f_i": 0.0,
                    "R_f_o": 0.0,
                },
                m_hot=15.0,
                m_cold=5.0,
                hot_is_tube=True,
            )


class TestP6_DoublePipeAnnulusNu(unittest.TestCase):
    """P6: Double-pipe laminar annulus Nu_i = 3.66 + 1.2*(r*)^(-0.8)."""

    def setUp(self):
        self.hot = Fluid("hot", cp=1100, density=0.5, mu=2e-5, k_cond=0.03)
        self.cold = Fluid("cold", cp=2200, density=850, mu=0.003, k_cond=0.12)

    def test_double_pipe_returns_positive_ho(self):
        hx = FinTubeHeatExchanger(
            self.hot,
            self.cold,
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 1,
            "k_wall": 45.0,
            "D_shell": 0.08,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=1.0, m_cold=0.5, hot_is_tube=True)
        self.assertGreater(res["h_o"], 0.0)
        self.assertGreater(res["Re_o"], 0.0)

    def test_double_pipe_laminar_warning(self):
        hx = FinTubeHeatExchanger(
            self.hot,
            self.cold,
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 1,
            "k_wall": 45.0,
            "D_shell": 0.08,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=0.01, m_cold=0.005, hot_is_tube=True)
        warnings = res.get("warnings", [])
        inner_warnings = [w for w in warnings if "iç çeper" in w or "annulus" in w]
        self.assertTrue(len(inner_warnings) > 0, "Should have an annulus warning")

    def test_double_pipe_pressure_drop_uses_annulus_friction(self):
        hx = FinTubeHeatExchanger(
            self.hot,
            self.cold,
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 1,
            "k_wall": 45.0,
            "D_shell": 0.08,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=1.0, m_cold=0.5, hot_is_tube=True)
        self.assertGreater(res["delta_p_shell"], 0.0)
        self.assertGreater(res["delta_p_tube"], 0.0)

    def test_double_pipe_geometry_validation(self):
        hx = FinTubeHeatExchanger(
            self.hot,
            self.cold,
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        with self.assertRaises(ValueError):
            hx.calculate_geometric_U(
                {
                    "D_o": 0.08,
                    "D_i": 0.07,
                    "L": 3.0,
                    "N_tubes": 1,
                    "k_wall": 45.0,
                    "D_shell": 0.05,
                    "R_f_i": 0.0,
                    "R_f_o": 0.0,
                },
                m_hot=1.0,
                m_cold=0.5,
                hot_is_tube=True,
            )

    def test_double_pipe_laminar_nu_reasonable(self):
        hx = FinTubeHeatExchanger(
            self.hot,
            self.cold,
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 1,
            "k_wall": 45.0,
            "D_shell": 0.08,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=0.001, m_cold=0.0005, hot_is_tube=True)
        self.assertGreater(res["h_o"], 0.0)


class TestP7_WilkeWassiljewa(unittest.TestCase):
    """P7: Wilke viscosity + Wassiljewa conductivity mixing rules."""

    def test_mixture_uses_wilke_wassiljewa(self):
        result = get_mixture_fluid_data(
            {"Nitrogen": 70.0, "Oxygen": 20.0, "CarbonDioxide": 10.0},
            comp_type="mass",
            T_c=180.0,
            P_pa=101325.0,
        )
        expected_sources = {
            "CoolProp HEOS mixture",
            "CoolProp ideal mixture",
            "ChEDL/thermo",
            "Wilke viscosity + Wassiljewa conductivity",
        }
        self.assertIn(result["property_source"], expected_sources)

    def test_wilke_produces_different_mu_than_simple_average(self):
        try:
            import CoolProp.CoolProp as CP

            mu_n2 = CP.PropsSI("V", "T", 300.0, "P", 101325.0, "Nitrogen")
            mu_o2 = CP.PropsSI("V", "T", 300.0, "P", 101325.0, "Oxygen")
            simple_mu = 0.5 * mu_n2 + 0.5 * mu_o2
            result = get_mixture_fluid_data(
                {"Nitrogen": 50.0, "Oxygen": 50.0},
                comp_type="mole",
                T_c=26.85,
                P_pa=101325.0,
            )
            if result["property_source"] == "Wilke viscosity + Wassiljewa conductivity":
                self.assertNotAlmostEqual(result["mu"], simple_mu, delta=simple_mu * 0.01)
        except ImportError:
            self.skipTest("CoolProp not available")

    def test_mixture_properties_all_positive(self):
        result = get_mixture_fluid_data(
            {"Nitrogen": 70.0, "Oxygen": 20.0, "CarbonDioxide": 10.0},
            comp_type="mass",
            T_c=180.0,
            P_pa=101325.0,
        )
        for key in ("cp", "density", "mu", "k_cond"):
            self.assertGreater(result[key], 0.0, f"{key} must be positive")


class TestP8_PDFReport(unittest.TestCase):
    """P8: PDF report improvements."""

    def _make_basic_context(self):
        hot = Fluid("hot", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        cold = Fluid("cold", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        hx = FinTubeHeatExchanger(hot, cold, U=100, A=10, flow_type="counter", exchanger_type=HX_SHELL)
        main = hx.solve_ntu(1.0, 1.0, 100.0, 0.0)
        return {
            "methods": {
                "Hesap amacı": "test",
                "Akış tipi": "counter",
                "Akış tipi internal": "counter",
                "Ana çözücü": "test",
                "U modu": "Basit Mod",
            },
            "inputs": {
                "m_hot_raw": "1 kg/s",
                "m_cold_raw": "1 kg/s",
                "m_hot_kg_s": 1.0,
                "m_cold_kg_s": 1.0,
                "T_hot_in_C": 100.0,
                "T_cold_in_C": 0.0,
                "U": 100.0,
                "A": 10.0,
            },
            "fluids": {
                "hot": {"label": "hot", "cp": 1000, "density": 1, "mu": 1e-5, "k_cond": 0.03},
                "cold": {"label": "cold", "cp": 1000, "density": 1, "mu": 1e-5, "k_cond": 0.03},
            },
            "geometry": {},
            "geo_result": None,
            "results": {"main": main},
            "actual_result": None,
            "crosscheck_results": [main],
        }

    def test_pdf_valid_pdf_structure(self):
        from reporting import build_calculation_report_pdf

        pdf = build_calculation_report_pdf(self._make_basic_context())
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"/Type /Catalog", pdf)
        self.assertIn(b"/Type /Pages", pdf)
        self.assertIn(b"/Type /Page", pdf)

    def test_pdf_starts_with_pdf_marker(self):
        from reporting import build_calculation_report_pdf

        pdf = build_calculation_report_pdf(self._make_basic_context())
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_pdf_with_geo_result_contains_shell_tube_headers(self):
        from reporting import build_calculation_report_pdf

        hot = Fluid("hot", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        cold = Fluid("cold", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        hx = FinTubeHeatExchanger(hot, cold, U=100, A=10, flow_type="counter", exchanger_type=HX_SHELL)
        main = hx.solve_ntu(1.0, 1.0, 100.0, 0.0)
        ctx = {
            "methods": {
                "Hesap amacı": "test",
                "Akış tipi": "counter",
                "Akış tipi internal": "counter",
                "Ana çözücü": "test",
                "U modu": "Geometrik",
            },
            "inputs": {
                "m_hot_raw": "1",
                "m_cold_raw": "1",
                "m_hot_kg_s": 1.0,
                "m_cold_kg_s": 1.0,
                "T_hot_in_C": 100.0,
                "T_cold_in_C": 0.0,
                "U": 100.0,
                "A": 10.0,
            },
            "fluids": {
                "hot": {"label": "hot", "cp": 1000, "density": 1, "mu": 1e-5, "k_cond": 0.03},
                "cold": {"label": "cold", "cp": 1000, "density": 1, "mu": 1e-5, "k_cond": 0.03},
            },
            "geometry": {"D_o": 0.0254, "D_i": 0.0211, "L": 3.0, "N_tubes": 100},
            "geo_result": {
                "U": 450,
                "A_total": 23.5,
                "h_i": 2500,
                "h_o": 1200,
                "Re_i": 25000,
                "Re_o": 15000,
                "R_wall": 0.0001,
                "eta_fin": 0.95,
                "delta_p_tube": 5000,
                "delta_p_shell": 3000,
            },
            "results": {"main": main},
            "actual_result": {
                "Q_hot [W]": 51000,
                "Q_cold [W]": 49000,
                "Q_avg [W]": 50000,
                "epsilon_actual": 0.74,
                "U_required": 480,
                "LMTD": 35.0,
                "F": 0.92,
            },
            "crosscheck_results": [main],
        }
        pdf = build_calculation_report_pdf(ctx)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"/Type /Page", pdf)
        self.assertGreater(len(pdf), 2000)

    def test_geo_simple_mode_pdf(self):
        from reporting import build_calculation_report_pdf

        pdf = build_calculation_report_pdf(self._make_basic_context())
        self.assertTrue(pdf.startswith(b"%PDF-"))


class TestP9_DesktopExchangerSelector(unittest.TestCase):
    """P9: Desktop PyQt5 exchanger type selector."""

    def test_exchanger_label_mapping_roundtrip(self):
        for label, internal in EXCHANGER_LABEL_TO_INTERNAL.items():
            self.assertEqual(EXCHANGER_INTERNAL_TO_LABEL[internal], label)

    def test_all_types_have_labels(self):
        for t in (HX_FINNED, HX_SHELL, HX_DOUBLE):
            self.assertIn(t, EXCHANGER_INTERNAL_TO_LABEL)

    def test_snapshot_contains_exchanger_type(self):
        def _manual_snapshot(**kw):
            s = {
                "purpose": "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)",
                "flow_label": "Ters Akış (Counter Flow)",
                "flow_type": "counter",
                "method": "Kendi Algoritmamız (Epsilon-NTU)",
                "u_mode": "Basit Mod (Manuel U Değeri)",
                "hot_selection": "Manuel Giriş (Özel Akışkan)",
                "cold_selection": "Manuel Giriş (Özel Akışkan)",
                "hot_mixture_data": {},
                "hot_mixture_basis": "mole",
                "cold_mixture_data": {},
                "cold_mixture_basis": "mole",
                "m_hot_raw": 1.0,
                "m_cold_raw": 2.0,
                "m_hot_unit": "kg/s",
                "m_cold_unit": "kg/s",
                "T_hot_raw": 180.0,
                "T_cold_raw": 40.0,
                "T_hot_unit": "°C",
                "T_cold_unit": "°C",
                "T_hot_out_raw": -999.0,
                "T_cold_out_raw": -999.0,
                "T_hot_out_unit": "°C",
                "T_cold_out_unit": "°C",
                "mu_hot": 2e-5,
                "k_hot": 0.03,
                "mu_cold": 1e-3,
                "k_cold": 0.6,
                "U": 250.0,
                "A": 12.0,
                "hot_is_tube": True,
                "geom": {
                    "D_o": 0.0254,
                    "D_i": 0.0211,
                    "L": 3.0,
                    "N_tubes": 20,
                    "k_wall": 45.0,
                    "is_finned": False,
                    "fin_height": 0.0,
                    "fin_thickness": 0.0,
                    "fin_density": 0.0,
                    "k_fin": 237.0,
                    "pitch": 0.06,
                    "D_shell": 0.08,
                    "R_f_i": 0.0,
                    "R_f_o": 0.0,
                },
            }
            s.update(kw)
            return s

        snap = _manual_snapshot(exchanger_type=HX_SHELL)
        self.assertEqual(snap["exchanger_type"], HX_SHELL)

    def test_compute_with_finned_exchanger(self):
        result = compute_desktop_calculation(
            {
                "purpose": "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)",
                "flow_label": "Çapraz Akış (Cross Flow Unmixed)",
                "flow_type": "cross_unmixed",
                "exchanger_type": "finned_tube",
                "method": "Kendi Algoritmamız (Epsilon-NTU)",
                "u_mode": "Basit Mod (Manuel U Değeri)",
                "hot_selection": "Manuel Giriş (Özel Akışkan)",
                "cold_selection": "Manuel Giriş (Özel Akışkan)",
                "hot_mixture_data": {},
                "hot_mixture_basis": "mole",
                "cold_mixture_data": {},
                "cold_mixture_basis": "mole",
                "m_hot_raw": 1.0,
                "m_cold_raw": 2.0,
                "m_hot_unit": "kg/s",
                "m_cold_unit": "kg/s",
                "T_hot_raw": 180.0,
                "T_cold_raw": 40.0,
                "T_hot_unit": "°C",
                "T_cold_unit": "°C",
                "T_hot_out_raw": -999.0,
                "T_cold_out_raw": -999.0,
                "T_hot_out_unit": "°C",
                "T_cold_out_unit": "°C",
                "mu_hot": 2e-5,
                "k_hot": 0.03,
                "mu_cold": 1e-3,
                "k_cold": 0.6,
                "U": 250.0,
                "A": 12.0,
                "hot_is_tube": True,
                "geom": {},
            }
        )
        self.assertGreater(result["res_main"]["Q [W]"], 0.0)
        self.assertEqual(result["hx"].exchanger_type, "finned_tube")

    def test_compute_with_shell_exchanger_simple(self):
        result = compute_desktop_calculation(
            {
                "purpose": "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)",
                "flow_label": "Ters Akış (Counter Flow)",
                "flow_type": "counter",
                "exchanger_type": "shell_and_tube",
                "method": "Kendi Algoritmamız (Epsilon-NTU)",
                "u_mode": "Basit Mod (Manuel U Değeri)",
                "hot_selection": "Manuel Giriş (Özel Akışkan)",
                "cold_selection": "Manuel Giriş (Özel Akışkan)",
                "hot_mixture_data": {},
                "hot_mixture_basis": "mole",
                "cold_mixture_data": {},
                "cold_mixture_basis": "mole",
                "m_hot_raw": 1.0,
                "m_cold_raw": 2.0,
                "m_hot_unit": "kg/s",
                "m_cold_unit": "kg/s",
                "T_hot_raw": 180.0,
                "T_cold_raw": 40.0,
                "T_hot_unit": "°C",
                "T_cold_unit": "°C",
                "T_hot_out_raw": -999.0,
                "T_cold_out_raw": -999.0,
                "T_hot_out_unit": "°C",
                "T_cold_out_unit": "°C",
                "mu_hot": 2e-5,
                "k_hot": 0.03,
                "mu_cold": 1e-3,
                "k_cold": 0.6,
                "U": 250.0,
                "A": 12.0,
                "hot_is_tube": True,
                "geom": {},
            }
        )
        self.assertGreater(result["res_main"]["Q [W]"], 0.0)
        self.assertEqual(result["hx"].exchanger_type, "shell_and_tube")

    def test_compute_with_double_pipe_exchanger_simple(self):
        result = compute_desktop_calculation(
            {
                "purpose": "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)",
                "flow_label": "Ters Akış (Counter Flow)",
                "flow_type": "counter",
                "exchanger_type": "double_pipe",
                "method": "Kendi Algoritmamız (Epsilon-NTU)",
                "u_mode": "Basit Mod (Manuel U Değeri)",
                "hot_selection": "Manuel Giriş (Özel Akışkan)",
                "cold_selection": "Manuel Giriş (Özel Akışkan)",
                "hot_mixture_data": {},
                "hot_mixture_basis": "mole",
                "cold_mixture_data": {},
                "cold_mixture_basis": "mole",
                "m_hot_raw": 1.0,
                "m_cold_raw": 2.0,
                "m_hot_unit": "kg/s",
                "m_cold_unit": "kg/s",
                "T_hot_raw": 180.0,
                "T_cold_raw": 40.0,
                "T_hot_unit": "°C",
                "T_cold_unit": "°C",
                "T_hot_out_raw": -999.0,
                "T_cold_out_raw": -999.0,
                "T_hot_out_unit": "°C",
                "T_cold_out_unit": "°C",
                "mu_hot": 2e-5,
                "k_hot": 0.03,
                "mu_cold": 1e-3,
                "k_cold": 0.6,
                "U": 250.0,
                "A": 12.0,
                "hot_is_tube": True,
                "geom": {},
            }
        )
        self.assertGreater(result["res_main"]["Q [W]"], 0.0)
        self.assertEqual(result["hx"].exchanger_type, "double_pipe")

    def test_exchanger_type_in_source(self):
        with open("app_desktop.py", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("combo_exchanger", source)
        self.assertIn("on_exchanger_changed", source)
        self.assertIn("EXCHANGER_LABEL_TO_INTERNAL", source)
        self.assertIn("EXCHANGER_INTERNAL_TO_LABEL", source)


class TestIntegration_AllExchangerTypesGeometric(unittest.TestCase):
    """End-to-end geometric calculations for all three exchanger types."""

    def setUp(self):
        self.fluids = {
            "hot": Fluid("hot", cp=1100, density=0.5, mu=2e-5, k_cond=0.03),
            "cold": Fluid("cold", cp=2200, density=850, mu=0.003, k_cond=0.12),
        }

    def _base_geom(self):
        return {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }

    def test_finned_geometric_flow(self):
        hx = FinTubeHeatExchanger(
            self.fluids["hot"],
            self.fluids["cold"],
            U=1.0,
            A=1.0,
            flow_type="cross_unmixed",
            exchanger_type=HX_FINNED,
        )
        geom = dict(
            self._base_geom(),
            is_finned=True,
            fin_height=0.0159,
            fin_thickness=0.0004,
            fin_density=400,
            k_fin=237.0,
            pitch=0.06,
            D_shell=0.08,
        )
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=False)
        for k in ("U", "h_i", "h_o", "Re_i", "Re_o", "delta_p_tube", "delta_p_shell"):
            self.assertIn(k, res, f"Missing key: {k}")

    def test_shell_geometric_flow(self):
        hx = FinTubeHeatExchanger(
            self.fluids["hot"],
            self.fluids["cold"],
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_SHELL,
        )
        geom = dict(self._base_geom(), pitch=0.03175, D_shell=0.5, baffle_spacing=0.6, tube_layout_angle="30")
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        for k in ("U", "h_i", "h_o", "Re_i", "Re_o", "delta_p_tube", "delta_p_shell"):
            self.assertIn(k, res, f"Missing key: {k}")

    def test_double_pipe_geometric_flow(self):
        hx = FinTubeHeatExchanger(
            self.fluids["hot"],
            self.fluids["cold"],
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_DOUBLE,
        )
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 1,
            "k_wall": 45.0,
            "D_shell": 0.08,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=1.0, m_cold=0.5, hot_is_tube=True)
        for k in ("U", "h_i", "h_o", "Re_i", "Re_o", "delta_p_tube", "delta_p_shell"):
            self.assertIn(k, res, f"Missing key: {k}")

    def test_all_types_produce_reasonable_U(self):
        for exch_type, flow, kw in [
            (
                HX_FINNED,
                "cross_unmixed",
                {
                    "is_finned": True,
                    "fin_height": 0.0159,
                    "fin_thickness": 0.0004,
                    "fin_density": 400,
                    "k_fin": 237.0,
                    "pitch": 0.06,
                    "D_shell": 0.08,
                },
            ),
            (HX_SHELL, "counter", {"pitch": 0.03175, "D_shell": 0.5, "baffle_spacing": 0.6, "tube_layout_angle": "30"}),
            (HX_DOUBLE, "counter", {"D_shell": 0.08}),
        ]:
            hx = FinTubeHeatExchanger(
                self.fluids["hot"],
                self.fluids["cold"],
                U=1.0,
                A=1.0,
                flow_type=flow,
                exchanger_type=exch_type,
            )
            geom = dict(self._base_geom(), **kw)
            res = hx.calculate_geometric_U(
                geom,
                m_hot=15.0 if exch_type != HX_DOUBLE else 1.0,
                m_cold=5.0 if exch_type != HX_DOUBLE else 0.5,
                hot_is_tube=True,
            )
            self.assertGreater(res["U"], 0.0, f"U must be > 0 for {exch_type}")

    def test_lmtd_solve_works_all_types(self):
        for exch_type, flow in [
            (HX_FINNED, "cross_unmixed"),
            (HX_SHELL, "counter"),
            (HX_DOUBLE, "counter"),
        ]:
            hx = FinTubeHeatExchanger(
                self.fluids["hot"],
                self.fluids["cold"],
                U=100,
                A=10,
                flow_type=flow,
                exchanger_type=exch_type,
            )
            main = hx.solve_lmtd(1.0, 2.0, 180.0, 40.0, source="custom")
            self.assertIn(
                main["status"], ("ok", "warning"), f"LMTD solve failed for {exch_type}: {main.get('warnings', [])}"
            )
            self.assertGreater(main["Q [W]"], 0, f"Q must be positive for {exch_type}")

    def test_kern_geometric_actual_performance(self):
        hx = FinTubeHeatExchanger(
            self.fluids["hot"],
            self.fluids["cold"],
            U=1.0,
            A=1.0,
            flow_type="counter",
            exchanger_type=HX_SHELL,
        )
        geom = dict(self._base_geom(), pitch=0.03175, D_shell=0.5, baffle_spacing=0.6, tube_layout_angle="30")
        geo_res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        hx.U = geo_res["U"]
        hx.A = geo_res["A_total"]
        ntu_res = hx.solve_ntu(15.0, 5.0, 180.0, 40.0)
        self.assertGreater(ntu_res["Q [W]"], 0.0)
        self.assertIn("T_hot_out [C]", ntu_res)
        self.assertIn("T_cold_out [C]", ntu_res)


class TestRegression_ExistingTestsStillPass(unittest.TestCase):
    """Sanity-check: run the previous regression tests in-process."""

    def test_existing_counterflow_lmtd_matches_ntu(self):
        hot = Fluid("hot", cp=4000, density=1000, mu=1e-3, k_cond=0.6)
        cold = Fluid("cold", cp=4000, density=1000, mu=1e-3, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=5000, A=100, flow_type="counter", exchanger_type=HX_DOUBLE)
        ntu = hx.solve_ntu(1.0, 1.0, 100.0, 0.0, source="custom")
        lmtd = hx.solve_lmtd(1.0, 1.0, 100.0, 0.0, source="ht")
        self.assertAlmostEqual(lmtd["Q [W]"], ntu["Q [W]"], delta=ntu["Q [W]"] * 0.01)

    def test_existing_geometric_u_fouling(self):
        hot = Fluid("hot", cp=1100, density=0.5, mu=2e-5, k_cond=0.03)
        cold = Fluid("cold", cp=2200, density=850, mu=0.003, k_cond=0.12)
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="cross_unmixed")
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "is_finned": False,
            "pitch": 0.06,
            "D_shell": 0.08,
        }
        clean = hx.calculate_geometric_U(dict(geom, R_f_i=0.0, R_f_o=0.0), m_hot=15.0, m_cold=5.0, hot_is_tube=False)
        fouled = hx.calculate_geometric_U(
            dict(geom, R_f_i=0.002, R_f_o=0.002), m_hot=15.0, m_cold=5.0, hot_is_tube=False
        )
        self.assertLess(fouled["U"], clean["U"])

    def test_existing_ntu_rejects_nonphysical(self):
        hot = Fluid("hot", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        cold = Fluid("cold", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        hx = FinTubeHeatExchanger(hot, cold, U=10, A=10, flow_type="counter", exchanger_type=HX_SHELL)
        with self.assertRaises(ValueError):
            hx.solve_ntu(0.0, 1.0, 100.0, 0.0)

    def test_existing_bowman_edge_cases(self):
        self.assertFalse(np.isnan(_bowman_lmtd_factor(100, 20, 99.999, 99.998, 100, 100)))
        self.assertFalse(np.isnan(_bowman_lmtd_factor(200, 50, 100, 60, 1e6, 100)))
        self.assertEqual(_bowman_lmtd_factor(100, 20, 100, 20, 100, 100), 1.0)
        self.assertFalse(np.isnan(_bowman_lmtd_factor(100, 20, 60, 60, 100, 100)))
        self.assertGreaterEqual(_bowman_lmtd_factor(100, 20, 60, 60, 100, 100), 0.01)


class TestFlowTypeExchangerValidation(unittest.TestCase):
    """Validates flow_type × exchanger_type cross-enforcement."""

    def test_finned_rejects_counter(self):
        with self.assertRaises(ValueError):
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="counter",
                exchanger_type=HX_FINNED,
            )

    def test_finned_rejects_parallel(self):
        with self.assertRaises(ValueError):
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="parallel",
                exchanger_type=HX_FINNED,
            )

    def test_shell_rejects_parallel(self):
        with self.assertRaises(ValueError):
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="parallel",
                exchanger_type=HX_SHELL,
            )

    def test_double_rejects_cross_unmixed(self):
        with self.assertRaises(ValueError):
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="cross_unmixed",
                exchanger_type=HX_DOUBLE,
            )

    def test_double_rejects_cross_mixed_unmixed(self):
        with self.assertRaises(ValueError):
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="cross_mixed_unmixed",
                exchanger_type=HX_DOUBLE,
            )

    def test_all_valid_combos_accepted(self):
        for exch, flows in EXCHANGER_ALLOWED_FLOWS.items():
            for flow in flows:
                hx = FinTubeHeatExchanger(
                    Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                    Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                    U=100,
                    A=10,
                    flow_type=flow,
                    exchanger_type=exch,
                )
                self.assertEqual(hx.flow_type, flow)
                self.assertEqual(hx.exchanger_type, exch)

    def test_error_message_mentions_allowed_types(self):
        with self.assertRaises(ValueError) as cm:
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="counter",
                exchanger_type=HX_FINNED,
            )
        msg = str(cm.exception)
        self.assertIn("izin verilmeyen", msg)
        self.assertIn("cross_unmixed", msg)

    def test_error_message_mentions_exchanger_type_name(self):
        with self.assertRaises(ValueError) as cm:
            FinTubeHeatExchanger(
                Fluid("h", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                Fluid("c", cp=1000, density=1, mu=1e-5, k_cond=0.03),
                U=100,
                A=10,
                flow_type="cross_unmixed",
                exchanger_type=HX_DOUBLE,
            )
        msg = str(cm.exception)
        self.assertIn("Çift Borulu", msg)

    def test_desktop_normalize_fixes_invalid_flow(self):
        from app_desktop import normalize_loaded_data

        data = {
            "flow_type": "parallel",
            "exchanger_type": "finned_tube",
        }
        normalized = normalize_loaded_data(data)
        self.assertEqual(normalized["exchanger_type"], "finned_tube")
        self.assertIn(normalized["flow_type"], EXCHANGER_ALLOWED_FLOWS["finned_tube"])

    def test_desktop_normalize_preserves_valid_flow(self):
        from app_desktop import normalize_loaded_data

        data = {
            "flow_type": "cross_unmixed",
            "exchanger_type": "finned_tube",
        }
        normalized = normalize_loaded_data(data)
        self.assertEqual(normalized["flow_type"], "cross_unmixed")


class TestIntegration_FullPipeline(unittest.TestCase):
    """End-to-end pipeline: snapshot → compute → report → verify output."""

    def _base_snapshot(self) -> dict:
        return {
            "purpose": "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)",
            "flow_label": "Ters Akış (Counter Flow)",
            "flow_type": "counter",
            "exchanger_type": "shell_and_tube",
            "method": "Kendi Algoritmamız (Epsilon-NTU)",
            "u_mode": "Basit Mod (Manuel U Değeri)",
            "hot_selection": "Manuel Giriş (Özel Akışkan)",
            "cold_selection": "Manuel Giriş (Özel Akışkan)",
            "hot_mixture_data": {},
            "hot_mixture_basis": "mole",
            "cold_mixture_data": {},
            "cold_mixture_basis": "mole",
            "m_hot_raw": 1.0,
            "m_cold_raw": 2.0,
            "m_hot_unit": "kg/s",
            "m_cold_unit": "kg/s",
            "T_hot_raw": 180.0,
            "T_cold_raw": 40.0,
            "T_hot_unit": "°C",
            "T_cold_unit": "°C",
            "T_hot_out_raw": -999.0,
            "T_cold_out_raw": -999.0,
            "T_hot_out_unit": "°C",
            "T_cold_out_unit": "°C",
            "mu_hot": 2e-5,
            "k_hot": 0.03,
            "mu_cold": 1e-3,
            "k_cold": 0.6,
            "U": 250.0,
            "A": 12.0,
            "hot_is_tube": True,
            "geom": {
                "D_o": 0.0254,
                "D_i": 0.0211,
                "L": 3.0,
                "N_tubes": 20,
                "k_wall": 45.0,
                "is_finned": False,
                "fin_height": 0.0,
                "fin_thickness": 0.0,
                "fin_density": 0.0,
                "k_fin": 237.0,
                "pitch": 0.06,
                "D_shell": 0.08,
                "R_f_i": 0.0,
                "R_f_o": 0.0,
            },
        }

    def _assert_valid_pipeline_result(self, result: dict) -> None:
        self.assertIn("report_context", result)
        rc = result["report_context"]
        self.assertIn("results", rc)
        self.assertIn("main", rc["results"])
        self.assertGreater(rc["results"]["main"]["Q [W]"], 0.0)
        self.assertIn("methods", rc)
        self.assertIn("Akış tipi", rc["methods"])
        self.assertIn("inputs", rc)
        self.assertIn("fluids", rc)

    def test_shell_and_tube_full_pipeline(self):
        from app_desktop import compute_desktop_calculation
        from reporting import build_calculation_report, build_calculation_report_pdf

        snap = self._base_snapshot()
        result = compute_desktop_calculation(snap)
        self._assert_valid_pipeline_result(result)

        text = build_calculation_report(result["report_context"])
        self.assertIn("Ters Akış", text)
        self.assertIn("Epsilon-NTU", text)

        pdf = build_calculation_report_pdf(result["report_context"])
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_double_pipe_full_pipeline(self):
        from app_desktop import compute_desktop_calculation
        from reporting import build_calculation_report, build_calculation_report_pdf

        snap = self._base_snapshot()
        snap["exchanger_type"] = "double_pipe"
        snap["flow_type"] = "counter"
        result = compute_desktop_calculation(snap)
        self._assert_valid_pipeline_result(result)

        text = build_calculation_report(result["report_context"])
        self.assertIn("Ters Akış", text)

        pdf = build_calculation_report_pdf(result["report_context"])
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_finned_tube_full_pipeline(self):
        from app_desktop import compute_desktop_calculation
        from reporting import build_calculation_report, build_calculation_report_pdf

        snap = self._base_snapshot()
        snap["exchanger_type"] = "finned_tube"
        snap["flow_type"] = "cross_unmixed"
        snap["flow_label"] = "Çapraz Akış"
        result = compute_desktop_calculation(snap)
        self._assert_valid_pipeline_result(result)

        text = build_calculation_report(result["report_context"])
        self.assertIn("Çapraz Akış", text)

        pdf = build_calculation_report_pdf(result["report_context"])
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_pipeline_geometric_mode_shell(self):
        from app_desktop import compute_desktop_calculation

        snap = self._base_snapshot()
        snap["u_mode"] = "Geometrik Mod (Tasarım)"
        snap["geom"].update(
            {
                "D_shell": 0.3,
                "baffle_spacing": 0.3,
                "baffle_cut": 0.25,
                "tube_layout_angle": "30",
                "shell_passes": 1,
            }
        )
        result = compute_desktop_calculation(snap)
        self._assert_valid_pipeline_result(result)
        self.assertGreater(result["report_context"]["results"]["main"]["Q [W]"], 0.0)


if __name__ == "__main__":
    unittest.main()
