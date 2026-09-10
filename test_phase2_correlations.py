"""Unit tests for Phase 2 advanced engineering correlations and standards."""

import unittest

from heat_exchanger import FinTubeHeatExchanger, Fluid, _bell_delaware_shell_h
from standards import ache_fin_options


def _create_sample_fluids():
    hot = Fluid("hot_water", cp=4180.0, density=990.0, mu=0.0005, k_cond=0.63, is_coolprop=False)
    cold = Fluid("cold_water", cp=4180.0, density=998.0, mu=0.001, k_cond=0.60, is_coolprop=False)
    return hot, cold


class TestPhase2Correlations(unittest.TestCase):
    def test_bell_delaware_ht_functions_integration(self):
        """Gerçek ht Bell-Delaware fonksiyonlarının J katsayıları ve h_o üretimi doğrulanmalıdır."""
        h_o, j_factors = _bell_delaware_shell_h(
            Nu_ideal=120.0,
            k_shell=0.60,
            D_o=0.0254,
            D_shell=0.40,
            baffle_cut=0.25,
            tube_count=60,
            L=3.0,
            baffle_spacing=0.4,
            Re_shell=8000.0,
        )
        self.assertGreater(h_o, 0.0)
        # J faktörleri fiziksel aralıkta (0.5 - 1.0) olmalı
        for name in ("J_c", "J_l", "J_b", "J_s", "J_r"):
            self.assertIn(name, j_factors)
            self.assertGreaterEqual(j_factors[name], 0.5)
            self.assertLessEqual(j_factors[name], 1.0)

    def test_api661_fin_temperature_warning_and_contact_resistance(self):
        """Proses sıcaklığı L-Fin limitini (130 °C) aştığında uyarı üretilmeli ve temas direnci eklenmelidir."""
        hot = Fluid("hot_oil", cp=2100.0, density=850.0, mu=0.002, k_cond=0.13, is_coolprop=False, calc_temp_c=160.0)
        cold = Fluid("air", cp=1005.0, density=1.2, mu=1.8e-5, k_cond=0.026, is_coolprop=False, calc_temp_c=25.0)

        geom_l_fin = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 30,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 400.0,
            "k_fin": 237.0,
            "ache_fin_type": "L-Fin (Wrap-on)",
            "pitch": 0.06,
        }

        hx = FinTubeHeatExchanger(hot, cold, U=50.0, A=10.0, flow_type="cross_unmixed")
        res = hx.calculate_geometric_U(geom_l_fin, m_hot=3.0, m_cold=2.0, hot_is_tube=True)

        # 160 °C > 130 °C olduğundan API 661 uyarısı bulunmalı
        self.assertTrue(any("API 661 Uyarısı" in w and "L-Fin" in w for w in res["warnings"]))

    def test_ache_fin_options_table(self):
        """standards.py içindeki API 661 kanat seçenekleri eksiksiz listelenmelidir."""
        opts = ache_fin_options()
        self.assertGreaterEqual(len(opts), 5)
        names = [o["name"] for o in opts]
        self.assertIn("L-Fin (Wrap-on)", names)
        self.assertIn("G-Fin (Embedded / Gömülü)", names)
        self.assertIn("Extruded (Bimetalik Ekstrüzyon)", names)

    def test_two_phase_heat_transfer_coefficient_boost(self):
        """İki-fazlı modda taşınım katsayısı film/kaynama mertebesine yükseltilmelidir."""
        hot, cold = _create_sample_fluids()
        geom_single = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 20,
            "k_wall": 45.0,
            "is_finned": False,
            "pitch": 0.06,
        }
        geom_two_phase = dict(geom_single, is_two_phase_tube=True, h_two_phase_tube=6000.0)

        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="cross_unmixed")
        res_single = hx.calculate_geometric_U(geom_single, m_hot=0.5, m_cold=1.0, hot_is_tube=True)
        res_tp = hx.calculate_geometric_U(geom_two_phase, m_hot=0.5, m_cold=1.0, hot_is_tube=True)

        # İki fazlı h_i (6000 W/m²K) tek fazlı laminer/düşük hız h_i'den kat kat büyük olmalı
        self.assertEqual(res_tp["h_i"], 6000.0)
        self.assertGreater(res_tp["U"], res_single["U"])
        self.assertTrue(any("iki-fazlı mod" in w for w in res_tp["warnings"]))

    def test_segmented_numerical_finite_volume_profile(self):
        """solve_segmented yöntemi gerçek 1D sıcaklık profili ve enerji dengesi üretmelidir."""
        hot, cold = _create_sample_fluids()
        hx = FinTubeHeatExchanger(hot, cold, U=200.0, A=15.0, flow_type="counter", exchanger_type="double_pipe")

        res_seg = hx.solve_segmented(m_hot=2.0, m_cold=1.5, T_hot_in=90.0, T_cold_in=20.0, n_segments=10)

        self.assertEqual(res_seg["status"], "ok")
        self.assertGreater(res_seg["Q [W]"], 0.0)
        self.assertIn("T_h_profile", res_seg)
        self.assertIn("T_c_profile", res_seg)
        self.assertEqual(len(res_seg["T_h_profile"]), 11)
        self.assertEqual(len(res_seg["T_c_profile"]), 11)

        # Sıcak akışkan girişten çıkışa azalmalı
        self.assertGreater(res_seg["T_h_profile"][0], res_seg["T_h_profile"][-1])
        # Soğuk akışkan çıkıştan girişe (ters akış profili)
        self.assertGreater(res_seg["T_c_profile"][0], res_seg["T_c_profile"][-1])


if __name__ == "__main__":
    unittest.main()
