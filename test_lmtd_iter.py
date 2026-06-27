import hashlib
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app_desktop import compute_desktop_calculation
from engineering_utils import fluid_report_data, from_celsius, result_warnings, to_celsius, to_kg_s
from fluids_db import get_chedl_mixture_fluid_data, get_fluid_data, get_mixture_fluid_data, materialize_fluid_data
from heat_exchanger import EXCHANGER_TYPE_DOUBLE, EXCHANGER_TYPE_SHELL, FinTubeHeatExchanger, Fluid

HX_SHELL = EXCHANGER_TYPE_SHELL
HX_DOUBLE = EXCHANGER_TYPE_DOUBLE
from exceptions import UpdaterError
from reporting import build_calculation_report, build_calculation_report_pdf
from updater import download_release_asset, select_release_asset


class _FakeUrlOpen:
    def __init__(self, payload):
        self._stream = BytesIO(payload)

    def __enter__(self):
        return self._stream

    def __exit__(self, exc_type, exc, tb):
        self._stream.close()
        return False


def _manual_snapshot(**overrides):
    snapshot = {
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
    snapshot.update(overrides)
    return snapshot


class HeatExchangerRegressionTests(unittest.TestCase):
    def test_counterflow_lmtd_matches_ntu_in_high_effectiveness_case(self):
        hot = Fluid(name="hot", cp=4000.0, density=1000.0, mu=1e-3, k_cond=0.6, is_coolprop=False)
        cold = Fluid(name="cold", cp=4000.0, density=1000.0, mu=1e-3, k_cond=0.6, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=5000.0, A=100.0, flow_type="counter", exchanger_type=HX_DOUBLE)

        ntu_res = hx.solve_ntu(1.0, 1.0, 100.0, 0.0, source="custom")
        lmtd_res = hx.solve_lmtd(1.0, 1.0, 100.0, 0.0, source="ht")

        self.assertAlmostEqual(lmtd_res["Q [W]"], ntu_res["Q [W]"], delta=ntu_res["Q [W]"] * 0.01)
        self.assertAlmostEqual(lmtd_res["T_hot_out [C]"], ntu_res["T_hot_out [C]"], delta=1.0)
        self.assertAlmostEqual(lmtd_res["T_cold_out [C]"], ntu_res["T_cold_out [C]"], delta=1.0)

    def test_lmtd_result_contains_report_crosscheck_fields(self):
        hot = Fluid(name="hot", cp=2000.0, density=900.0, mu=1e-3, k_cond=0.2, is_coolprop=False)
        cold = Fluid(name="cold", cp=4200.0, density=1000.0, mu=1e-3, k_cond=0.6, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=250.0, A=20.0, flow_type="counter", exchanger_type=HX_DOUBLE)

        result = hx.solve_lmtd(1.5, 2.0, 160.0, 30.0, source="ht")

        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["Q [W]"], 0.0)
        for key in ("epsilon", "NTU", "C_r", "T_hot_in [C]", "T_cold_in [C]"):
            self.assertIn(key, result)

    def test_actual_performance_flags_energy_balance_mismatch(self):
        hot = Fluid(name="hot", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type=HX_SHELL)

        result = hx.calculate_actual_performance(1.0, 1.0, 100.0, 0.0, 70.0, 10.0)

        self.assertEqual(result["status"], "warning")
        self.assertGreater(result["energy_balance_error_fraction"], 0.05)
        self.assertTrue(any("Enerji dengesi" in msg for msg in result["warnings"]))

    def test_geometric_u_includes_fouling_resistance(self):
        hot = Fluid(name="hot", cp=1100.0, density=0.5, mu=2e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=2200.0, density=850.0, mu=0.003, k_cond=0.12, is_coolprop=False)
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
        self.assertEqual(fouled["R_f_i"], 0.002)
        self.assertEqual(fouled["R_f_o"], 0.002)

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
        hx = FinTubeHeatExchanger(hot, cold, U=10.0, A=10.0, flow_type="counter", exchanger_type=HX_SHELL)

        with self.assertRaises(ValueError):
            hx.solve_ntu(0.0, 1.0, 100.0, 0.0)
        with self.assertRaises(ValueError):
            hx.solve_ntu(1.0, 1.0, 0.0, 100.0)

    def test_cross_mixed_unmixed_custom_respects_capacity_side(self):
        hot = Fluid(name="hot", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=2000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="cross_mixed_unmixed")

        custom = hx.solve_ntu(1.0, 2.0, 200.0, 20.0, source="custom")
        reference = hx.solve_ntu(1.0, 2.0, 200.0, 20.0, source="ht")

        self.assertAlmostEqual(custom["epsilon"], reference["epsilon"], delta=1e-9)

    def test_empty_mixture_composition_is_rejected(self):
        with self.assertRaises(ValueError):
            get_mixture_fluid_data({}, comp_type="mole", T_c=200.0, P_pa=101325.0)

    def test_unknown_mixture_component_is_rejected(self):
        with self.assertRaises(ValueError):
            get_mixture_fluid_data({"UnknownGas": 100.0}, comp_type="mole", T_c=200.0, P_pa=101325.0)

    def test_mass_basis_mixture_normalization_returns_physical_properties(self):
        result = get_mixture_fluid_data(
            {"Nitrogen": 70.0, "Oxygen": 20.0, "CarbonDioxide": 10.0},
            comp_type="mass",
            T_c=180.0,
            P_pa=101325.0,
        )

        self.assertIn(
            result["property_source"],
            {
                "CoolProp HEOS mixture",
                "CoolProp ideal mixture",
                "ChEDL/thermo",
                "Wilke viscosity + Wassiljewa conductivity",
            },
        )
        self.assertGreater(result["cp"], 0.0)
        self.assertGreater(result["density"], 0.0)
        self.assertGreater(result["mu"], 0.0)
        self.assertGreater(result["k_cond"], 0.0)

    def test_correlation_temperature_limits_emit_warning(self):
        data = materialize_fluid_data(get_fluid_data("Therminol 66"), T_c=500.0)

        self.assertTrue(data["warnings"])
        self.assertIn("cp", data)

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
        hx = FinTubeHeatExchanger(hot, cold, U=10.0, A=10.0, flow_type="counter", exchanger_type=HX_SHELL)

        result = hx.solve_pychemengg_ntu(1.0, 1.0, 100.0, 0.0)

        self.assertEqual(result["Source"], "PyChemEngg")
        self.assertGreater(result["Q [W]"], 0.0)

    def test_engineering_utils_conversions_and_warning_deduplication(self):
        self.assertAlmostEqual(to_kg_s(3600.0, "kg/h", density=1.0), 1.0)
        self.assertAlmostEqual(to_kg_s(2.0, "m3/s", density=3.0), 6.0)
        self.assertAlmostEqual(to_kg_s(2.0, "mÂ³/s", density=3.0), 6.0)
        self.assertAlmostEqual(to_celsius(212.0, "Â°F"), 100.0)
        self.assertAlmostEqual(from_celsius(100.0, "Â°F"), 212.0)

        warnings = result_warnings({"warnings": ["a", "b"]}, {"warnings": ["a"]})
        self.assertEqual(warnings, ["a", "b"])

    def test_fluid_report_data_prefers_property_source(self):
        fluid = Fluid(name="manual", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)

        result = fluid_report_data("label", {"property_source": "test-source"}, fluid)

        self.assertEqual(result["source"], "test-source")
        self.assertEqual(result["property_source"], "test-source")

    def test_reporting_text_and_pdf_include_fouling_formula(self):
        hot = Fluid(name="hot", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type=HX_DOUBLE)
        main = hx.solve_ntu(1.0, 1.0, 100.0, 0.0)
        context = {
            "methods": {
                "Hesap amacı": "test",
                "Akış tipi": "counter",
                "Akış tipi internal": "counter",
                "Ana çözücü": "test",
                "U modu": "Geometrik Mod",
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
            "fluids": {"hot": fluid_report_data("hot", {}, hot), "cold": fluid_report_data("cold", {}, cold)},
            "geometry": {"R_f_i": 0.001, "R_f_o": 0.002},
            "geo_result": {
                "U": 100.0,
                "A_total": 10.0,
                "h_i": 500.0,
                "h_o": 100.0,
                "Re_i": 10000.0,
                "Re_o": 20000.0,
                "R_wall": 0.0001,
            },
            "results": {"main": main},
            "actual_result": None,
            "crosscheck_results": [main],
        }

        text = build_calculation_report(context)
        pdf = build_calculation_report_pdf(context)

        self.assertIn("Fouling iç", text)
        self.assertIn("Fouling dış", text)
        self.assertIn("Gnielinski", text)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_enhanced_schematic_can_show_temperatures(self):
        hot = Fluid(name="hot", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        cold = Fluid(name="cold", cp=1000.0, density=1.0, mu=1e-5, k_cond=0.03, is_coolprop=False)
        hx = FinTubeHeatExchanger(hot, cold, U=100.0, A=10.0, flow_type="counter", exchanger_type=HX_SHELL)
        result = hx.solve_ntu(1.0, 1.0, 100.0, 0.0)

        fig = hx.plot_enhanced_schematic(result=result)
        text = "\n".join(item.get_text() for item in fig.axes[0].texts)

        self.assertIn("100.0 °C", text)
        self.assertIn("0.0 °C", text)

    def test_web_source_exposes_cross_mixed_unmixed_option(self):
        source = Path("app_web.py").read_text(encoding="utf-8")

        self.assertIn("cross_mixed_unmixed", source)
        self.assertIn("report_context", source)

    def test_desktop_compute_function_returns_reportable_payload(self):
        result = compute_desktop_calculation(_manual_snapshot())

        self.assertGreater(result["res_main"]["Q [W]"], 0.0)
        self.assertGreaterEqual(len(result["crosscheck_results"]), 4)
        self.assertIn("report_context", result)
        self.assertIn("main", result["report_context"]["results"])

    def test_desktop_compute_function_rejects_invalid_temperature_order(self):
        with self.assertRaises(ValueError):
            compute_desktop_calculation(_manual_snapshot(T_hot_raw=30.0, T_cold_raw=40.0))

    def test_updater_selects_matching_asset_and_verifies_sha256(self):
        payload = b"release-bytes"
        digest = hashlib.sha256(payload).hexdigest()
        update_info = {
            "assets": [
                {"name": "HeatExchangerCalcWeb-v1.zip", "download_url": "https://example.test/web.zip", "digest": ""},
                {
                    "name": "HeatExchangerCalcDesktop-v1.zip",
                    "download_url": "https://example.test/desktop.zip",
                    "digest": f"sha256:{digest}",
                },
            ]
        }

        self.assertEqual(select_release_asset(update_info, "desktop")["name"], "HeatExchangerCalcDesktop-v1.zip")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("urllib.request.urlopen", return_value=_FakeUrlOpen(payload)):
                result = download_release_asset(update_info, tmpdir, app_kind="desktop")
            self.assertTrue(os.path.exists(result["path"]))
            self.assertEqual(Path(result["path"]).read_bytes(), payload)

    def test_updater_removes_download_when_sha256_fails(self):
        update_info = {
            "assets": [
                {
                    "name": "HeatExchangerCalcDesktop-v1.zip",
                    "download_url": "https://example.test/desktop.zip",
                    "digest": "sha256:" + "0" * 64,
                }
            ]
        }

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("urllib.request.urlopen", return_value=_FakeUrlOpen(b"bad-bytes")),
        ):
            with self.assertRaises((ValueError, UpdaterError)):
                download_release_asset(update_info, tmpdir, app_kind="desktop")
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "HeatExchangerCalcDesktop-v1.zip")))

    def test_pyinstaller_specs_include_release_dependencies(self):
        for spec_name in ("HeatExchangerCalcDesktop.spec", "HeatExchangerCalcWeb.spec"):
            spec_text = Path(spec_name).read_text(encoding="utf-8")
            self.assertIn("engineering_utils", spec_text)
            self.assertIn("reportlab", spec_text)
            self.assertIn("collect_data_files('ht')", spec_text)
            self.assertTrue(
                "icon='app_icon.ico'" in spec_text
                or "icon=['app_icon.ico']" in spec_text
                or "icon=[icon_path]" in spec_text
            )
            self.assertIn("version='version_info.txt'", spec_text)

    def test_bowman_f_edge_cases_do_not_produce_nan(self):
        from heat_exchanger import _bowman_lmtd_factor

        # Edge case: P ≈ 1 (temperature cross)
        f1 = _bowman_lmtd_factor(100.0, 20.0, 99.999, 99.998, C_h=100.0, C_c=100.0)
        self.assertFalse(np.isnan(f1))
        self.assertGreaterEqual(f1, 0.01)
        # Edge case: R = 0 (phase change — C_h >> C_c)
        f2 = _bowman_lmtd_factor(200.0, 50.0, 100.0, 60.0, C_h=1e6, C_c=100.0)
        self.assertFalse(np.isnan(f2))
        # Edge case: P = 0 (no heat transfer)
        f3 = _bowman_lmtd_factor(100.0, 20.0, 100.0, 20.0, C_h=100.0, C_c=100.0)
        self.assertEqual(f3, 1.0)
        # Edge case: R = 1 (balanced flow)
        f4 = _bowman_lmtd_factor(100.0, 20.0, 60.0, 60.0, C_h=100.0, C_c=100.0)
        self.assertFalse(np.isnan(f4))
        self.assertGreaterEqual(f4, 0.01)


if __name__ == "__main__":
    unittest.main()
