"""Unit tests for Phase 1 critical thermal, hydraulic, and mechanical fixes."""

import unittest

import numpy as np

from heat_exchanger import FinTubeHeatExchanger, Fluid
from mechanical import asme_wall_thickness, mechanical_design_report


def _create_sample_fluids():
    hot = Fluid("hot_water", cp=4180.0, density=990.0, mu=0.0005, k_cond=0.63, is_coolprop=False)
    cold = Fluid("cold_air", cp=1005.0, density=1.2, mu=1.8e-5, k_cond=0.026, is_coolprop=False)
    return hot, cold


class TestPhase1ThermalHydraulicFixes(unittest.TestCase):
    def test_multipass_tube_velocity_and_reynolds(self):
        """Çok geçişli boruda hız ve Re sayısı N_pass ile doğru orantılı artmalıdır."""
        hot, cold = _create_sample_fluids()
        geom_base = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 40,
            "k_wall": 45.0,
            "is_finned": False,
            "pitch": 0.06,
        }

        hx1 = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="cross_unmixed")
        hx1.tube_passes = 1
        res1 = hx1.calculate_geometric_U(geom_base, m_hot=5.0, m_cold=2.0, hot_is_tube=True)

        hx2 = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="cross_unmixed")
        hx2.tube_passes = 2
        res2 = hx2.calculate_geometric_U(geom_base, m_hot=5.0, m_cold=2.0, hot_is_tube=True)

        # 2 geçişte geçiş kesit alanı yarıya iner, hız 2 katına çıkar
        self.assertAlmostEqual(res2["Re_i"], 2.0 * res1["Re_i"], delta=res1["Re_i"] * 0.01)
        # İç taşınım katsayısı daha yüksek olmalı
        self.assertGreater(res2["h_i"], res1["h_i"])
        # Basınç kaybı akış boyu 2 kat ve v^2 nedeniyle çok daha büyük olmalı
        self.assertGreater(res2["delta_p_tube"], 2.0 * res1["delta_p_tube"])

    def test_annular_fin_surface_area_exact(self):
        """Dairesel kanadın tam dış alanı, eski eksik düz şerit alanından belirgin şekilde büyük olmalıdır."""
        hot, cold = _create_sample_fluids()
        D_o = 0.0254
        D_i = 0.0211
        L = 2.0
        N = 10
        fin_h = 0.0159
        fin_t = 0.0004
        fin_dens = 400.0

        geom_finned = {
            "D_o": D_o,
            "D_i": D_i,
            "L": L,
            "N_tubes": N,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": fin_h,
            "fin_thickness": fin_t,
            "fin_density": fin_dens,
            "k_fin": 237.0,
            "fin_type": "annular",
            "pitch": 0.06,
        }

        hx = FinTubeHeatExchanger(hot, cold, U=50.0, A=10.0, flow_type="cross_unmixed")
        res = hx.calculate_geometric_U(geom_finned, m_hot=2.0, m_cold=1.0, hot_is_tube=True)

        # Eski eksik formül: A_o * (1 + 2 * fin_h * fin_dens)
        A_o = np.pi * D_o * L * N
        A_old_approx = A_o * (1.0 + 2.0 * fin_h * fin_dens)

        # Gerçek dairesel alan bu eski yaklaşımdan belirgin şekilde büyük olmalıdır (dışa genişleyen alan etkisi)
        self.assertGreater(res["A_total"], A_old_approx)

    def test_overall_surface_efficiency_eta_o(self):
        """Çıplak boru kök alanı verimi 1.0 olduğundan genel yüzey verimi eta_o >= eta_fin olmalıdır."""
        hot, cold = _create_sample_fluids()
        geom_finned = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 2.0,
            "N_tubes": 10,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 400.0,
            "k_fin": 237.0,
            "fin_type": "annular",
            "pitch": 0.06,
        }

        hx = FinTubeHeatExchanger(hot, cold, U=50.0, A=10.0, flow_type="cross_unmixed")
        res = hx.calculate_geometric_U(geom_finned, m_hot=2.0, m_cold=1.0, hot_is_tube=True)

        self.assertIn("eta_o", res)
        self.assertIn("eta_fin", res)
        self.assertGreaterEqual(res["eta_o"], res["eta_fin"])
        self.assertLessEqual(res["eta_o"], 1.0)

    def test_asme_outer_radius_and_tema_ca_zero(self):
        """ASME dış çapa göre formül çalışmalı ve raporda boru için CA=0 uygulanmalıdır."""
        P = 2.0e6
        R_o = 0.0127
        S = 110.0e6
        E = 0.85
        t_out = asme_wall_thickness(P, R_o, S, E, CA=0.0, use_outer_radius=True)
        expected_t = (P * R_o) / (S * E + 0.4 * P)
        self.assertAlmostEqual(t_out, expected_t, delta=1e-8)

        geom = {"D_shell": 0.5, "D_o": 0.0254, "design_pressure": 2.0e6, "corrosion_allowance": 0.003}
        rows = mechanical_design_report(geom)
        tube_row = next(r for r in rows if "Boru min" in r["label"])
        self.assertIn("CA=0", tube_row["label"])
        val_mm = float(tube_row["value"].replace(" mm", ""))
        self.assertLess(val_mm, 1.0)


if __name__ == "__main__":
    unittest.main()
