"""Unit tests for Phase 3: Software Architecture, i18n, app_shared, and units cleanup."""

import unittest

import app_shared
import i18n
import standards
import units
from heat_exchanger import EXCHANGER_TYPE_FINNED, FinTubeHeatExchanger, Fluid


class TestAppShared(unittest.TestCase):
    """Verify shared application constants and helpers."""

    def test_flow_mappings_bidirectional(self):
        for label, internal in app_shared.FLOW_LABEL_TO_INTERNAL.items():
            self.assertEqual(app_shared.FLOW_INTERNAL_TO_LABEL[internal], label)

    def test_exchanger_mappings_bidirectional(self):
        for label, internal in app_shared.EXCHANGER_LABEL_TO_INTERNAL.items():
            self.assertEqual(app_shared.EXCHANGER_INTERNAL_TO_LABEL[internal], label)

    def test_safe_index(self):
        opts = ["Alpha", "Beta", "Gamma"]
        self.assertEqual(app_shared.safe_index(opts, "Beta"), 1)
        self.assertEqual(app_shared.safe_index(opts, "Omega", default=0), 0)
        self.assertEqual(app_shared.safe_index(opts, None, default=2), 2)

    def test_mixture_presets_not_empty(self):
        self.assertIn("Doğal Gaz", app_shared.MIXTURE_PRESETS)
        for name, preset in app_shared.MIXTURE_PRESETS.items():
            self.assertTrue(len(preset) > 0, f"Preset {name} is empty")
            total = sum(preset.values())
            self.assertAlmostEqual(total, 100.0, delta=5.0)


class TestI18nCatalog(unittest.TestCase):
    """Verify gettext i18n translation switching between TR and EN."""

    def tearDown(self):
        i18n.set_language("tr")

    def test_turkish_default(self):
        i18n.set_language("tr")
        self.assertEqual(i18n.get_language(), "tr")
        self.assertEqual(i18n._("Sıcak akışkan debisi"), "Sıcak akışkan debisi")
        self.assertEqual(i18n._("Isı Değiştirici Hesap Raporu"), "Isı Değiştirici Hesap Raporu")

    def test_english_translation(self):
        i18n.set_language("en")
        self.assertEqual(i18n.get_language(), "en")
        self.assertEqual(i18n._("Sıcak akışkan debisi"), "Hot fluid mass flow rate")
        self.assertEqual(i18n._("Isı Değiştirici Hesap Raporu"), "Heat Exchanger Calculation Report")
        self.assertEqual(i18n._("1. Secilen Yontemler"), "1. Selected Methods")
        self.assertEqual(i18n._("Enerji dengesi sapması"), "Energy balance deviation")


class TestUnitsModule(unittest.TestCase):
    """Verify unicode normalization and robust decoding in units.py."""

    def test_celsius_normalizations(self):
        self.assertAlmostEqual(units.to_celsius(100.0, "°C"), 100.0)
        self.assertAlmostEqual(units.to_celsius(212.0, "°F"), 100.0, places=1)
        self.assertAlmostEqual(units.to_celsius(373.15, "K"), 100.0, places=1)

    def test_celsius_mojibake_tolerance(self):
        # Mojibake stringler de güvenle çözülmeli
        self.assertAlmostEqual(units.to_celsius(100.0, "Â°C"), 100.0)
        self.assertAlmostEqual(units.to_celsius(100.0, "Ã‚Â°C"), 100.0)

    def test_mass_flow_conversions(self):
        self.assertAlmostEqual(units.to_kg_s(3600.0, "kg/h", density=1000.0), 1.0)
        self.assertAlmostEqual(units.to_kg_s(1.0, "m³/s", density=850.0), 850.0)
        self.assertAlmostEqual(units.to_kg_s(3600.0, "m³/h", density=1000.0), 1000.0)


class TestApi661FinAttachmentIntegration(unittest.TestCase):
    """Verify API 661 fin attachment is integrated with calculate_geometric_U."""

    def test_ache_fin_names_list(self):
        names = standards.ache_fin_names()
        self.assertGreaterEqual(len(names), 5)
        self.assertTrue(any("L-Fin" in n for n in names))
        self.assertTrue(any("Extruded" in n for n in names))

    def test_fin_attachment_passes_to_solver(self):
        hot_fluid = Fluid(calc_temp_c=180.0, density=980.0, cp=4180.0, mu=0.0003, k_cond=0.6)
        cold_fluid = Fluid(calc_temp_c=25.0, density=1.2, cp=1005.0, mu=1.8e-5, k_cond=0.026)
        hx = FinTubeHeatExchanger(hot_fluid, cold_fluid, U=50.0, A=10.0, exchanger_type=EXCHANGER_TYPE_FINNED)
        hx.flow_type = "cross_unmixed"

        geom = {
            "D_o": 0.0254,
            "D_i": 0.0211,
            "L": 4.0,
            "N_tubes": 50,
            "k_wall": 45.0,
            "is_finned": True,
            "fin_height": 0.0159,
            "fin_thickness": 0.0004,
            "fin_density": 400.0,
            "k_fin": 237.0,
            "fin_type": "annular",
            "fin_attachment": "L-Fin (Wrap-on)",
            "pitch": 0.06,
        }
        res = hx.calculate_geometric_U(geom, m_hot=5.0, m_cold=15.0, hot_is_tube=True)
        # L-Fin sıcaklık limiti 130°C, proses 180°C -> API 661 uyarısı üretmeli
        warnings = res.get("warnings", [])
        self.assertTrue(any("API 661" in w for w in warnings), f"Expected API 661 warning in: {warnings}")


if __name__ == "__main__":
    unittest.main()
