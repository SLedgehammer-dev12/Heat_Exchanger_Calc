"""Regression tests for the engineering improvement plan (Faz 1+)."""

import unittest

import numpy as np

from config import EXCHANGER_TYPE_SHELL
from heat_exchanger import FinTubeHeatExchanger, Fluid
from model_types import GeometryInput


def _fluids():
    return Fluid("hot", cp=1100, density=0.5, mu=2e-5, k_cond=0.03), Fluid(
        "cold", cp=2200, density=850, mu=0.003, k_cond=0.12
    )


class TestCrossMixedUnmixedFBranch(unittest.TestCase):
    """Faz 1.1: cross_mixed_unmixed F-faktörü Cmin/Cmax dallanması."""

    def _hx(self):
        hot, cold = _fluids()
        return FinTubeHeatExchanger(
            hot, cold, U=100.0, A=10.0, flow_type="cross_mixed_unmixed", exchanger_type="finned_tube"
        )

    def test_both_branches_in_range(self):
        hx = self._hx()
        # C_h >= C_c  -> Cmax karışmış
        f_high = hx._calc_crossflow_F(100.0, 20.0, 70.0, 80.0, C_h=200.0, C_c=100.0, warnings=[])
        # C_h < C_c   -> Cmin karışmış
        f_low = hx._calc_crossflow_F(100.0, 20.0, 40.0, 50.0, C_h=100.0, C_c=200.0, warnings=[])
        for f in (f_high, f_low):
            self.assertTrue(np.isfinite(f), f"F sonlu olmalı: {f}")
            self.assertGreaterEqual(f, 0.01)
            self.assertLessEqual(f, 1.0)

    def test_branches_do_not_collapse(self):
        hx = self._hx()
        f_high = hx._calc_crossflow_F(100.0, 20.0, 70.0, 80.0, C_h=200.0, C_c=100.0, warnings=[])
        f_low = hx._calc_crossflow_F(100.0, 20.0, 40.0, 50.0, C_h=100.0, C_c=200.0, warnings=[])
        # Aynı Cr ve epsilon koşullarında iki ters fonksiyon farklı F üretir.
        self.assertNotAlmostEqual(f_high, f_low, delta=1e-6)


class TestBowmanTubePasses(unittest.TestCase):
    """Faz 1.2: shell_passes/tube_passes kablolaması."""

    def _hx(self):
        hot, cold = _fluids()
        return FinTubeHeatExchanger(
            hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL
        )

    def test_single_tube_pass_is_counterflow_F1(self):
        hx = self._hx()
        hx.tube_passes = 1
        f = hx._calc_lmtd_F(100.0, 20.0, 60.0, 60.0, 1000.0, 1000.0)
        self.assertEqual(f, 1.0)

    def test_multi_tube_pass_lowers_F(self):
        hx = self._hx()
        hx.tube_passes = 2
        f2 = hx._calc_lmtd_F(100.0, 20.0, 60.0, 60.0, 1000.0, 1000.0)
        self.assertLess(f2, 1.0)
        self.assertGreater(f2, 0.0)

    def test_tube_passes_from_geometry(self):
        hot, cold = _fluids()
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL)
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "D_shell": 0.5,
            "pitch": 0.03175,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "30",
            "shell_passes": 1,
            "tube_passes": 4,
            "baffle_cut": 0.25,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        self.assertEqual(hx.tube_passes, 4)
        self.assertEqual(hx.baffle_cut, 0.25)

    def test_baffle_cut_out_of_tema_warns(self):
        hot, cold = _fluids()
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL)
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "D_shell": 0.5,
            "pitch": 0.03175,
            "baffle_spacing": 0.6,
            "tube_layout_angle": "30",
            "baffle_cut": 0.5,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=True)
        self.assertTrue(any("baffle cut" in w for w in res["warnings"]))


class TestLaminarEntrance(unittest.TestCase):
    """Faz 1.3: laminer termal giriş bölgesi (Hausen/Graetz)."""

    def _hx(self):
        hot, cold = _fluids()
        return FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type="double_pipe")

    def test_entrance_increases_nu(self):
        hx = self._hx()
        nu_entrance = hx._nusselt_internal(1000.0, 100.0, 0.4, 3.66, "test", [], gz=1000.0)
        self.assertGreater(nu_entrance, 3.66)

    def test_no_gz_returns_constant(self):
        hx = self._hx()
        nu_const = hx._nusselt_internal(1000.0, 100.0, 0.4, 3.66, "test", [], gz=None)
        self.assertAlmostEqual(nu_const, 3.66, delta=1e-9)


class TestGeometryInputNewFields(unittest.TestCase):
    """Faz 1.4: GeometryInput tube_passes alanı seri hale getirme."""

    def test_tube_passes_roundtrip(self):
        g = GeometryInput(
            D_o=0.0254, D_i=0.0211, L=3.0, N_tubes=100, exchanger_type=EXCHANGER_TYPE_SHELL, tube_passes=4
        )
        d = g.to_dict()
        self.assertEqual(d["tube_passes"], 4)
        g2 = GeometryInput.from_dict(d)
        self.assertEqual(g2.tube_passes, 4)

    def test_default_tube_passes(self):
        g = GeometryInput(D_o=0.0254, D_i=0.0211, L=3.0, N_tubes=100)
        self.assertEqual(g.tube_passes, 2)


