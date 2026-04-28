import unittest

from heat_exchanger import FinTubeHeatExchanger, Fluid
from fluids_db import get_chedl_mixture_fluid_data, get_fluid_data, materialize_fluid_data


class HeatExchangerRegressionTests(unittest.TestCase):
    def test_counterflow_lmtd_matches_ntu_in_high_effectiveness_case(self):
        hot = Fluid(name="hot", cp=4000.0, density=1000.0, mu=1e-3, k_cond=0.6, is_coolprop=False)
        cold = Fluid(name="cold", cp=4000.0, density=1000.0, mu=1e-3, k_cond=0.6, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=5000.0, A=100.0, flow_type="counter")

        ntu_res = hx.solve_ntu(1.0, 1.0, 100.0, 0.0, source="custom")
        lmtd_res = hx.solve_lmtd(1.0, 1.0, 100.0, 0.0, source="ht")

        self.assertAlmostEqual(lmtd_res["Q [W]"], ntu_res["Q [W]"], delta=ntu_res["Q [W]"] * 0.01)
        self.assertAlmostEqual(
            lmtd_res["T_hot_out [C]"], ntu_res["T_hot_out [C]"], delta=1.0
        )
        self.assertAlmostEqual(
            lmtd_res["T_cold_out [C]"], ntu_res["T_cold_out [C]"], delta=1.0
        )

    def test_geometric_u_works_with_manual_fluid_density(self):
        hot = Fluid(name="hot", cp=1100.0, density=0.5, mu=2e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=2200.0, density=850.0, mu=0.003, k_cond=0.12, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="cross_unmixed")

        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 400,
            "k_fin": 237.0,
            "pitch": 0.06,
        }

        result = hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=False)

        self.assertGreater(result["U"], 0.0)
        self.assertGreater(result["A_total"], 0.0)
        self.assertGreater(result["Re_i"], 0.0)
        self.assertGreater(result["Re_o"], 0.0)

    def test_ntu_rejects_nonphysical_inputs(self):
        hot = Fluid(name="hot", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=10.0, A=10.0, flow_type="counter")

        with self.assertRaises(ValueError):
            hx.solve_ntu(0.0, 1.0, 100.0, 0.0)
        with self.assertRaises(ValueError):
            hx.solve_ntu(1.0, 1.0, 0.0, 100.0)

    def test_thermal_oil_correlation_uses_temperature(self):
        data = materialize_fluid_data(get_fluid_data("Therminol 66"), T_c=100.0)

        self.assertFalse(data["is_coolprop"])
        self.assertAlmostEqual(data["cp"], 1500.0 + 3.2 * 100.0)

    def test_chedl_mixture_properties_are_available(self):
        comps = {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0}
        total = sum(comps.values())
        mole_fracs = {name: value / total for name, value in comps.items()}

        result = get_chedl_mixture_fluid_data(comps, mole_fracs, T_c=200.0, P_pa=101325.0)

        self.assertEqual(result["property_source"], "ChEDL/thermo")
        self.assertGreater(result["cp"], 0.0)
        self.assertGreater(result["density"], 0.0)
        self.assertGreater(result["mu"], 0.0)
        self.assertGreater(result["k_cond"], 0.0)

    def test_geometric_u_rejects_invalid_fin_spacing(self):
        hot = Fluid(name="hot", cp=1100.0, density=0.5, mu=2e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=2200.0, density=850.0, mu=0.003, k_cond=0.12, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=1.0, A=1.0, flow_type="cross_unmixed")
        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_tubes": 100,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": 0.0159,
            "fin_thickness": 0.003,
            "fin_density": 400,
            "k_fin": 237.0,
            "pitch": 0.06,
        }

        with self.assertRaises(ValueError):
            hx.calculate_geometric_U(geom, m_hot=15.0, m_cold=5.0, hot_is_tube=False)

    def test_pychemengg_validation_is_optional(self):
        hot = Fluid(name="hot", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=10.0, A=10.0, flow_type="counter")

        result = hx.solve_pychemengg_ntu(1.0, 1.0, 100.0, 0.0)

        self.assertEqual(result["Source"], "PyChemEngg")
        self.assertGreater(result["Q [W]"], 0.0)


if __name__ == "__main__":
    unittest.main()
