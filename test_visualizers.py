"""Unit tests for visualizer components, Excel export, TEMA FIV and API 661 extensions."""

import io
import unittest

import openpyxl

from exchanger_3d_component import get_exchanger_3d_html
from heat_exchanger import FinTubeHeatExchanger, Fluid
from mechanical import (
    api661_fan_coverage_check,
    api661_noise_level,
    mechanical_design_report,
    tema_fiv_analysis,
)
from orc_schematic_component import get_orc_schematic_html
from reporting import export_calculation_excel
from tubesheet_component import generate_tubesheet_svg


class TestVisualizersAndDeliverables(unittest.TestCase):
    def test_3d_component_html_generation(self):
        html_default = get_exchanger_3d_html()
        self.assertIn("<!DOCTYPE html>", html_default)
        self.assertIn("three.js", html_default.lower())
        self.assertIn("<canvas", html_default.lower())

        custom_geom = {
            "D_o_mm": 25.4,
            "D_i_mm": 21.1,
            "L_m": 3.0,
            "N_tubes": 48,
            "D_shell_mm": 400.0,
            "baffle_spacing_mm": 150.0,
        }
        html_custom = get_exchanger_3d_html(custom_geom)
        self.assertIn("25.4", html_custom)
        self.assertIn("400", html_custom)

    def test_orc_schematic_html_generation(self):
        html = get_orc_schematic_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<svg", html.lower())
        self.assertIn("cyclopenta", html.lower())
        self.assertIn("therminol", html.lower())
        self.assertIn("recalculate()", html)
        self.assertIn("selectEquipment(state.selected_eq)", html)

    def test_orc_schematic_live_initial_data(self):
        live_data = {
            "m_hot": 28.5,
            "m_cold": 14.2,
            "T_cold_in": 48.0,
            "st_shell_p_des_bar": 16.5,
            "n_boilers": 3,
            "condenser_type": "air",
            "T_air_in": 35.0,
            "bypass_ratio": 0.15,
            "U_value": 600.0,
            "Area": 40.0,
        }
        html = get_orc_schematic_html(live_data)
        self.assertIn("28.5", html)
        self.assertIn("14.2", html)
        self.assertIn("48.0", html)
        self.assertIn("16.5", html)
        self.assertIn('"condenser_type": "air"', html)
        self.assertIn("recalculate()", html)

    def test_orc_schematic_safe_script_escaping(self):
        malicious_data = {
            "comment": "</script><script>alert('xss')</script>",
            "m_oil": 30.0,
        }
        html = get_orc_schematic_html(malicious_data)
        self.assertNotIn("</script><script>", html)
        self.assertIn("<\\/script>", html)

    def test_orc_schematic_recalculate_scoping(self):
        html = get_orc_schematic_html()
        self.assertIn("let new_t_oil_sup = 295.0;", html)
        self.assertIn("setTxt('kpi_q_boiler'", html)
        self.assertIn("setTxt('kpi_w_net'", html)
        self.assertIn("setTxt('kpi_q_orc'", html)
        self.assertIn("setTxt('kpi_plant_eff'", html)

    def test_orc_schematic_thermodynamic_bounds(self):
        html = get_orc_schematic_html()
        self.assertIn("m_cp_actual", html)
        self.assertIn("eta_carnot", html)
        self.assertIn("w_turb_carnot_max", html)
        self.assertIn("(q_boiler / 1000.0) * eta_carnot", html)

    def test_orc_schematic_kpi_info_modal(self):
        html = get_orc_schematic_html()
        self.assertIn('id="kpi_modal"', html)
        self.assertIn("showKpiInfo", html)
        self.assertIn("closeKpiModal", html)
        self.assertIn("kpi-info-btn", html)
        for key in ["q_boiler", "w_net", "q_orc", "plant_eff", "bypass", "pinch"]:
            self.assertIn(f"'{key}'", html)

    def test_excel_export_validity(self):
        context = {
            "inputs": {
                "m_hot_kg_s": 2.5,
                "m_cold_kg_s": 4.0,
                "T_hot_in_C": 95.0,
                "T_cold_in_C": 25.0,
            },
            "fluids": {
                "hot": {"label": "Su (Water)"},
                "cold": {"label": "Su (Water)"},
            },
            "results": {
                "main": {
                    "Q [W]": 250000.0,
                    "epsilon": 0.72,
                    "LMTD": 38.5,
                    "F": 0.95,
                    "T_hot_out [C]": 71.0,
                    "T_cold_out [C]": 40.0,
                }
            },
            "geometry": {
                "D_o": 0.0254,
                "D_i": 0.0211,
                "L": 4.0,
                "N_tubes": 64,
            },
            "actual_result": {
                "U": 850.0,
                "A_total": 20.4,
                "delta_p_tube_kPa": 14.2,
                "delta_p_shell_kPa": 22.8,
            },
        }
        xlsx_bytes = export_calculation_excel(context)
        self.assertTrue(xlsx_bytes.startswith(b"PK\x03\x04"))
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        self.assertIn("TEMA Hesap Föyü", wb.sheetnames)
        ws = wb["TEMA Hesap Föyü"]
        self.assertIn("HEAT EXCHANGER CALCULATION", str(ws["A1"].value))

    def test_tema_fiv_analysis(self):
        res = tema_fiv_analysis(
            D_o=0.01905,
            t_wall=0.0021,
            L_b=0.35,
            pitch=0.0238,
            v_cross=0.8,
            rho_shell=850.0,
            rho_tube=1000.0,
        )
        self.assertIn("f_n", res)
        self.assertIn("f_v", res)
        self.assertIn("v_crit", res)
        self.assertGreater(res["f_n"], 10.0)
        self.assertGreater(res["v_crit"], 0.1)

    def test_api661_fan_coverage_and_noise(self):
        ok, cov, lim = api661_fan_coverage_check(
            fan_diameter=2.4,
            num_fans=2,
            bundle_width=3.0,
            bundle_length=6.0,
        )
        self.assertGreaterEqual(cov, lim)
        self.assertTrue(ok)

        pwl, spl = api661_noise_level(tip_speed=45.0, fan_power_kw=15.0, distance_m=1.0)
        self.assertGreater(pwl, 70.0)
        self.assertGreater(spl, 50.0)

    def test_multizone_condenser_solve(self):
        hot = Fluid(name="HotVapor", cp=2000.0, density=800.0, mu=0.001, k_cond=0.15, h_fg=300000.0)
        cold = Fluid(name="CoolingWater", cp=4180.0, density=1000.0, mu=0.0008, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=1200.0, A=15.0)
        res = hx.solve_multizone_condenser(
            m_hot=0.5,
            m_cold=5.0,
            T_hot_in=120.0,
            T_sat=90.0,
            T_cold_in=25.0,
            T_subcool=75.0,
        )
        self.assertEqual(res["Method"], "Çok Bölgeli Kondenser (3-Zone)")
        self.assertGreater(res["Q_desuperheat [W]"], 0.0)
        self.assertGreater(res["Q_condensing [W]"], 0.0)
        self.assertGreater(res["Q_subcooling [W]"], 0.0)
        self.assertGreater(res["Q [W]"], 100000.0)

    def test_tubesheet_svg_generation(self):
        for angle in ("30", "45", "60", "90"):
            for passes in (1, 2, 4):
                svg = generate_tubesheet_svg(
                    D_shell_mm=400.0,
                    D_o_mm=19.05,
                    D_i_mm=16.55,
                    pitch_mm=25.0,
                    layout_angle=angle,
                    N_tubes=80,
                    tube_passes=passes,
                )
                self.assertIn("<svg", svg)
                self.assertIn("</svg>", svg)
                self.assertIn("<circle", svg)
                self.assertIn(f"{angle}°", svg)

        # Invalid geometry returns fallback SVG
        svg_err = generate_tubesheet_svg(D_shell_mm=100.0, D_o_mm=25.0, D_i_mm=20.0, pitch_mm=20.0)
        self.assertIn("geçersiz", svg_err)

    def test_evaporator_glide_solve(self):
        hot = Fluid(name="HotWater", cp=4180.0, density=1000.0, mu=0.0005, k_cond=0.6)
        cold = Fluid(name="Refrigerant", cp=1500.0, density=1100.0, mu=0.0003, k_cond=0.1, h_fg=200000.0)
        hx = FinTubeHeatExchanger(hot, cold, U=1000.0, A=10.0)
        res_noglide = hx.solve_evaporator(m_hot=2.0, m_cold=0.5, T_hot_in=80.0, T_sat=20.0, h_fg=200000.0)
        res_glide = hx.solve_evaporator(m_hot=2.0, m_cold=0.5, T_hot_in=80.0, T_sat=20.0, h_fg=200000.0, glide=6.0)
        self.assertEqual(res_noglide["Method"], "Evaporatör (Cr=0)")
        self.assertEqual(res_glide["Method"], "Evaporatör (Zeotropik Glide)")
        self.assertIn("glide=6.0", str(res_glide.get("warnings", [])))
        self.assertGreater(res_glide["Q [W]"], 0.0)

    def test_mechanical_design_report_integration(self):
        geom = {
            "design_pressure": 1.6e6,
            "design_stress": 118e6,
            "corrosion_allowance": 0.003,
            "joint_efficiency": 0.85,
            "tema_class": "R",
            "D_shell": 0.40,
            "D_o": 0.01905,
            "D_i": 0.01655,
            "pitch": 0.025,
            "baffle_spacing": 0.15,
            "v_cross": 0.75,
            "rho_shell": 850.0,
            "rho_tube": 1000.0,
        }
        rows = mechanical_design_report(geom)
        self.assertGreaterEqual(len(rows), 6)
        labels = [r["label"] for r in rows]
        self.assertTrue(any("ASME UG-27" in lbl for lbl in labels))
        self.assertTrue(any("TEMA RCB-7" in lbl for lbl in labels))
        self.assertTrue(any("ASME UG-34" in lbl for lbl in labels))
        self.assertTrue(any("TEMA Doğal Frekans" in lbl for lbl in labels))
        self.assertTrue(any("Akışkan-Elastik" in lbl for lbl in labels))

    def test_get_val_with_default_arg(self):
        from app_web import get_val
        # Test 1 arg
        val1 = get_val("exch_type")
        self.assertIsNotNone(val1)
        # Test 2 args with known key
        val2 = get_val("condenser_type", "water")
        self.assertIn(val2, ("water", "air"))
        # Test 2 args with missing key
        val3 = get_val("non_existent_key_xyz", "my_fallback")
        self.assertEqual(val3, "my_fallback")

    def test_orc_schematic_live_hud_and_split_balancing(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({"n_boilers": 3, "m_oil": 35.0, "m_cp": 12.0})
        self.assertIn("insp_live_hud", html)
        self.assertIn("function updateInspectorLiveHUD(data)", html)
        self.assertIn("state.boilers[bIdx].split = newSplit", html)
        self.assertIn("txt_oil_sup_fluid", html)
        self.assertIn("txt_sh_in_fluid", html)
        self.assertIn("power-balance-bar", html)
        self.assertIn("pwr_w_turb", html)
        self.assertIn("pwr_w_oil_pump", html)
        self.assertIn("pwr_w_cp_pump", html)
        self.assertIn("pwr_w_cond", html)
        self.assertIn("pwr_w_net", html)
        self.assertIn("pump_oil_power", html)
        self.assertIn("w_turb", html)

    def test_orc_3d_plant_robustness(self):
        from orc_3d_plant_component import get_orc_3d_plant_js
        js = get_orc_3d_plant_js()
        self.assertIn("const stainlessMat = new THREE.MeshStandardMaterial", js)
        self.assertIn("WebGLRenderer", js)
        self.assertIn("Tarayıcınızda WebGL donanım hızlandırması başlatılamadı", js)

    def test_orc_schematic_darcy_weisbach_and_bridge(self):
        from app_web import DEFAULT_STATE
        from orc_schematic_component import get_orc_schematic_html

        # 1. DEFAULT_STATE hydraulic verification
        self.assertIn("pipe_di_mm", DEFAULT_STATE)
        self.assertIn("pipe_length_m", DEFAULT_STATE)
        self.assertEqual(DEFAULT_STATE["pipe_di_mm"], 154.0)
        self.assertEqual(DEFAULT_STATE["pipe_length_m"], 80.0)

        # 2. Darcy-Weisbach formulation in HTML/JS
        html = get_orc_schematic_html({
            "pipe_di_mm": 102.3,
            "pipe_length_m": 120.0,
            "UA_ph": 140.0,
            "UA_sh": 40.0
        })
        self.assertIn("pipe_di_mm", html)
        self.assertIn("pipe_length_m", html)
        self.assertIn("f_darcy", html)
        self.assertIn("rough_m", html)
        self.assertIn("dp_pipe_bar", html)
        self.assertIn("v_oil", html)
        self.assertIn("re_oil", html)

    def test_orc_schematic_solver_and_fluid_selection(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({
            "solver_method": "LMTD",
            "cold_fluid_sel": "Dowtherm A",
            "cp_hot": 1150.0,
            "density_hot": 0.52,
            "mu_hot": 2.6e-5,
            "cp_cold": 2150.0,
            "density_cold": 980.0,
            "mu_cold": 0.0008
        })
        self.assertIn("ORC_FLUIDS", html)
        self.assertIn("Cyclopentane", html)
        self.assertIn("n-Pentane", html)
        self.assertIn("Isopentane", html)
        self.assertIn("R245fa", html)
        self.assertIn("R1233zd(E)", html)
        self.assertIn("Toluene", html)
        self.assertIn("THERMAL_OILS", html)
        self.assertIn("Therminol 66", html)
        self.assertIn("Dowtherm A", html)
        self.assertIn("whru_solver_method", html)
        self.assertIn("Kendi Algoritmamız (Epsilon-NTU)", html)
        self.assertIn("Kendi Algoritmamız (LMTD)", html)
        self.assertIn("HT Kütüphanesi (Epsilon-NTU)", html)
        self.assertIn("HT Kütüphanesi (LMTD)", html)
        self.assertIn("setWhruSolverMethod", html)
        self.assertIn("setWhruFlowType", html)
        self.assertIn("setWhruCalcPurpose", html)
        self.assertIn("setWhruUMode", html)
        self.assertIn("calcHxLMTD", html)
        self.assertIn("setOrcFluid", html)
        self.assertIn("setThermalOil", html)

    def test_orc_schematic_segmented_darcy_and_static_head(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({
            "pipe_di_mm": 154.0,
            "pipe_length_m": 80.0
        })
        self.assertIn("static_elevation_m", html)
        self.assertIn("hx_dp_bar", html)
        self.assertIn("dp_static_bar", html)
        self.assertIn("dp_pipes_sum_bar", html)
        self.assertIn("calcPipeDarcy", html)
        self.assertIn("pipe_supply", html)
        self.assertIn("pipe_boiler_inlet", html)
        self.assertIn("pipe_bypass", html)
        self.assertIn("pipe_return", html)

    def test_orc_schematic_turbine_enthalpy_and_power(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({})
        self.assertIn("dh_is", html)
        self.assertIn("w_turb_mech_kw", html)
        self.assertIn("w_turb_kw", html)
        self.assertIn("turb_eta_is", html)
        self.assertIn("turb_eta_gen", html)
        self.assertIn("t_cp_exh", html)
        self.assertIn("pwr_w_turb", html)

    def test_orc_schematic_boiler_flow_balance_and_dual_input(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({})
        self.assertIn("num_b${bNum}_m_oil", html)
        self.assertIn("autoBalanceBoilerFlows", html)
        self.assertIn("balance-warning-box", html)

    def test_orc_schematic_flue_gas_composition_and_manual_props(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({
            "hot_mix_data": {"Nitrogen": 72.0, "Oxygen": 6.0, "CarbonDioxide": 15.0, "Water": 6.0, "SulfurDioxide": 1.0},
            "hot_mix_basis": "mole",
            "cp_hot": 1144.0,
            "density_hot": 0.492,
            "mu_hot": 3.55e-5
        })
        self.assertIn("flue_gas_mix", html)
        self.assertIn("calcFlueGasMixtureProperties", html)
        self.assertIn("applyFlueGasPreset", html)
        self.assertIn("setFlueGasBasis", html)
        self.assertIn("onFlueGasCompChange", html)
        self.assertIn("resetFlueGasToAuto", html)
        self.assertIn("flue_gas_is_manual", html)
        self.assertIn("Doğal Gaz", html)
        self.assertIn("Kömür", html)
        self.assertIn("Biyogaz", html)
        self.assertIn("Nitrogen", html)
        self.assertIn("CarbonDioxide", html)

    def test_orc_schematic_kettle_snt_and_multizone_config(self):
        from orc_schematic_component import get_orc_schematic_html
        html = get_orc_schematic_html({
            "exch_type": "Kanatçıklı Borulu (Finned Tube - WHRU Baca Kazanı)",
            "st_tema_type": "K (Kettle Reboiler Evaporatör - Genişletilmiş Kubbeli)",
            "st_shell_fluid": "Therminol 66 (Kızgın Yağ)",
            "st_tube_fluid": "Siklopentan (ORC Çevrim Akışkanı)",
            "st_kettle_dome_ratio": 1.95,
            "st_demister_type": "SS316 Tel Örgü Ped (Wire Mesh Pad - 100 mm)",
            "st_baffle_cut_pct": 30.0,
            "st_baffle_spacing_mm": 250.0,
            "st_pinch_min_target_c": 12.0,
            "st_shell_fouling": 0.00025,
            "st_tube_fouling": 0.00012,
            "glide_c": 2.5,
            "enable_multizone": True,
            "t_subcool": 92.0
        })
        self.assertIn("whru_exch_type", html)
        self.assertIn("setWhruExchType", html)
        self.assertIn("whru_T_hot_out_opt", html)
        self.assertIn("whru_T_cold_out_opt", html)
        self.assertIn("st_tema_type", html)
        self.assertIn("setStTemaType", html)
        self.assertIn("st_kettle_dome_ratio", html)
        self.assertIn("st_demister_type", html)
        self.assertIn("setStDemisterType", html)
        self.assertIn("st_baffle_cut", html)
        self.assertIn("st_baffle_pitch", html)
        self.assertIn("st_pinch_min_target", html)
        self.assertIn("ph_shell_fouling", html)
        self.assertIn("ph_tube_fouling", html)
        self.assertIn("glide_c", html)
        self.assertIn("enable_multizone", html)
        self.assertIn("setMultizoneToggle", html)
        self.assertIn("t_subcool", html)
        self.assertIn("q_desup_kw", html)
        self.assertIn("q_sub_kw", html)
        self.assertIn("3-Bölge Isı Dağılımı", html)

    def test_orc_schematic_numerical_boundary_guards_and_render_loop(self):
        from orc_3d_plant_component import get_orc_3d_plant_js
        from orc_schematic_component import get_orc_schematic_html

        html = get_orc_schematic_html({
            "P_evap_bar": 1.5,
            "P_cond_bar": 2.0,  # Inverted pressure condition P_evap <= P_cond
            "m_oil": 0.0,
            "orc_fluid_sel": "Toluene"
        })

        # 1. Kays & London Cr < 1e-4 guard exists to prevent NaN
        self.assertIn("if (cr < 1e-4)", html)
        self.assertIn("eps = 1.0 - Math.exp(-ntu);", html)

        # 2. Inverted pressure head guard
        self.assertIn("has_head = state.P_evap_bar > p_cond_actual", html)

        # 3. Manifold energy conservation on partial boiler splits
        self.assertIn("unheated_oil = Math.max(0.0, state.m_oil - sum_m_oil_active)", html)

        # 4. Fluid-specific Antoine parameters for NPSH
        self.assertIn("activeOrcFluid.antoine", html)

        # 5. Controlled WebGL render loop (pause/resume without memory leak)
        plant_js = get_orc_3d_plant_js()
        self.assertIn("start3DAnimation", plant_js)
        self.assertIn("stop3DAnimation", plant_js)
        self.assertIn("cancelAnimationFrame(animFrameId)", plant_js)
        self.assertIn("ResizeObserver", plant_js)

    def test_orc_schematic_export_and_hydraulic_smoothing(self):
        from orc_3d_plant_component import get_orc_3d_plant_js
        from orc_schematic_component import get_orc_schematic_html

        html = get_orc_schematic_html({
            "cold_fluid_sel": "Mobiltherm 605",
            "orc_fluid_sel": "R245fa",
            "m_flue": 22.0,
            "T_flue_in": 460.0,
            "flue_gas_cp": 1120.0
        })

        # 1. JSON Export function and action button in mode-bar
        self.assertIn("exportSimulationJSON", html)
        self.assertIn("btn_export_json", html)
        self.assertIn("📥 JSON İndir", html)

        # 2. Hydraulic Darcy-Weisbach transition smoothing (2300 <= Re < 4000)
        self.assertIn("f_lam_trans", html)
        self.assertIn("f_turb_trans", html)

        # 3. Comprehensive telemetry payload to 3D Plant
        self.assertIn("boilerTelemetry", html)
        self.assertIn("pump_oil: {", html)
        self.assertIn("pump_cp: {", html)

        # 4. 3D Digital Twin HUD Dynamic Telemetry Rendering
        plant_js = get_orc_3d_plant_js()
        self.assertIn("res.superheater", plant_js)
        self.assertIn("res.boiler", plant_js)
        self.assertIn("res.turbine", plant_js)
        self.assertIn("res.condenser", plant_js)
        self.assertIn("res.pump_oil", plant_js)

    def test_orc_3d_plant_script_escaping(self):
        """Standalone 3D plant HTML must escape closing script tags to prevent XSS."""
        from orc_3d_plant_component import get_standalone_3d_plant_html

        payload = {"title": "Test</script><script>alert(1)</script>"}
        html = get_standalone_3d_plant_html(payload)
        self.assertNotIn("</script><script>", html)
        self.assertIn("<\\/script>", html)

    def test_tubesheet_svg_layout_angle_coercion(self):
        """generate_tubesheet_svg must coerce angles and safely handle non-numeric or malicious strings."""
        from tubesheet_component import generate_tubesheet_svg

        # Malicious angle string
        svg_bad = generate_tubesheet_svg(400.0, 19.05, 16.55, 25.0, layout_angle="30<script>")
        self.assertNotIn("<script>", svg_bad)
        self.assertIn("TEMA 30° Açılı Ayna", svg_bad)

        # String with degree symbol
        svg_deg = generate_tubesheet_svg(400.0, 19.05, 16.55, 25.0, layout_angle="45°")
        self.assertIn("TEMA 45° Açılı Ayna", svg_deg)

    def test_orc_pressure_inversion_guard_and_preheater_duty(self):
        """solve_orc_system must clamp inverted condenser pressures and not double-count preheater duty."""
        from orc_system_model import solve_orc_system

        # Inverted pressure: P_cond (20.0) >= P_evap (16.0)
        res = solve_orc_system({"P_evap_bar": 16.0, "P_cond_bar": 20.0})
        self.assertLess(res["condenser"]["P_cond_bar"], 16.0)
        self.assertIsNotNone(res["condenser"].get("warning"))
        self.assertIn("sınırlandırıldı", res["condenser"]["warning"])

        # Preheater sensible duty check
        sh = res["superheater"]
        evap = res["evaporator"]
        ph = res["preheater"]
        orc = res["orc"]
        self.assertAlmostEqual(orc["Q_total_kW"], round(sh["Q_kW"] + evap["Q_kW"] + ph["Q_kW"], 1), delta=0.5)

    def test_multizone_condenser_superheat_driving_force_limit(self):
        """Multizone condenser must clamp condensation driving head to prevent pinch violation with superheated vapor."""
        from heat_exchanger import FinTubeHeatExchanger, Fluid

        hot = Fluid("Vapor", cp=2500.0, density=500.0, mu=0.001, k_cond=0.2, h_fg=250000.0)
        cold = Fluid("CoolingWater", cp=4180.0, density=1000.0, mu=0.001, k_cond=0.6)
        hx = FinTubeHeatExchanger(hot, cold, U=1500.0, A=30.0)

        # High superheat: T_hot_in=250 C, T_sat=50 C, T_cold_in=20 C
        res = hx.solve_multizone_condenser(
            m_hot=1.0,
            m_cold=20.0,
            T_hot_in=250.0,
            T_sat=50.0,
            T_cold_in=20.0,
        )
        C_c = 20.0 * 4180.0
        # Cold temperature entering desuperheating zone cannot exceed T_sat
        T_cold_entering_desup = res["T_cold_out [C]"] - (res["Q_desuperheat [W]"] / C_c)
        self.assertLessEqual(T_cold_entering_desup, 50.01)

    def test_asme_formed_heads_and_hydro_stress_ratio(self):
        """Verify ASME UG-32 formed heads and UG-99 hydro test temperature correction."""
        from mechanical import asme_formed_head_thickness, hydrostatic_test_pressure

        # 2:1 Ellipsoidal Head
        t_ellip = asme_formed_head_thickness(P=1.0e6, D=1.0, S=118.0e6, CA=0.003, head_type="2:1_ellipsoidal")
        self.assertGreater(t_ellip, 0.003)
        self.assertLess(t_ellip, 0.020)

        # Torispherical Head
        t_tori = asme_formed_head_thickness(P=1.0e6, D=1.0, S=118.0e6, CA=0.003, head_type="torispherical")
        self.assertGreater(t_tori, t_ellip)  # Torispherical is thicker than 2:1 ellipsoidal

        # Hydrostatic test pressure with temperature derating S_test / S_design
        p_base = hydrostatic_test_pressure(MAWP=1.0e6)
        self.assertAlmostEqual(p_base, 1.3e6)
        p_hot = hydrostatic_test_pressure(MAWP=1.0e6, S_test=138.0e6, S_design=115.0e6)
        self.assertAlmostEqual(p_hot, 1.3e6 * (138.0 / 115.0))

    def test_exchanger_3d_component_escaping(self):
        """Standalone exchanger 3D component must escape script tags to prevent XSS."""
        from exchanger_3d_component import get_exchanger_3d_html

        data = {"tube_material": "Steel</script><script>alert(1)</script>"}
        html = get_exchanger_3d_html(data)
        self.assertNotIn("</script><script>", html)
        self.assertIn("<\\/script>", html)

    def test_orc_acid_dew_point_and_balanced_cr(self):
        """Verify acid dew point warning and smooth balanced Cr in ORC model."""
        from orc_system_model import solve_orc_system

        # Low flue temperature triggers acid dew point warning
        res = solve_orc_system({"T_flue_in": 140.0, "m_flue": 10.0})
        self.assertTrue(res["boiler"]["acid_dew_point_warning"])


if __name__ == "__main__":
    unittest.main()