class TestPumpPowerAndLocalLosses(unittest.TestCase):
    """Faz 2.1/2.2: pompa gücü ve çok geçişli lokal kayıplar."""

    def _shell_geom(self, tube_passes=2, baffle_spacing=0.6):
        return {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "D_shell": 0.5,
            "pitch": 0.03175,
            "baffle_spacing": baffle_spacing,
            "tube_layout_angle": "30",
            "shell_passes": 1,
            "tube_passes": tube_passes,
            "baffle_cut": 0.25,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }

    def test_pump_power_keys_present(self):
        hot, cold = _fluids()
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL)
        res = hx.calculate_geometric_U(self._shell_geom(), m_hot=12.0, m_cold=8.0, hot_is_tube=True)
        self.assertIn("pump_power_tube", res)
        self.assertIn("pump_power_shell", res)
        self.assertGreaterEqual(res["pump_power_tube"], 0.0)
        self.assertGreaterEqual(res["pump_power_shell"], 0.0)

    def test_multipass_increases_tube_pressure_drop(self):
        hot, cold = _fluids()
        hx1 = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL)
        r1 = hx1.calculate_geometric_U(self._shell_geom(tube_passes=1), m_hot=12.0, m_cold=8.0, hot_is_tube=True)
        hx4 = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL)
        r4 = hx4.calculate_geometric_U(self._shell_geom(tube_passes=4), m_hot=12.0, m_cold=8.0, hot_is_tube=True)
        self.assertGreater(r4["delta_p_tube"], r1["delta_p_tube"])


class TestVibrationScreening(unittest.TestCase):
    """Faz 2.3: TEMA titreşim ön kontrolü."""

    def test_unsupported_span_warning(self):
        hot, cold = _fluids()
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="counter", exchanger_type=EXCHANGER_TYPE_SHELL)
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "D_shell": 0.5,
            "pitch": 0.03175,
            "baffle_spacing": 2.0,  # > 60*D_o = 1.524
            "tube_layout_angle": "30",
            "shell_passes": 1,
            "tube_passes": 2,
            "baffle_cut": 0.25,
            "R_f_i": 0.0,
            "R_f_o": 0.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=12.0, m_cold=8.0, hot_is_tube=True)
        self.assertTrue(any("baffle aralığı" in w or "Titreşim" in w for w in res["warnings"]))


class TestSchmidtPlateFin(unittest.TestCase):
    """Faz 2.5: Schmidt plaka-kanat modeli."""

    def test_plate_fin_efficiency_in_range(self):
        from heat_exchanger import _fin_efficiency

        eta = _fin_efficiency("plate", h_o=100.0, k_fin=237.0, fin_thickness=0.0004, fin_height=0.0159, D_o=0.0254,
                              pitch=0.06, pitch_parallel=0.06)
        self.assertGreaterEqual(eta, 0.0)
        self.assertLessEqual(eta, 1.0)


class TestStandardsModule(unittest.TestCase):
    """Faz 2.4: BWG + TEMA fouling presets."""

    def test_tube_presets_valid(self):
        from standards import tube_preset_options

        opts = tube_preset_options()
        self.assertGreater(len(opts), 0)
        for o in opts:
            self.assertLess(o["D_i_mm"], o["D_o_mm"])

    def test_fouling_presets_valid(self):
        from standards import fouling_preset_options

        opts = fouling_preset_options()
        self.assertGreater(len(opts), 0)
        for _lbl, val in opts:
            self.assertGreaterEqual(val, 0.0)


class TestRunSolvers(unittest.TestCase):
    """Faz 4.1: run_solvers çekirdek kapsüllemesi."""

    def test_run_solvers_returns_four(self):
        hot, cold = _fluids()
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type="double_pipe")
        results = hx.run_solvers(3.0, 2.0, 90.0, 20.0)
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertIn("Q [W]", r)


class TestPhaseChangeSolvers(unittest.TestCase):
    """Faz 4.3: kondenser/evaporatör (Cr=0) çözücüleri."""

    def _hx(self):
        hot = Fluid("Steam", cp=2000, density=1.0, mu=1e-5, k_cond=0.03, h_fg=2.2e6)
        cold = Fluid("Water", cp=4180, density=995, mu=6.9e-4, k_cond=0.62)
        return FinTubeHeatExchanger(hot, cold, U=500.0, A=20.0, flow_type="counter", exchanger_type="double_pipe")

    def test_condenser_basic(self):
        hx = self._hx()
        res = hx.solve_condenser(m_hot=1.0, m_cold=5.0, T_sat=100.0, T_cold_in=20.0)
        self.assertGreater(res["Q [W]"], 0)
        self.assertGreater(res["T_cold_out [C]"], 20.0)
        self.assertEqual(res["C_r"], 0.0)

    def test_condenser_latent_limit(self):
        hx = self._hx()
        res = hx.solve_condenser(m_hot=0.1, m_cold=5.0, T_sat=100.0, T_cold_in=20.0)
        self.assertLessEqual(res["Q [W]"], res["Q_max [W]"])

    def test_evaporator_basic(self):
        hx = self._hx()
        res = hx.solve_evaporator(m_hot=5.0, m_cold=1.0, T_hot_in=90.0, T_sat=10.0, h_fg=2.2e6)
        self.assertGreater(res["Q [W]"], 0)
        self.assertLess(res["T_hot_out [C]"], 90.0)

    def test_requires_h_fg(self):
        hot = Fluid("Steam", cp=2000, density=1.0, mu=1e-5, k_cond=0.03)
        cold = Fluid("Water", cp=4180, density=995, mu=6.9e-4, k_cond=0.62)
        hx = FinTubeHeatExchanger(hot, cold, U=500.0, A=20.0, flow_type="counter", exchanger_type="double_pipe")
        with self.assertRaises(ValueError):
            hx.solve_condenser(m_hot=1.0, m_cold=5.0, T_sat=100.0, T_cold_in=20.0)


if __name__ == "__main__":
    unittest.main()
