"""Unit tests for Phase 4: Industrial Deliverables, Material Library, Datasheet PDF, and CSV Export."""

import unittest

import config
from heat_exchanger import EXCHANGER_TYPE_FINNED, FinTubeHeatExchanger, Fluid
from reporting import (
    export_calculation_csv,
    export_profile_csv,
    generate_tema_datasheet_pdf,
)


class TestExpandedMaterialLibrary(unittest.TestCase):
    """Verify expanded industrial alloy properties in config.py."""

    def test_alloys_present_and_positive_k(self):
        required_alloys = [
            "Titanyum Gr. 2",
            "Admirallik Pirinci (C44300)",
            "Bakır-Nikel 90/10 (C70600)",
            "Bakır-Nikel 70/30 (C71500)",
            "Duplex Paslanmaz 2205",
            "Paslanmaz Çelik 304",
            "Inconel 625",
        ]
        for alloy in required_alloys:
            self.assertIn(alloy, config.TUBE_MATERIALS, f"Missing alloy: {alloy}")
            self.assertGreater(config.TUBE_MATERIALS[alloy], 0.0)

    def test_titanium_thermal_rating(self):
        hot_fluid = Fluid(calc_temp_c=80.0, density=970.0, cp=4180.0, mu=0.00035, k_cond=0.67)
        cold_fluid = Fluid(calc_temp_c=20.0, density=1025.0, cp=3990.0, mu=0.001, k_cond=0.60)
        hx = FinTubeHeatExchanger(
            hot_fluid, cold_fluid, U=100.0, A=10.0, flow_type="counter", exchanger_type="shell_and_tube"
        )

        geom = {
            "D_o": 0.01905,
            "D_i": 0.01655,
            "L": 3.0,
            "N_tubes": 80,
            "k_wall": config.TUBE_MATERIALS["Titanyum Gr. 2"],
            "D_shell": 0.35,
            "baffle_spacing": 0.15,
            "baffle_cut": 0.25,
        }
        res = hx.calculate_geometric_U(geom, m_hot=4.0, m_cold=10.0, hot_is_tube=True)
        self.assertGreater(res["U"], 100.0)
        self.assertGreater(res["A_total"], 1.0)


class TestMatrixGeometry(unittest.TestCase):
    """Verify N_T x N_L transverse and longitudinal row calculation."""

    def test_matrix_tubes_and_transverse_flow(self):
        hot_fluid = Fluid(calc_temp_c=90.0, density=965.0, cp=4190.0, mu=0.0003, k_cond=0.67)
        cold_fluid = Fluid(calc_temp_c=25.0, density=1.18, cp=1005.0, mu=1.8e-5, k_cond=0.026)
        hx = FinTubeHeatExchanger(hot_fluid, cold_fluid, U=50.0, A=10.0, exchanger_type=EXCHANGER_TYPE_FINNED)
        hx.flow_type = "cross_unmixed"

        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 3.0,
            "N_transverse": 12,
            "N_rows": 4,
            "pitch": 0.06,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 400.0,
            "k_fin": 237.0,
        }
        res = hx.calculate_geometric_U(geom, m_hot=2.0, m_cold=15.0, hot_is_tube=True)
        # 12 * 4 = 48 boru
        expected_bare = 48 * (3.1415926535 * 0.0254 * 3.0)
        self.assertAlmostEqual(res["A_bare_total"], expected_bare * max(0, 1 - 400 * 0.0004), delta=1.0)


class TestDatasheetAndExportOutputs(unittest.TestCase):
    """Verify 1-page TEMA/API 661 datasheet PDF and CSV outputs."""

    def setUp(self):
        self.sample_context = {
            "methods": {
                "Hesap amacı": "Proses Soğutucu",
                "Eşanjör tipi": "Gövde-Boru TEMA",
                "Akış tipi": "Ters Akış",
            },
            "inputs": {
                "m_hot_kg_s": 5.0,
                "T_hot_in_C": 90.0,
                "m_cold_kg_s": 8.0,
                "T_cold_in_C": 25.0,
            },
            "fluids": {
                "hot": {"label": "Su", "density": 980.0, "cp": 4180.0, "k_cond": 0.65, "mu": 0.0004},
                "cold": {"label": "Soğutma Suyu", "density": 998.0, "cp": 4182.0, "k_cond": 0.60, "mu": 0.001},
            },
            "geometry": {
                "D_o": 0.0254,
                "D_i": 0.0211,
                "L": 4.0,
                "N_tubes": 120,
                "D_shell": 0.5,
                "pitch": 0.03175,
                "baffle_spacing": 0.25,
                "baffle_cut": 0.25,
                "tube_material": "Karbon Çelik",
                "tema_designation": "BEM",
                "tube_passes": 2,
                "shell_passes": 1,
            },
            "results": {
                "main": {
                    "Q [W]": 450000.0,
                    "T_hot_out [C]": 68.5,
                    "T_cold_out [C]": 38.4,
                    "epsilon": 0.55,
                    "LMTD": 45.2,
                    "F": 0.95,
                    "U": 850.0,
                    "A": 12.5,
                }
            },
            "actual_result": {
                "U": 850.0,
                "A_total": 12.5,
                "h_i": 2500.0,
                "h_o": 1800.0,
                "delta_p_tube_kPa": 18.5,
                "delta_p_shell_kPa": 24.2,
                "T_h_profile": [90.0, 85.0, 80.0, 75.0, 70.0, 68.5],
                "T_c_profile": [25.0, 28.0, 31.0, 34.0, 36.5, 38.4],
            },
        }

    def test_generate_tema_datasheet_pdf(self):
        pdf_bytes = generate_tema_datasheet_pdf(self.sample_context)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "Output is not a valid PDF header")
        self.assertGreater(len(pdf_bytes), 2000, "PDF output is too small")

    def test_export_calculation_csv(self):
        csv_str = export_calculation_csv(self.sample_context)
        self.assertIsInstance(csv_str, str)
        self.assertIn("HEAT EXCHANGER CALCULATION EXPORT", csv_str)
        self.assertIn("OPERATING CONDITIONS", csv_str)
        self.assertIn("THERMAL PERFORMANCE", csv_str)
        self.assertIn("GEOMETRY PARAMETERS", csv_str)
        self.assertIn("Su", csv_str)
        self.assertIn("450000", csv_str)

    def test_export_profile_csv(self):
        profile_csv = export_profile_csv(self.sample_context)
        self.assertIsInstance(profile_csv, str)
        self.assertIn("Segment,Length_Fraction,T_hot_C,T_cold_C,Delta_T_C", profile_csv)
        self.assertIn("90.0", profile_csv)
        self.assertIn("25.0", profile_csv)


if __name__ == "__main__":
    unittest.main()
