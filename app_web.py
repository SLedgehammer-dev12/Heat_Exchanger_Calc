import io
import json
import logging
import os
import sys
from typing import Any

# Ensure application base directory and PyInstaller bundle directory are in sys.path
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import streamlit as st
import streamlit.components.v1 as _st_components

from engineering_utils import (
    fluid_report_data,
    from_celsius,
    to_celsius,
    to_kg_s,
)
from i18n import set_language
from logging_config import setup_logging
from orc_schematic_component import get_orc_schematic_html

LOG_FILE = setup_logging("web")
logger = logging.getLogger(__name__)


from app_shared import MIXTURE_PRESETS, safe_index
from config import EXCHANGER_ALLOWED_FLOWS, EXCHANGER_TYPES, TEMA_DESIGNATIONS, TUBE_MATERIALS
from fluids_db import get_fluid_data, get_fluid_list_flat, get_mixture_fluid_data, materialize_fluid_data
from heat_exchanger import FinTubeHeatExchanger, Fluid
from reporting import (
    build_calculation_report,
    build_calculation_report_pdf,
    export_calculation_csv,
    export_calculation_excel,
    export_profile_csv,
    generate_tema_datasheet_pdf,
)
from standards import ache_fin_names, fouling_preset_options, tube_preset_options
from updater import check_for_update, default_download_dir, download_release_asset
from version import APP_NAME, VERSION

_bwg_presets = tube_preset_options()
_fouling_presets = fouling_preset_options()

# Eşanjör tipi seçenekleri (görünen isim -> internal key)
EXCH_TYPE_OPTIONS = list(EXCHANGER_TYPES.values())
EXCH_TYPE_INTERNAL = {v: k for k, v in EXCHANGER_TYPES.items()}

FLOW_OPTIONS = [
    "Çapraz Akış (Cross Flow Unmixed)",
    "Çapraz Akış (Mixed/Unmixed)",
    "Ters Akış (Counter Flow)",
    "Paralel Akış (Parallel Flow)",
]
FLOW_MAP = {
    "Çapraz Akış (Cross Flow Unmixed)": "cross_unmixed",
    "Çapraz Akış (Mixed/Unmixed)": "cross_mixed_unmixed",
    "Ters Akış (Counter Flow)": "counter",
    "Paralel Akış (Parallel Flow)": "parallel",
}
FLOW_MAP_REVERSE = {value: key for key, value in FLOW_MAP.items()}

EXCH_FLOW_OPTIONS_CACHE: dict[str, list[str]] = {}


def _get_allowed_flow_labels(exch_type_internal: str) -> list[str]:
    """Return display labels for flow types allowed by this exchanger type."""
    allowed = EXCHANGER_ALLOWED_FLOWS.get(exch_type_internal, set())
    return [label for label, internal in FLOW_MAP.items() if internal in allowed]


CALC_PURPOSE_OPTIONS = [
    "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)",
    "Performans Değerlendirmesi (Verim Bul)",
    "Yoğuşturucu (Kondenser)",
    "Buharlaştırıcı (Evaporatör)",
]
SOLVER_OPTIONS = [
    "Kendi Algoritmamız (Epsilon-NTU)",
    "Kendi Algoritmamız (LMTD)",
    "HT Kütüphanesi (Epsilon-NTU)",
    "HT Kütüphanesi (LMTD)",
]
U_MODE_OPTIONS = [
    "Basit Mod (Manuel U Değeri)",
    "Geometrik Mod (Malzeme ve Çap ile Hesapla)",
]

STATE_KEY_ALIASES = {
    "purpose": "calc_purpose",
    "u_mode": "u_calc_mode",
    "hot_fluid": "hot_fluid_sel",
    "cold_fluid": "cold_fluid_sel",
    "t_hot_in": "T_hot_in",
    "t_cold_in": "T_cold_in",
    "t_hot_out_opt": "T_hot_out_opt",
    "t_cold_out_opt": "T_cold_out_opt",
    "U": "U_value",
    "A": "Area",
    "Do": "D_o_mm",
    "Di": "D_i_mm",
    "L": "L_m",
    "Nt": "N_tubes",
    "mu_hot": "mu_hot",
    "k_hot": "k_hot",
    "mu_cold": "mu_cold",
    "k_cold": "k_cold",
}

DEFAULT_STATE = {
    "exch_type": "Kanatçıklı Borulu",
    "flow_type": FLOW_OPTIONS[0],
    "calc_purpose": CALC_PURPOSE_OPTIONS[0],
    "h_fg": 2_200_000,
    "pump_efficiency": 0.70,
    "fan_efficiency": 0.60,
    "solver_method": SOLVER_OPTIONS[0],
    "u_calc_mode": U_MODE_OPTIONS[0],
    "hot_fluid_sel": "Doğal Gaz Türbin Egzoz Gazı (Manuel)",
    "m_hot": 15.0,
    "T_hot_in": 450.0,
    "T_hot_out_opt": -999.0,
    "cp_hot": 1100.0,
    "density_hot": 0.5,
    "mu_hot": 2e-5,
    "k_hot": 0.03,
    "hot_mix_data": {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0},
    "hot_mix_basis": "mole",
    "cold_fluid_sel": "Therminol 66",
    "m_cold": 5.0,
    "T_cold_in": 120.0,
    "T_cold_out_opt": -999.0,
    "cp_cold": 2000.0,
    "density_cold": 850.0,
    "mu_cold": 0.001,
    "k_cold": 0.15,
    "cold_mix_data": {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0},
    "cold_mix_basis": "mole",
    "U_value": 50.0,
    "Area": 200.0,
    "D_o_mm": 25.4,
    "D_i_mm": 21.1,
    "L_m": 3.0,
    "N_tubes": 100,
    "pitch_mm": 60.0,
    "D_shell_mm": 50.0,
    "tube_material": "Karbon Çelik (k=45)",
    "hot_is_tube": "Soğuk Akışkan",
    "is_finned": True,
    "fin_h_mm": 15.9,
    "fin_t_mm": 0.4,
    "fin_density": 400,
    "fin_material": "Alüminyum (k=237)",
    "fin_type": "Dairesel (Annular)",
    "fin_attachment": "L-Fin (Wrap-on)",
    "P_design_bar": 10.0,
    "S_stress_mpa": 118.0,
    "CA_mm": 3.0,
    "joint_eff_str": "0.85 (Noktasal RT / Spot)",
    "tema_class_str": "R (Petrol & Ağır Sanayi)",
    "glide_c": 0.0,
    "enable_multizone": False,
    "t_subcool": 95.0,
    "st_tema_type": "K (Kettle Reboiler Evaporatör - Genişletilmiş Kubbeli)",
    "st_shell_fluid": "Therminol 66 (Kızgın Yağ)",
    "st_tube_fluid": "Siklopentan (ORC Çevrim Akışkanı)",
    "st_shell_p_des_bar": 16.0,
    "st_tube_p_des_bar": 25.0,
    "st_shell_fouling": 0.0002,
    "st_tube_fouling": 0.0001,
    "st_baffle_cut_pct": 25.0,
    "st_baffle_spacing_mm": 150.0,
    "st_kettle_dome_ratio": 1.80,
    "st_pinch_min_target_c": 8.0,
    "st_demister_type": "SS316 Tel Örgü Ped (Wire Mesh Pad - 100 mm)",
    "condenser_type": "air",
    "t_air_in": 30.0,
    "t_cw_in": 25.0,
    "acc_fan_eff": 65.0,
    "cw_pump_eff": 75.0,
    "sh_t_oil_in_mode": "Otomatik (Kazan Çıkışıyla Aynı)",
    "sh_t_oil_in_manual": 290.0,
    "sh_pipe_loss_c": 0.0,
    "pipe_dn_sel": "DN150 (Di=154.0 mm)",
    "pipe_di_mm": 154.0,
    "pipe_length_m": 80.0,
}

ENGINEERING_PRESETS = {
    "tema_water_water": {
        "title": "🏢 Su - Su (TEMA Gövde-Boru)",
        "desc": "Endüstriyel proses soğutma: Ters akış, 2 geçişli boru demeti.",
        "state": {
            "exch_type": "Gövde-Boru TEMA",
            "flow_type": "Ters Akış (Counter Flow)",
            "calc_purpose": CALC_PURPOSE_OPTIONS[0],
            "u_calc_mode": U_MODE_OPTIONS[1],
            "hot_fluid_sel": "Water",
            "m_hot": 5.0,
            "T_hot_in": 85.0,
            "cold_fluid_sel": "Water",
            "m_cold": 8.0,
            "T_cold_in": 25.0,
            "D_o_mm": 19.05,
            "D_i_mm": 16.55,
            "L_m": 3.0,
            "N_tubes": 80,
            "D_shell_mm": 350.0,
            "pitch_mm": 25.0,
            "baffle_spacing_mm": 150.0,
            "baffle_cut": 0.25,
            "tube_material": "Karbon Çelik (k=45)",
            "tube_passes": 2,
            "shell_passes": 1,
            "tema_designation": "BEM",
            "is_finned": False,
            "hot_is_tube": "Sıcak Akışkan",
            "bwg_preset": "Manuel",
            "fouling_preset": "Temiz (yok)",
            "P_design_bar": 10.0,
            "S_stress_mpa": 118.0,
            "CA_mm": 3.0,
            "joint_eff_str": "0.85 (Noktasal RT / Spot)",
            "tema_class_str": "R (Petrol & Ağır Sanayi)",
        },
    },
    "finned_exhaust_oil": {
        "title": "💨 Egzoz Gazı - Yağ (Kanatçıklı Boru)",
        "desc": "Atık ısı geri kazanımı: Türbin egzozu ile termal yağ ısıtma.",
        "state": {
            "exch_type": "Kanatçıklı Borulu",
            "flow_type": "Çapraz Akış (Cross Flow Unmixed)",
            "calc_purpose": CALC_PURPOSE_OPTIONS[0],
            "u_calc_mode": U_MODE_OPTIONS[1],
            "hot_fluid_sel": "Doğal Gaz Türbin Egzoz Gazı (Manuel)",
            "m_hot": 15.0,
            "T_hot_in": 450.0,
            "cold_fluid_sel": "Therminol 66",
            "m_cold": 5.0,
            "T_cold_in": 120.0,
            "D_o_mm": 25.4,
            "D_i_mm": 21.1,
            "L_m": 3.0,
            "N_tubes": 100,
            "pitch_mm": 60.0,
            "is_finned": True,
            "fin_h_mm": 15.9,
            "fin_t_mm": 0.4,
            "fin_density": 400,
            "fin_material": "Alüminyum (k=237)",
            "fin_type": "Dairesel (Annular)",
            "fin_attachment": "L-Fin (Wrap-on)",
            "hot_is_tube": "Soğuk Akışkan",
            "bwg_preset": "Manuel",
            "fouling_preset": "Temiz (yok)",
        },
    },
    "condenser_steam": {
        "title": "⚡ Buhar Yoğuşturucu (Kondenser)",
        "desc": "Faz değişimi: Doymuş buhar yoğuşması ile sıcak su eldesi.",
        "state": {
            "exch_type": "Gövde-Boru TEMA",
            "flow_type": "Ters Akış (Counter Flow)",
            "calc_purpose": CALC_PURPOSE_OPTIONS[2],
            "h_fg": 2257000.0,
            "u_calc_mode": U_MODE_OPTIONS[0],
            "U_value": 2200.0,
            "Area": 120.0,
            "hot_fluid_sel": "Water",
            "m_hot": 2.0,
            "T_hot_in": 100.0,
            "cold_fluid_sel": "Water",
            "m_cold": 35.0,
            "T_cold_in": 25.0,
            "hot_is_tube": "Soğuk Akışkan",
            "enable_multizone": True,
            "glide_c": 0.0,
            "t_subcool": 90.0,
        },
    },
}


def normalize_loaded_state(data):
    normalized = {}
    for key, value in data.items():
        normalized[STATE_KEY_ALIASES.get(key, key)] = value

    flow_value = normalized.get("flow_type")
    if flow_value in FLOW_MAP_REVERSE:
        normalized["flow_type"] = FLOW_MAP_REVERSE[flow_value]

    if normalized.get("u_calc_mode") == "Basit Mod":
        normalized["u_calc_mode"] = U_MODE_OPTIONS[0]
    elif normalized.get("u_calc_mode") == "Geometrik Mod (Malzeme ile Hesapla)":
        normalized["u_calc_mode"] = U_MODE_OPTIONS[1]

    if normalized.get("calc_purpose") not in CALC_PURPOSE_OPTIONS:
        normalized["calc_purpose"] = DEFAULT_STATE["calc_purpose"]
    if normalized.get("solver_method") not in SOLVER_OPTIONS:
        normalized["solver_method"] = DEFAULT_STATE["solver_method"]
    if normalized.get("u_calc_mode") not in U_MODE_OPTIONS:
        normalized["u_calc_mode"] = DEFAULT_STATE["u_calc_mode"]
    if normalized.get("flow_type") not in FLOW_OPTIONS:
        normalized["flow_type"] = DEFAULT_STATE["flow_type"]
    # Akış tipini eşanjör tipine göre doğrula
    exch_label = normalized.get("exch_type", DEFAULT_STATE["exch_type"])
    exch_internal = EXCH_TYPE_INTERNAL.get(exch_label, "finned_tube")
    allowed_flow_labels = _get_allowed_flow_labels(exch_internal)
    if normalized.get("flow_type") not in allowed_flow_labels and allowed_flow_labels:
        normalized["flow_type"] = allowed_flow_labels[0]

    return normalized


def get_val(key, default=None):
    val = st.session_state.get(key)
    if val is not None:
        return val
    val_cfg = st.session_state.get(f"cfg_{key}")
    if val_cfg is not None:
        return val_cfg
    return DEFAULT_STATE.get(key, default)


def build_manual_fluid(fluid_data, cp, density, mu, k_cond):
    return Fluid(
        name=fluid_data["name"],
        cp=cp,
        density=density,
        mu=mu,
        k_cond=k_cond,
        is_coolprop=False,
    )


MIXTURE_GASES = [
    "Nitrogen",
    "Oxygen",
    "CarbonDioxide",
    "Water",
    "Argon",
    "CarbonMonoxide",
    "Methane",
    "Hydrogen",
    "SulfurDioxide",
]


def is_mixture_selection(label, fluid_data):
    return bool(fluid_data.get("is_mixture")) or "Egzoz" in label or "Kompozisyon" in label


def is_custom_manual_selection(label):
    return "Manuel Giriş" in label


def render_mixture_editor(side_label, state_prefix, T_c):
    mix_key = f"{state_prefix}_mix_data"
    basis_key = f"{state_prefix}_mix_basis"
    if mix_key not in st.session_state:
        st.session_state[mix_key] = dict(DEFAULT_STATE[mix_key])
    if basis_key not in st.session_state:
        st.session_state[basis_key] = DEFAULT_STATE[basis_key]

    with st.expander(f"🔧 {side_label} egzoz gazı kompozisyonu", expanded=True):
        c1, c2, c3 = st.columns(3)
        for col, preset_name in zip((c1, c2, c3), MIXTURE_PRESETS, strict=False):
            if col.button(preset_name, key=f"{state_prefix}_preset_{preset_name}"):
                st.session_state[mix_key] = dict(MIXTURE_PRESETS[preset_name])

        basis = st.radio(
            "Kompozisyon bazı",
            options=["mole", "mass"],
            format_func=lambda value: "Molar yüzde (%)" if value == "mole" else "Kütlesel yüzde (%)",
            horizontal=True,
            key=basis_key,
        )
        value_label = "Molar Yüzde (%)" if basis == "mole" else "Kütlesel Yüzde (%)"
        df_mix = pd.DataFrame(
            list(st.session_state[mix_key].items()),
            columns=["Bileşen", value_label],
        )
        edited_df = st.data_editor(
            df_mix,
            num_rows="dynamic",
            key=f"{state_prefix}_mix_editor",
            column_config={
                "Bileşen": st.column_config.SelectboxColumn(options=MIXTURE_GASES),
                value_label: st.column_config.NumberColumn(min_value=0.0, format="%.4f"),
            },
        )

        new_mix = {}
        for _, row in edited_df.iterrows():
            if pd.notna(row["Bileşen"]) and pd.notna(row[value_label]):
                gas = str(row["Bileşen"])
                val = float(row[value_label])
                if val > 0:
                    new_mix[gas] = new_mix.get(gas, 0.0) + val
        st.session_state[mix_key] = new_mix
        total_pct = sum(new_mix.values())
        if total_pct <= 0:
            st.error("Kompozisyon toplamı sıfırdan büyük olmalıdır.")
        elif abs(total_pct - 100.0) > 0.5:
            st.warning(f"Kompozisyon toplamı {total_pct:.2f}%. Hesaplamada normalize edilecek.")

        mixture_data = get_mixture_fluid_data(new_mix, comp_type=basis, T_c=T_c, P_pa=101325.0)
        st.success(
            f"Hesaplanan karışım özellikleri: Cp={mixture_data['cp']:.1f} J/kgK, "
            f"Rho={mixture_data['density']:.3f} kg/m3, "
            f"mu={mixture_data['mu']:.6f} Pa.s, k={mixture_data['k_cond']:.4f} W/mK"
        )
        return mixture_data, new_mix, basis


def save_state(current_data):
    return json.dumps(current_data, indent=4, ensure_ascii=False)


def crosscheck_row(result, reference_q=None):
    q_value = result["Q [W]"]
    diff_pct = ""
    if reference_q and reference_q > 0:
        diff_pct = round(abs(q_value - reference_q) / reference_q * 100.0, 3)
    return {
        "Metot": result["Method"],
        "Kaynak": result["Source"],
        "Durum": result.get("status", "ok"),
        "Q (kW)": round(q_value / 1000, 2),
        "Q Sapma (%)": diff_pct,
        "Sıcak Çıkış (°C)": round(result["T_hot_out [C]"], 2),
        "Soğuk Çıkış (°C)": round(result["T_cold_out [C]"], 2),
        "Uyarılar": " | ".join(result.get("warnings", [])),
    }


def _render_calc_results(data, tab_results, tab_crosscheck, tab_log):
    """Render previously computed results from cached data dict."""
    hx_data = data["hx_data"]
    geo_res = data.get("geo_res")
    res_main = data["res_main"]
    res_actual = data.get("res_actual")
    crosscheck_results = data["crosscheck_results"]
    pychemengg_warning = data.get("pychemengg_warning")
    report_context = data["report_context"]
    report_text = data.get("report_text", "")
    log_text = data.get("log_text", "")
    u_t_hot = data.get("u_t_hot", "°C")
    u_t_cold = data.get("u_t_cold", "°C")
    U_value = data.get("U_value", 0.0)
    Area = data.get("Area", 0.0)

    from heat_exchanger import FinTubeHeatExchanger
    from heat_exchanger import Fluid as _F

    _h_hot = _F(name=hx_data["hot_name"], cp=1000, density=1, mu=1e-5, k_cond=0.03, is_coolprop=False)
    _h_cold = _F(name=hx_data["cold_name"], cp=1000, density=1, mu=1e-5, k_cond=0.03, is_coolprop=False)
    _hx = FinTubeHeatExchanger(
        _h_hot,
        _h_cold,
        U=hx_data["U"],
        A=hx_data["A"],
        flow_type=hx_data["flow_type"],
        exchanger_type=hx_data["exchanger_type"],
    )

    with tab_results:
        st.markdown("### 📊 Hesaplama Çıktıları ve Özet")
        t_ho_disp = from_celsius(res_main.get("T_hot_out [C]", 0.0), u_t_hot)
        t_co_disp = from_celsius(res_main.get("T_cold_out [C]", 0.0), u_t_cold)
        q_disp = res_main.get("Q [W]", 0.0) / 1000.0
        eps_disp = res_main.get("epsilon", 0.0) * 100.0

        # KPI Metrics Grid (Row 1)
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("🔥 Isı Yükü (Q)", f"{q_disp:.2f} kW")
        kpi2.metric("🌡️ Sıcak Çıkış", f"{t_ho_disp:.2f} {u_t_hot}")
        kpi3.metric("❄️ Soğuk Çıkış", f"{t_co_disp:.2f} {u_t_cold}")
        kpi4.metric("⚡ Etkinlik (ε)", f"%{eps_disp:.1f}")

        # KPI Metrics Grid (Row 2)
        kpi5, kpi6, kpi7, kpi8 = st.columns(4)
        kpi5.metric("📐 Efektif Alan (A)", f"{Area:.2f} m²")
        kpi6.metric("🔄 Toplam U", f"{U_value:.1f} W/m²K")
        if geo_res:
            kpi7.metric("Boru ΔP", f"{geo_res.get('delta_p_tube', 0)/1000.0:.2f} kPa")
            kpi8.metric("Gövde/Hava ΔP", f"{geo_res.get('delta_p_shell', 0)/1000.0:.2f} kPa")
        elif res_actual:
            kpi7.metric("Gereken U", f"{res_actual.get('U_required', 0):.1f} W/m²K")
            kpi8.metric("Gerçek ε", f"%{res_actual.get('epsilon_actual', 0)*100:.1f}")
        else:
            kpi7.metric("LMTD", f"{res_main.get('LMTD', 0):.1f} °C")
            kpi8.metric("F Faktörü", f"{res_main.get('F', 1.0):.3f}")

        if geo_res and geo_res.get("warnings"):
            for msg in geo_res["warnings"]:
                st.warning(msg)
        if res_main.get("warnings"):
            for msg in res_main["warnings"]:
                st.warning(msg)

        # 3-Zone Condenser Breakdown (WEB-1.4)
        if "Q_desuperheat [W]" in res_main:
            q_desup = res_main.get("Q_desuperheat [W]", 0.0) / 1000.0
            q_cond = res_main.get("Q_condensing [W]", 0.0) / 1000.0
            q_sub = res_main.get("Q_subcooling [W]", 0.0) / 1000.0
            q_total_zone = max(1e-6, q_desup + q_cond + q_sub)
            p_desup = (q_desup / q_total_zone) * 100.0
            p_cond = (q_cond / q_total_zone) * 100.0
            p_sub = (q_sub / q_total_zone) * 100.0

            st.markdown("#### ⚡ 3 Bölgeli Kondenser Isı Yükü Dağılımı")
            z_c1, z_c2, z_c3 = st.columns(3)
            z_c1.metric("🟠 Kızgınlık Alma (Desuperheating)", f"{q_desup:.2f} kW", f"%{p_desup:.1f}")
            z_c2.metric("🔵 Yoğuşma (Condensing)", f"{q_cond:.2f} kW", f"%{p_cond:.1f}")
            z_c3.metric("🟢 Aşırı Soğutma (Subcooling)", f"{q_sub:.2f} kW", f"%{p_sub:.1f}")

            st.markdown(
                f"""
                <div style="display:flex; width:100%; height:26px; border-radius:6px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.1); margin:4px 0 16px 0;">
                    <div style="width:{p_desup}%; background:#f97316; display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px; font-weight:bold;" title="Kızgınlık Alma: {q_desup:.1f} kW (%{p_desup:.1f})">%{p_desup:.0f}</div>
                    <div style="width:{p_cond}%; background:#3b82f6; display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px; font-weight:bold;" title="Yoğuşma: {q_cond:.1f} kW (%{p_cond:.1f})">%{p_cond:.0f}</div>
                    <div style="width:{p_sub}%; background:#10b981; display:flex; align-items:center; justify-content:center; color:#fff; font-size:11px; font-weight:bold;" title="Aşırı Soğutma: {q_sub:.1f} kW (%{p_sub:.1f})">%{p_sub:.0f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        # Visualizations Side-by-Side in 2 columns
        c_plot1, c_plot2 = st.columns(2)
        with c_plot1:
            st.markdown("#### 📐 Eşanjör Akış Şeması")
            st.pyplot(_hx.plot_enhanced_schematic(result=res_main))
        with c_plot2:
            st.markdown("#### 🌡️ 1D Sıcaklık Profili")
            st.pyplot(_hx.plot_temperature_profile(res_main))

        # 1D Segmented Finite-Volume Detailed Distribution Expander
        seg_res = next((r for r in crosscheck_results if "Segmented" in r.get("Method", "")), None)
        if seg_res and "T_h_profile" in seg_res and "T_c_profile" in seg_res:
            with st.expander("🔬 1D Sayısal Dilimli (Finite-Volume) Eksenel Sıcaklık ve Yerel ΔT Dağılımı", expanded=False):
                th_prof = seg_res["T_h_profile"]
                tc_prof = seg_res["T_c_profile"]
                dt_prof = seg_res.get("dT_local_profile", [round(h - c, 2) for h, c in zip(th_prof, tc_prof, strict=True)])
                min_dt = seg_res.get("min_dT_local [C]", min(dt_prof) if dt_prof else 0.0)
                n_seg = len(th_prof) - 1

                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.metric("Bölüntü Sayısı", f"{n_seg} Dilim")
                col_s2.metric("Min Yerel Yaklaşım (ΔT_min)", f"{min_dt:.2f} °C")
                col_s3.metric("Segmentli Isı Yükü", f"{seg_res['Q [W]']/1000.0:.2f} kW")

                df_seg = pd.DataFrame({
                    "Konum (x/L %)": [f"%{int(i * 100 / n_seg)}" for i in range(len(th_prof))],
                    "Sıcak Akışkan T_h (°C)": th_prof,
                    "Soğuk Akışkan T_c (°C)": tc_prof,
                    "Yerel Sıcaklık Farkı ΔT (°C)": dt_prof,
                })
                st.dataframe(df_seg, use_container_width=True)

        # Mechanical & Standards Verification (ASME UG-27, TEMA RCB-7, ASME UG-34, TEMA FIV)
        from mechanical import mechanical_design_report

        geom_for_mech = dict(report_context.get("geometry", {}))
        if geo_res:
            for k in ("v_cross", "rho_shell", "rho_tube", "api_face_velocity", "bundle_width", "bundle_length"):
                geom_for_mech.setdefault(k, geo_res.get(k, 0.0))

        mech_rows = mechanical_design_report(geom_for_mech)
        if mech_rows:
            with st.expander("ℹ️ Mekanik Tasarım Bilgi Notu & Standart Kontrolleri (ASME / TEMA)", expanded=False):
                st.caption(
                    "ℹ️ **Bilgilendirme Notu:** Yazılımımızın önceliği termodinamik ve ısı transferi hesaplamalarıdır. "
                    "Aşağıdaki ASME BPVC Section VIII Div 1 ve TEMA 10th Edition et kalınlığı ve FIV (akış kaynaklı titreşim) "
                    "değerleri ön boyutlandırma ve imalat fizibilitesi için referans bilgi amaçlı sunulmaktadır:"
                )
                col_m1, col_m2 = st.columns(2)
                for idx, r in enumerate(mech_rows):
                    target_col = col_m1 if (idx % 2 == 0) else col_m2
                    is_ok = bool(r.get("ok", True))
                    badge = "✅ UYGUN" if is_ok else "⚠️ DİKKAT"
                    badge_color = "#16a34a" if is_ok else "#dc2626"
                    with target_col:
                        st.markdown(
                            f"""
                            <div style="background:#ffffff; border:1px solid #e2e8f0; border-left:4px solid {badge_color}; border-radius:6px; padding:10px 14px; margin-bottom:8px;">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span style="font-weight:600; font-size:13px; color:#1e293b;">{r['label']}</span>
                                    <span style="font-size:11px; font-weight:700; color:{badge_color}; background:#f1f5f9; padding:2px 8px; border-radius:4px;">{badge}</span>
                                </div>
                                <div style="font-size:15px; font-weight:700; color:#0f3a5d; margin-top:4px;">{r['value']}</div>
                                <div style="font-size:11.5px; color:#64748b; margin-top:2px;">Durum: <i>{r['status']}</i></div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

        # Cached Export Document Generation (compiled once per calculation run)
        exports = data.setdefault("exports", {})
        if "tema_pdf" not in exports:
            pdf_images = []
            for fig_fn, caption, h_mm in (
                (_hx.plot_enhanced_schematic, "Akış Şeması", 60.0),
                (_hx.plot_temperature_profile, "Sıcaklık Profili", 55.0),
            ):
                try:
                    fig = fig_fn(result=res_main)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
                    pdf_images.append({"buffer": buf, "caption": caption, "width_mm": 170.0, "height_mm": h_mm})
                except Exception as exc:
                    logger.warning("Rapor görseli üretilemedi: %s", exc)
            if pdf_images:
                report_context["images"] = pdf_images

            exports["tema_pdf"] = generate_tema_datasheet_pdf(report_context)
            exports["report_pdf"] = build_calculation_report_pdf(report_context)
            exports["calc_csv"] = export_calculation_csv(report_context)
            exports["profile_csv"] = export_profile_csv(report_context)
            exports["calc_xlsx"] = export_calculation_excel(report_context)

        # Export Grid Toolbar
        st.markdown("---")
        st.markdown("#### 📥 Mühendislik Çıktıları ve Dışa Aktarma")
        c_dl1, c_dl2, c_dl3 = st.columns(3)
        c_dl1.download_button(
            "📑 TEMA/API 661 Föyü (.pdf)",
            exports["tema_pdf"],
            file_name="tema_api661_datasheet.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        c_dl2.download_button(
            "📄 Detaylı Hesap Raporu (.pdf)",
            exports["report_pdf"],
            file_name="isi_degistirici_raporu.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        c_dl3.download_button(
            "📝 Metin Raporu (.txt)",
            report_text,
            file_name="isi_degistirici_raporu.txt",
            use_container_width=True,
        )

        c_csv1, c_csv2, c_csv3 = st.columns(3)
        c_csv1.download_button(
            "📊 Hesap Verileri Tablosu (.csv)",
            exports["calc_csv"],
            file_name="hesaplama_verileri.csv",
            mime="text/csv",
            use_container_width=True,
        )
        c_csv2.download_button(
            "📈 1D Sıcaklık Profili (.csv)",
            exports["profile_csv"],
            file_name="sicaklik_profili.csv",
            mime="text/csv",
            use_container_width=True,
        )
        c_csv3.download_button(
            "📗 Canlı Formüllü Excel (.xlsx)",
            exports["calc_xlsx"],
            file_name="tema_hesaplama.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with tab_crosscheck:
        st.markdown("### 🔍 Çözücü Algoritmaları Çapraz Doğrulama (Cross-Check)")
        st.caption("Farklı analitik çözücüler (Kendi Algoritmamız Epsilon-NTU, LMTD ve 'ht' Kütüphanesi) aynı girdilerle koşturulup sonuçların tutarlılığı kıyaslanır:")
        if pychemengg_warning:
            st.info(pychemengg_warning)
        df = pd.DataFrame([crosscheck_row(r, reference_q=res_main["Q [W]"]) for r in crosscheck_results])
        st.table(df)

    with tab_log:
        st.markdown("### Hesaplama Logları")
        st.code(log_text, language="log")


st.set_page_config(page_title=APP_NAME, page_icon="🌡️", layout="wide")

st.markdown(
    """
<style>
    /* Modern Global Typography & High-Contrast Theme */
    .stApp {
        background-color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #0f172a;
    }

    /* Universal High-Contrast Labels & Typography */
    .stWidgetLabel, label, [data-testid="stWidgetLabel"] {
        color: #0f172a !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        margin-bottom: 3px !important;
    }
    .stMarkdown p, .stMarkdown span {
        color: #0f172a;
    }
    .stCaption, [data-testid="stCaptionContainer"] {
        color: #334155 !important;
        font-size: 12.5px !important;
        font-weight: 500 !important;
        line-height: 1.4 !important;
    }

    /* Professional Top Banner */
    .app-header-banner {
        background: linear-gradient(135deg, #0f3a5d 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 16px 22px;
        margin-bottom: 16px;
        color: #ffffff;
        box-shadow: 0 4px 14px rgba(15, 58, 93, 0.15);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .app-header-title {
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.3px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .app-header-sub {
        font-size: 13px;
        color: #94a3b8;
        margin-top: 3px;
    }
    .app-header-badge {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 600;
        color: #e2e8f0;
    }

    /* Section Card Headers */
    .side-card-header {
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 12px;
        font-weight: 700;
        font-size: 14.5px;
    }
    .side-card-header.hot {
        background: #fee2e2;
        color: #991b1b;
        border-left: 4px solid #dc2626;
    }
    .side-card-header.cold {
        background: #e0f2fe;
        color: #075985;
        border-left: 4px solid #0284c7;
    }

    /* Fluid Property Badge Bar */
    .fluid-prop-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 6px 0 12px 0;
    }
    .fluid-prop-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 500;
        color: #334155;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .fluid-prop-pill b {
        color: #0f3a5d;
        font-weight: 700;
    }

    /* Modern Card Containers */
    .stPlotlyChart, .stImage, .stTable, .stDataFrame {
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        background: #ffffff;
        padding: 8px;
        margin-bottom: 16px;
        border: 1px solid #e2e8f0;
    }

    /* Sleek Segmented Tab Bar */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 9px 18px;
        font-weight: 600;
        font-size: 13.5px;
        background-color: transparent;
        color: #475569;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e2e8f0;
        color: #0f172a;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f3a5d !important;
        color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(15, 58, 93, 0.25);
    }

    /* Modern Metric Cards */
    .stMetric {
        background: #ffffff;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        border: 1px solid #e2e8f0;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .stMetric:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    [data-testid="stMetricLabel"] {
        color: #475569 !important;
        font-size: 12.5px !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: #0f3a5d !important;
        font-size: 22px !important;
        font-weight: 700 !important;
    }

    /* Form Controls & Inputs */
    input[type="text"], input[type="number"], .stTextInput input, .stNumberInput input {
        color: #0f172a !important;
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 8px 10px !important;
    }
    input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
    }
    [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        color: #0f172a !important;
    }
    [data-baseweb="select"] span {
        color: #0f172a !important;
        font-weight: 600 !important;
    }

    /* BaseWeb Selectbox Popover & Menu Items (High Contrast Fix) */
    [data-baseweb="popover"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.12) !important;
        border-radius: 8px !important;
    }
    [data-baseweb="menu"] {
        background-color: #ffffff !important;
        padding: 4px !important;
    }
    [data-baseweb="menu"] li, [role="option"] {
        color: #0f172a !important;
        background-color: #ffffff !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        border-radius: 6px !important;
        padding: 8px 12px !important;
    }
    [data-baseweb="menu"] li:hover, [role="option"]:hover, [aria-selected="true"] {
        background-color: #f1f5f9 !important;
        color: #0f3a5d !important;
        font-weight: 700 !important;
    }

    /* Polished Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(0,0,0,0.08);
    }

    /* Radio buttons and Checkboxes */
    [data-testid="stRadio"] label, [data-testid="stCheckbox"] label {
        color: #0f172a !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        background: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03) !important;
        margin-bottom: 8px !important;
    }
    [data-testid="stExpander"] summary {
        font-weight: 700 !important;
        color: #0f3a5d !important;
    }
    [data-testid="stExpander"] summary span {
        color: #0f3a5d !important;
        font-weight: 700 !important;
        font-size: 13.5px !important;
    }

    /* Tables */
    [data-testid="stTable"] table {
        width: 100% !important;
        color: #0f172a !important;
        background: #ffffff !important;
        border-collapse: collapse !important;
    }
    [data-testid="stTable"] th {
        background-color: #f1f5f9 !important;
        color: #0f3a5d !important;
        font-weight: 700 !important;
        border-bottom: 2px solid #cbd5e1 !important;
        padding: 8px 12px !important;
    }
    [data-testid="stTable"] td {
        color: #1e293b !important;
        border-bottom: 1px solid #e2e8f0 !important;
        padding: 8px 12px !important;
    }
    [data-testid="stTable"] tbody tr:nth-child(even) {
        background-color: #f8fafc !important;
    }

    /* Alerts & Notifications */
    .stAlert {
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        font-weight: 500;
    }
    .stAlert p, .stAlert span {
        color: #0f172a !important;
        font-weight: 500 !important;
    }

    /* Enhanced Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #f1f5f9 !important;
        border-right: 1px solid #cbd5e1 !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #0f3a5d !important;
        font-weight: 700 !important;
    }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
    [data-testid="stSidebar"] .stWidgetLabel,
    [data-testid="stSidebar"] label {
        color: #0f3a5d !important;
        font-weight: 700 !important;
        font-size: 13px !important;
    }
    [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stTextInput {
        margin-bottom: 8px;
    }

    /* Code Block Logs */
    [data-testid="stCodeBlock"] pre {
        background-color: #0f172a !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
        font-size: 12.5px !important;
        border: 1px solid #334155 !important;
    }

    /* Action & Download Buttons */
    .stDownloadButton > button {
        background-color: #ffffff !important;
        color: #0f3a5d !important;
        border: 1.5px solid #0f3a5d !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        box-shadow: 0 1px 3px rgba(15, 58, 93, 0.08) !important;
        transition: all 0.2s ease !important;
    }
    .stDownloadButton > button:hover {
        background-color: #0f3a5d !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(15, 58, 93, 0.2) !important;
        transform: translateY(-1px) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="app-header-banner">
    <div>
        <div class="app-header-title">🌡️ {APP_NAME}</div>
        <div class="app-header-sub">Modern Isı Değiştirici Termodinamik Analiz ve Canlı Sistem Simülatörü</div>
    </div>
    <div class="app-header-badge">v{VERSION} | Mühendislik Sürümü</div>
</div>
""",
    unsafe_allow_html=True,
)

fluid_list = get_fluid_list_flat()

# --- SIDEBAR: Yapılandırılmış ve Ergonomik Kontroller ---
with st.sidebar.expander("🛠️ İleri Ayarlar (Pompa/Fan/Dil)", expanded=False):
    pump_eff = st.slider("Pompa Verimi (sıvı)", 0.05, 1.0, float(get_val("pump_efficiency") or 0.70), 0.01)
    fan_eff = st.slider("Fan Verimi (gaz)", 0.05, 1.0, float(get_val("fan_efficiency") or 0.60), 0.01)
    _ui_lang = st.selectbox("Dil / Language", ["Türkçe (TR)", "English (EN)"], index=0)
    set_language("en" if "EN" in _ui_lang else "tr")

with st.sidebar.expander("💾 Proje & Veri Yönetimi", expanded=False):
    uploaded_file = st.file_uploader("Kayıtlı verileri yükle (.json)", type=["json"])
    if uploaded_file is not None:
        try:
            loaded_data = normalize_loaded_state(json.load(uploaded_file))
            if st.session_state.get("last_uploaded_file") != uploaded_file.name:
                for key, value in loaded_data.items():
                    st.session_state[key] = value
                st.session_state["last_uploaded_file"] = uploaded_file.name
                st.toast("Veriler yüklendi", icon="✅")
        except Exception as exc:
            logger.exception("Saved input file could not be loaded.")
            st.error(f"Dosya yüklenemedi: {exc}")

    st.caption(f"Sürüm: v{VERSION}")
    if "update_checked" not in st.session_state:
        st.session_state["update_checked"] = True
        st.session_state["update_result"] = check_for_update(timeout=3)
    update_result = st.session_state.get("update_result")
    if update_result and update_result.get("update_available"):
        st.warning(update_result["message"])
        target_dir = st.text_input(
            "İndirme klasörü",
            value=st.session_state.get("update_download_dir", default_download_dir()),
            key="update_download_dir",
        )
        if st.button("Güncelleme Paketini İndir"):
            try:
                with st.status("Güncelleme indiriliyor...", expanded=False):
                    download_result = download_release_asset(update_result, target_dir, app_kind="web", timeout=120)
                st.success(f"İndirildi: {download_result['path']}")
                logger.info("Update downloaded: %s (%s bytes)", download_result["path"], download_result["size"])
            except Exception as exc:
                logger.exception("Update download failed.")
                st.error(f"Güncelleme indirilemedi: {exc}")
    elif update_result and not update_result.get("ok"):
        st.info(update_result.get("message"))
    if st.button("Güncellemeyi Kontrol Et"):
        st.session_state["update_result"] = check_for_update(timeout=5)
        st.rerun()

# --- HIZLI MÜHENDİSLİK ŞABLONLARI ---
with st.expander("⚡ Hızlı Mühendislik Şablonları (Tek Tıkla Senaryo Yükle)", expanded=False):
    st.caption("Farklı eşanjör tiplerini ve çalışma koşullarını hazır parametrelerle anında test edin:")
    p_c1, p_c2, p_c3 = st.columns(3)
    for col, (p_id, p_info) in zip((p_c1, p_c2, p_c3), ENGINEERING_PRESETS.items(), strict=False):
        with col:
            st.markdown(f"**{p_info['title']}**")
            st.caption(p_info["desc"])
            if st.button(f"Yükle: {p_info['title'].split()[1]}", key=f"btn_p_{p_id}", use_container_width=True):
                for k, v in p_info["state"].items():
                    st.session_state[k] = v
                if "calc_cache" in st.session_state:
                    del st.session_state["calc_cache"]
                st.toast(f"{p_info['title']} şablonu yüklendi!", icon="✅")
                st.rerun()

tab_config, tab_geom, tab_results, tab_orc, tab_crosscheck, tab_log = st.tabs(
    [
        "⚙️ Eşanjör & Tesis Konfigürasyonu",
        "📐 Geometri ve Malzeme",
        "📊 Sonuçlar",
        "🏭 Canlı P&ID & 3D Dijital İkiz",
        "🔍 Cross-Check",
        "📝 Sistem Logları",
    ]
)

with tab_config:
    st.markdown("### ⚙️ Eşanjör & Tesis Konfigürasyonu")
    st.caption("Termodinamik çözücü mimarisi, akışkan özellikleri, WHRU Atık Isı Kazanları, TEMA S&T ve ORC çevrim parametreleri.")

    cfg_col1, cfg_col2 = st.columns(2)

    with cfg_col1:
        st.markdown('<div class="side-card-header hot">⚙️ Atık Isı Baca Kazanı (WHRU) Mimarisi & Çözücü Yöntemi</div>', unsafe_allow_html=True)
        exch_type_label = st.selectbox(
            "Eşanjör Tipi",
            options=EXCH_TYPE_OPTIONS,
            index=safe_index(EXCH_TYPE_OPTIONS, get_val("exch_type")),
            key="cfg_exch_type",
        )
        exch_type_internal = EXCH_TYPE_INTERNAL[exch_type_label]

        allowed_flow_labels = _get_allowed_flow_labels(exch_type_internal)
        flow_type = st.selectbox(
            "Akış Konfigürasyonu",
            options=allowed_flow_labels,
            index=safe_index(allowed_flow_labels, get_val("flow_type")),
            key="cfg_flow_type",
        )
        calc_purpose = st.selectbox(
            "Hesaplama Amacı",
            CALC_PURPOSE_OPTIONS,
            index=safe_index(CALC_PURPOSE_OPTIONS, get_val("calc_purpose")),
            key="cfg_calc_purpose",
        )
        u_calc_mode = st.selectbox(
            "U Katsayısı Yöntemi",
            U_MODE_OPTIONS,
            index=safe_index(U_MODE_OPTIONS, get_val("u_calc_mode")),
            key="cfg_u_calc_mode",
        )
        solver_method = st.selectbox(
            "Ana Çözücü Algoritması",
            options=SOLVER_OPTIONS,
            index=safe_index(SOLVER_OPTIONS, get_val("solver_method")),
            key="cfg_solver_method",
        )

        is_phase_change = "Kondenser" in calc_purpose or "Evaporatör" in calc_purpose
        glide_c = 0.0
        enable_multizone = False
        t_subcool = 95.0
        if is_phase_change:
            h_fg = st.number_input(
                "Gizli Isı h_fg (J/kg)",
                min_value=0.0,
                value=float(get_val("h_fg") or 2_200_000),
                step=50_000.0,
                help="Kondenser/Evaporatör için gizli buharlaşma ısısı",
                key="cfg_h_fg",
            )
            glide_c = st.number_input(
                "Zeotropik Kayma / Glide (°C)",
                min_value=0.0,
                max_value=50.0,
                value=float(get_val("glide_c") or 0.0),
                step=0.5,
                help="Zeotropik akışkan karışımları için sıcaklık kayması (glide)",
                key="cfg_glide_c",
            )
            if "Kondenser" in calc_purpose:
                enable_multizone = st.checkbox(
                    "3 Bölgeli Analiz (Kızgınlık Alma + Yoğuşma + Aşırı Soğutma)",
                    value=bool(get_val("enable_multizone")),
                    help="Desuperheating, Condensing ve Subcooling bölgelerini ayrı ayrı boyutlandırır",
                    key="cfg_enable_multizone",
                )
                if enable_multizone:
                    t_subcool = st.number_input(
                        "Aşırı Soğutma Hedefi T_sub (°C)",
                        value=float(get_val("t_subcool") or 95.0),
                        step=1.0,
                        help="Aşırı soğutulmuş sıvı çıkış hedef sıcaklığı",
                        key="cfg_t_subcool",
                    )
        else:
            h_fg = float(get_val("h_fg") or 2_200_000)

        # Sıcak Akışkan (Hot Side)
        st.markdown('<div class="side-card-header hot" style="margin-top:16px;">🔴 Sıcak Akışkan (Hot Side)</div>', unsafe_allow_html=True)
        hot_fluid_sel = st.selectbox(
            "Akışkan Seçimi (Hot)",
            options=fluid_list,
            index=safe_index(fluid_list, get_val("hot_fluid_sel")),
        )
        col_m_val, col_m_u = st.columns([2, 1])
        m_hot_raw = col_m_val.number_input("Sıcak Debi", min_value=0.001, value=float(get_val("m_hot")), step=0.5)
        u_m_hot = col_m_u.selectbox("Birim", ["kg/s", "kg/h", "lb/s", "m³/s", "m³/h", "CFM"], key="u_m_hot")

        col_t_val, col_t_u = st.columns([2, 1])
        T_hot_in_raw = col_t_val.number_input("Sıcak Giriş", value=float(get_val("T_hot_in")), step=1.0)
        u_t_hot = col_t_u.selectbox("Birim", ["°C", "°F", "K"], key="u_t_hot")

        if calc_purpose == CALC_PURPOSE_OPTIONS[1]:
            col_to_val, col_to_u = st.columns([2, 1])
            T_hot_out_opt_raw = col_to_val.number_input(
                "Sıcak Çıkış",
                value=float(get_val("T_hot_out_opt") if get_val("T_hot_out_opt") != -999.0 else 200.0),
                step=1.0,
            )
            u_t_hot_out = col_to_u.selectbox("Birim", ["°C", "°F", "K"], key="u_t_hot_out")
            T_hot_out_opt = to_celsius(T_hot_out_opt_raw, u_t_hot_out)
        else:
            T_hot_out_opt = -999.0

        T_hot_in = to_celsius(T_hot_in_raw, u_t_hot)
        m_hot = m_hot_raw  # We will convert to kg/s later when density is known

        hot_data = materialize_fluid_data(get_fluid_data(hot_fluid_sel), T_hot_in)
        for msg in hot_data.get("warnings", []):
            st.warning(msg)
        cp_hot = float(hot_data.get("cp") or get_val("cp_hot", 1100.0))
        density_hot = float(hot_data.get("density") or get_val("density_hot", 0.5))
        mu_hot = float(hot_data.get("mu") or get_val("mu_hot", 2e-5))
        k_hot = float(hot_data.get("k_cond") or get_val("k_hot", 0.03))

        if hot_data.get("is_coolprop") or hot_data.get("is_iapws"):
            st.markdown(
                f"""
                <div class="fluid-prop-bar">
                    <span class="fluid-prop-pill">Cp: <b>{cp_hot:.0f} J/kgK</b></span>
                    <span class="fluid-prop-pill">ρ: <b>{density_hot:.1f} kg/m³</b></span>
                    <span class="fluid-prop-pill">μ: <b>{mu_hot*1000:.2f} cP</b></span>
                    <span class="fluid-prop-pill">k: <b>{k_hot:.3f} W/mK</b></span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if is_mixture_selection(hot_fluid_sel, hot_data):
            hot_data["is_mixture"] = True
            hot_mix_data, hot_mix, hot_mix_basis = render_mixture_editor("Sıcak akışkan", "hot", T_hot_in)
            cp_hot = hot_mix_data["cp"]
            density_hot = hot_mix_data["density"]
            mu_hot = hot_mix_data["mu"]
            k_hot = hot_mix_data["k_cond"]
        elif not hot_data["is_coolprop"]:
            st.warning("Bu akışkanın özellikleri manuel girilmelidir")
            cp_hot = st.number_input("Hot Cp (J/kg.K)", value=cp_hot)
            density_hot = st.number_input("Hot Density (kg/m³)", min_value=0.001, value=density_hot, format="%.3f")
            manual_hot = is_custom_manual_selection(hot_fluid_sel)
            mu_hot = st.number_input(
                "Hot Dynamic Viscosity (Pa.s)", value=mu_hot, format="%.6f", disabled=not manual_hot
            )
            k_hot = st.number_input(
                "Hot Thermal Conductivity (W/m.K)", value=k_hot, format="%.4f", disabled=not manual_hot
            )

        # Soğuk Akışkan (Cold Side)
        st.markdown('<div class="side-card-header cold" style="margin-top:16px;">🔵 Soğuk Akışkan (Cold Side)</div>', unsafe_allow_html=True)
        cold_fluid_sel = st.selectbox(
            "Akışkan Seçimi (Cold)",
            options=fluid_list,
            index=safe_index(fluid_list, get_val("cold_fluid_sel")),
        )
        col_mc_val, col_mc_u = st.columns([2, 1])
        m_cold_raw = col_mc_val.number_input("Soğuk Debi", min_value=0.001, value=float(get_val("m_cold")), step=0.5)
        u_m_cold = col_mc_u.selectbox("Birim", ["kg/s", "kg/h", "lb/s", "m³/s", "m³/h", "CFM"], key="u_m_cold")

        col_tc_val, col_tc_u = st.columns([2, 1])
        T_cold_in_raw = col_tc_val.number_input("Soğuk Giriş", value=float(get_val("T_cold_in")), step=1.0)
        u_t_cold = col_tc_u.selectbox("Birim", ["°C", "°F", "K"], key="u_t_cold")

        if calc_purpose == CALC_PURPOSE_OPTIONS[1]:
            col_tco_val, col_tco_u = st.columns([2, 1])
            T_cold_out_opt_raw = col_tco_val.number_input(
                "Soğuk Çıkış",
                value=float(get_val("T_cold_out_opt") if get_val("T_cold_out_opt") != -999.0 else 200.0),
                step=1.0,
            )
            u_t_cold_out = col_tco_u.selectbox("Birim", ["°C", "°F", "K"], key="u_t_cold_out")
            T_cold_out_opt = to_celsius(T_cold_out_opt_raw, u_t_cold_out)
        else:
            T_cold_out_opt = -999.0

        T_cold_in = to_celsius(T_cold_in_raw, u_t_cold)
        m_cold = m_cold_raw  # Will convert later

        cold_data = materialize_fluid_data(get_fluid_data(cold_fluid_sel), T_cold_in)
        for msg in cold_data.get("warnings", []):
            st.warning(msg)
        cp_cold = float(cold_data.get("cp") or get_val("cp_cold", 2000.0))
        density_cold = float(cold_data.get("density") or get_val("density_cold", 850.0))
        mu_cold = float(cold_data.get("mu") or get_val("mu_cold", 0.001))
        k_cold = float(cold_data.get("k_cond") or get_val("k_cold", 0.15))

        if cold_data.get("is_coolprop") or cold_data.get("is_iapws"):
            st.markdown(
                f"""
                <div class="fluid-prop-bar">
                    <span class="fluid-prop-pill">Cp: <b>{cp_cold:.0f} J/kgK</b></span>
                    <span class="fluid-prop-pill">ρ: <b>{density_cold:.1f} kg/m³</b></span>
                    <span class="fluid-prop-pill">μ: <b>{mu_cold*1000:.2f} cP</b></span>
                    <span class="fluid-prop-pill">k: <b>{k_cold:.3f} W/mK</b></span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if is_mixture_selection(cold_fluid_sel, cold_data):
            cold_data["is_mixture"] = True
            cold_mix_data, cold_mix, cold_mix_basis = render_mixture_editor("Soğuk akışkan", "cold", T_cold_in)
            cp_cold = cold_mix_data["cp"]
            density_cold = cold_mix_data["density"]
            mu_cold = cold_mix_data["mu"]
            k_cold = cold_mix_data["k_cond"]
        elif not cold_data["is_coolprop"]:
            st.warning("Bu akışkanın özellikleri manuel girilmelidir")
            cp_cold = st.number_input("Cold Cp (J/kg.K)", value=cp_cold)
            density_cold = st.number_input("Cold Density (kg/m³)", min_value=0.001, value=density_cold, format="%.3f")
            manual_cold = is_custom_manual_selection(cold_fluid_sel)
            mu_cold = st.number_input(
                "Cold Dynamic Viscosity (Pa.s)", value=mu_cold, format="%.6f", disabled=not manual_cold
            )
            k_cold = st.number_input(
                "Cold Thermal Conductivity (W/m.K)", value=k_cold, format="%.4f", disabled=not manual_cold
            )

    with cfg_col2:
        st.markdown('<div class="side-card-header cold">🛢️ Kızgın Yağ & Siklopentan S&T Eşanjörü (Therminol 66 / ORC)</div>', unsafe_allow_html=True)

        st_tema_options = [
            "K (Kettle Reboiler Evaporatör - Genişletilmiş Kubbeli)",
            "BEM (Sabit Boru Aynası - Tek Geçişli Gövde)",
            "BEU (U-Borulu Demet - Termal Genleşmeye Dayanıklı)",
            "AKT (Kayan Kafalı - Temizlenebilir Boru Demeti)",
            "AES (Bölünmüş Halka Yüzer Başlıklı)",
        ]
        st_tema_type = st.selectbox(
            "TEMA Eşanjör Tipi",
            options=st_tema_options,
            index=safe_index(st_tema_options, get_val("st_tema_type")),
            key="cfg_st_tema_type",
            help="ASME Section VIII Div 1 ve TEMA 10. Baskı standartlarına uygun gövde-boru tipi seçimi",
        )

        c_sf1, c_sf2 = st.columns(2)
        st_shell_fluid = c_sf1.selectbox(
            "Gövde Tarafı Akışkanı (Shell)",
            ["Therminol 66 (Kızgın Yağ)", "Siklopentan (Buhar/Sıvı)", "Su"],
            index=0,
            key="cfg_st_shell_fluid",
        )
        st_tube_fluid = c_sf2.selectbox(
            "Boru Tarafı Akışkanı (Tube)",
            ["Siklopentan (ORC Çevrim Akışkanı)", "Therminol 66 (Kızgın Yağ)", "Soğutma Suyu"],
            index=0,
            key="cfg_st_tube_fluid",
        )

        c_p1, c_p2 = st.columns(2)
        st_shell_p_des = c_p1.number_input(
            "Gövde Tasarım Basıncı (bar)",
            min_value=1.0,
            max_value=100.0,
            value=float(get_val("st_shell_p_des_bar") or 16.0),
            step=1.0,
            key="cfg_st_shell_p_des",
        )
        st_tube_p_des = c_p2.number_input(
            "Boru Tasarım Basıncı (bar)",
            min_value=1.0,
            max_value=100.0,
            value=float(get_val("st_tube_p_des_bar") or 25.0),
            step=1.0,
            key="cfg_st_tube_p_des",
        )

        c_rf1, c_rf2 = st.columns(2)
        st_shell_fouling = c_rf1.number_input(
            "Gövde Kirlilik Rf (m²K/W)",
            min_value=0.0,
            max_value=0.005,
            value=float(get_val("st_shell_fouling") or 0.0002),
            step=0.00005,
            format="%.5f",
            key="cfg_st_shell_fouling",
            help="Therminol 66 için önerilen kirlilik direnci Rf: 0.00018 - 0.00035 m²K/W",
        )
        st_tube_fouling = c_rf2.number_input(
            "Boru Kirlilik Rf (m²K/W)",
            min_value=0.0,
            max_value=0.005,
            value=float(get_val("st_tube_fouling") or 0.0001),
            step=0.00005,
            format="%.5f",
            key="cfg_st_tube_fouling",
            help="Siklopentan organik akışkanı için önerilen kirlilik direnci Rf: 0.00010 m²K/W",
        )

        c_b1, c_b2 = st.columns(2)
        st_baffle_cut = c_b1.number_input(
            "Şaşırtma Kesme Oranı / Baffle Cut (%)",
            min_value=15.0,
            max_value=45.0,
            value=float(get_val("st_baffle_cut_pct") or 25.0),
            step=5.0,
            key="cfg_st_baffle_cut",
        )
        st_baffle_pitch = c_b2.number_input(
            "Şaşırtma Aralığı (mm)",
            min_value=50.0,
            max_value=1000.0,
            value=float(get_val("st_baffle_spacing_mm") or 150.0),
            step=25.0,
            key="cfg_st_baffle_pitch",
        )

        c_k1, c_k2 = st.columns(2)
        st_kettle_dome_ratio = c_k1.number_input(
            "Kettle Kubbe Çap Oranı (D_dome / D_bundle)",
            min_value=1.2,
            max_value=3.0,
            value=float(get_val("st_kettle_dome_ratio") or 1.80),
            step=0.05,
            key="cfg_st_kettle_dome_ratio",
            help="Kettle Reboiler buhar ayrışma hacmi için buhar kubbesi çapı / boru demeti çap oranı",
        )
        st_pinch_min_target = c_k2.number_input(
            "Hedef Min. Pinch Payı ΔT (°C)",
            min_value=2.0,
            max_value=30.0,
            value=float(get_val("st_pinch_min_target_c") or 8.0),
            step=1.0,
            key="cfg_st_pinch_min_target",
            help="Evaporatör çıkışındaki yağ ile buharlaşma sıcaklığı arasındaki asgari sıcaklık yaklaşımı",
        )

        demister_options = [
            "SS316 Tel Örgü Ped (Wire Mesh Pad - 100 mm)",
            "Vane / Kanatçıklı Damla Tutucu (Chevron Type)",
            "Siklonik Ayırıcı Giriş Difüzörü",
        ]
        st_demister_type = st.selectbox(
            "Buhar Kubbesi Demister (Damla Tutucu) Tipi",
            options=demister_options,
            index=0,
            key="cfg_st_demister_type",
            help="Türbine sıvı damlası kaçışını engelleyen kuru buhar separatörü",
        )

        st.info(
            "💡 **Therminol 66 / Siklopentan Termal Entegrasyon Notu:** Kızgın yağ önce Aşırı Kızdırıcı (Superheater) gövdesine girerek doymuş buharı kızdırır, ardından seri olarak Ön Isıtıcı & Evaporatör (Kettle Reboiler) gövdesine geçerek sıvı siklopentanı buharlaştırır."
        )

        # Superheater (SH) Hot Oil Inlet Temperature & Pipeline Heat Loss
        st.markdown('<div class="side-card-header hot">🔥 Siklopentan Aşırı Kızdırıcı (SH) Yağ Giriş Sıcaklığı & Hat Isı Kaybı</div>', unsafe_allow_html=True)
        sh_oil_modes = [
            "🔗 Otomatik (Kazan Çıkışıyla Aynı)",
            "✏️ Manuel Giriş (°C)",
            "📏 Hat Isı Kaybı / ΔT (°C)",
        ]
        current_sh_mode = get_val("sh_t_oil_in_mode", "🔗 Otomatik (Kazan Çıkışıyla Aynı)")
        sh_mode_idx = 0
        if "Manuel" in str(current_sh_mode):
            sh_mode_idx = 1
        elif "Hat" in str(current_sh_mode) or "Kayıp" in str(current_sh_mode):
            sh_mode_idx = 2

        sh_t_oil_in_mode = st.radio(
            "SH Kızgın Yağ Giriş Sıcaklığı Belirleme Yöntemi",
            options=sh_oil_modes,
            index=sh_mode_idx,
            horizontal=True,
            key="cfg_sh_t_oil_in_mode",
            help="WHRU Atık Isı Kazanından Aşırı Kızdırıcıya kadar olan boru hattındaki mesafe kaynaklı ısı kaybını veya doğrudan girilen SH yağ giriş sıcaklığını belirler",
        )

        c_sh1, c_sh2 = st.columns(2)
        if "Manuel" in sh_t_oil_in_mode:
            sh_t_oil_in_manual = c_sh1.number_input(
                "SH Yağ Giriş Sıcaklığı T_oil,SH,in (°C)",
                min_value=120.0,
                max_value=350.0,
                value=float(get_val("sh_t_oil_in_manual") or 295.0),
                step=1.0,
                key="cfg_sh_t_oil_in_manual",
                help="Aşırı Kızdırıcı gövdesine giren gerçek kızgın yağ sıcaklığı",
            )
            sh_pipe_loss_c = 0.0
            c_sh2.info(f"✏️ SH giriş sıcaklığı doğrudan **{sh_t_oil_in_manual:.1f} °C** olarak sabitlendi.")
        elif "Hat" in sh_t_oil_in_mode or "Kayıp" in sh_t_oil_in_mode:
            sh_pipe_loss_c = c_sh1.number_input(
                "Boru Hattı Sıcaklık Düşüşü ΔT_loss (°C)",
                min_value=0.0,
                max_value=50.0,
                value=float(get_val("sh_pipe_loss_c") or 5.0),
                step=0.5,
                key="cfg_sh_pipe_loss_c",
                help="Boru hattı yalıtım ve hat mesafesi kaynaklı sıcaklık kaybı (T_oil,SH,in = T_kazan_çıkış - ΔT_loss)",
            )
            sh_t_oil_in_manual = None
            c_sh2.info(f"📏 Kazan çıkışına kıyasla **{sh_pipe_loss_c:.1f} °C** hat kaybı düşülecektir.")
        else:
            sh_t_oil_in_manual = None
            sh_pipe_loss_c = 0.0
            st.caption("🔗 SH giriş sıcaklığı, Atık Isı Kazanları çıkış manifold sıcaklığına (T_supply) eşit kabul edilir (ΔT = 0 °C).")

        # Kızgın Yağ Dağıtım Boru Hattı Hidroliği (Darcy-Weisbach)
        st.markdown('<div class="side-card-header hot">🔄 Kızgın Yağ Dağıtım Hattı Borulaması (Darcy-Weisbach)</div>', unsafe_allow_html=True)
        c_pipe1, c_pipe2 = st.columns(2)
        pipe_dn_options = [
            "DN80 (Di=82.5 mm)",
            "DN100 (Di=102.3 mm)",
            "DN125 (Di=127.0 mm)",
            "DN150 (Di=154.0 mm)",
            "DN200 (Di=204.9 mm)",
            "Özel / Manuel",
        ]
        curr_pipe_dn = get_val("pipe_dn_sel", "DN150 (Di=154.0 mm)")
        dn_idx = safe_index(pipe_dn_options, curr_pipe_dn)
        if dn_idx == 0 and curr_pipe_dn not in pipe_dn_options:
            dn_idx = 3
        pipe_dn_sel = c_pipe1.selectbox(
            "Kızgın Yağ Hat Çapı (Nominal DN)",
            options=pipe_dn_options,
            index=dn_idx,
            key="cfg_pipe_dn_sel",
            help="WHRU kazanları ile ORC eşanjörleri arasındaki ana sirkülasyon borusunun nominal çapı",
        )
        dn_map = {"DN80": 82.5, "DN100": 102.3, "DN125": 127.0, "DN150": 154.0, "DN200": 204.9}
        if pipe_dn_sel == "Özel / Manuel":
            pipe_di_mm = c_pipe1.number_input(
                "Boru İç Çapı Di (mm)",
                min_value=40.0,
                max_value=350.0,
                value=float(get_val("pipe_di_mm", 154.0) or 154.0),
                step=5.0,
                key="cfg_pipe_di_mm",
                help="Özel boru et kalınlığına göre net iç akış çapı (mm)",
            )
        else:
            dn_key = pipe_dn_sel.split()[0]
            pipe_di_mm = dn_map.get(dn_key, 154.0)
            c_pipe1.caption(f"📏 Seçili standart iç çap: **{pipe_di_mm:.1f} mm**")

        pipe_length_m = c_pipe2.number_input(
            "Toplam Eşdeğer Hat Uzunluğu - Leq (m)",
            min_value=5.0,
            max_value=500.0,
            value=float(get_val("pipe_length_m", 80.0) or 80.0),
            step=5.0,
            key="cfg_pipe_length_m",
            help="Gidiş-dönüş toplam düz boru uzunluğu ve vana/dirsek eşdeğer uzunlukları toplamı (Leq = L_düz + Σ L_ek)",
        )
        c_pipe2.caption("⚡ Darcy-Weisbach ve Swamee-Jain formülleriyle hat sürtünmesi ve pompa tüketimi hesaplanır.")

        # ORC Condenser
        st.markdown('<div class="side-card-header cold">❄️ ORC Kondenseri (Yoğuşturucu) Tipi & Soğutma Kaynağı</div>', unsafe_allow_html=True)
        condenser_type_label = st.selectbox(
            "Kondenser Soğutma Tipi",
            options=["💧 Su Soğutmalı Kondenser (Su Kulesi / Shell & Tube)", "💨 Hava Soğutmalı Kondenser (Air-Cooled Condenser - ACC)"],
            index=0 if get_val("condenser_type", "air") == "water" else 1,
            key="cfg_condenser_type",
            help="ORC türbin çıkışındaki buharın yoğuşturulmasında kullanılacak soğutma yöntemi",
        )
        is_acc = "Hava" in condenser_type_label
        condenser_type = "air" if is_acc else "water"

        if is_acc:
            c_acc1, c_acc2 = st.columns(2)
            t_air_in = c_acc1.number_input(
                "Çevre Havası Tasarım Sıcaklığı (°C)",
                min_value=5.0,
                max_value=55.0,
                value=float(get_val("t_air_in") or 30.0),
                step=1.0,
                key="cfg_t_air_in",
                help="ACC giriş havası tasarım kuru termometre sıcaklığı",
            )
            acc_fan_eff = c_acc2.number_input(
                "ACC Fan Verimi (%)",
                min_value=30.0,
                max_value=90.0,
                value=float(get_val("acc_fan_eff") or 65.0),
                step=5.0,
                key="cfg_acc_fan_eff",
                help="Aksiyal soğutma fanı aerodinamik/motor verimi",
            )
            t_cw_in = 25.0
            cw_pump_eff = 75.0
        else:
            c_cw1, c_cw2 = st.columns(2)
            t_cw_in = c_cw1.number_input(
                "Soğutma Suyu Giriş Sıcaklığı (°C)",
                min_value=5.0,
                max_value=40.0,
                value=float(get_val("t_cw_in") or 25.0),
                step=1.0,
                key="cfg_t_cw_in",
                help="Soğutma kulesinden gelen suyun kondenser giriş sıcaklığı",
            )
            cw_pump_eff = c_cw2.number_input(
                "Kule Sirkülasyon Pompa Verimi (%)",
                min_value=30.0,
                max_value=90.0,
                value=float(get_val("cw_pump_eff") or 75.0),
                step=5.0,
                key="cfg_cw_pump_eff",
            )
            t_air_in = 30.0
            acc_fan_eff = 65.0

current_data = {
    "exch_type": exch_type_label,
    "calc_purpose": calc_purpose,
    "h_fg": h_fg,
    "glide_c": glide_c,
    "enable_multizone": enable_multizone,
    "t_subcool": t_subcool,
    "pump_efficiency": pump_eff,
    "fan_efficiency": fan_eff,
    "flow_type": flow_type,
    "solver_method": solver_method,
    "u_calc_mode": u_calc_mode,
    "st_tema_type": st_tema_type,
    "st_shell_fluid": st_shell_fluid,
    "st_tube_fluid": st_tube_fluid,
    "st_shell_p_des_bar": st_shell_p_des,
    "st_tube_p_des_bar": st_tube_p_des,
    "st_shell_fouling": st_shell_fouling,
    "st_tube_fouling": st_tube_fouling,
    "st_baffle_cut_pct": st_baffle_cut,
    "st_baffle_spacing_mm": st_baffle_pitch,
    "st_kettle_dome_ratio": st_kettle_dome_ratio,
    "st_pinch_min_target_c": st_pinch_min_target,
    "st_demister_type": st_demister_type,
    "sh_t_oil_in_mode": sh_t_oil_in_mode,
    "sh_t_oil_in_manual": sh_t_oil_in_manual,
    "sh_pipe_loss_c": sh_pipe_loss_c,
    "T_oil_sh_in_C": sh_t_oil_in_manual,
    "sh_t_oil_in": sh_t_oil_in_manual,
    "delta_T_pipe_loss_C": sh_pipe_loss_c,
    "condenser_type": condenser_type,
    "t_air_in": t_air_in,
    "t_cw_in": t_cw_in,
    "T_air_in": t_air_in,
    "T_cw_in": t_cw_in,
    "acc_fan_eff": acc_fan_eff / 100.0,
    "cw_pump_eff": cw_pump_eff / 100.0,
    "hot_fluid_sel": hot_fluid_sel,
    "m_hot": to_kg_s(m_hot_raw, u_m_hot, density_hot),
    "m_hot_raw": m_hot_raw,
    "T_hot_in": T_hot_in,
    "T_hot_out_opt": T_hot_out_opt,
    "cp_hot": cp_hot,
    "density_hot": density_hot,
    "mu_hot": mu_hot,
    "k_hot": k_hot,
    "hot_mix_data": st.session_state.get("hot_mix_data", DEFAULT_STATE["hot_mix_data"]),
    "hot_mix_basis": st.session_state.get("hot_mix_basis", DEFAULT_STATE["hot_mix_basis"]),
    "cold_fluid_sel": cold_fluid_sel,
    "m_cold": to_kg_s(m_cold_raw, u_m_cold, density_cold),
    "m_cold_raw": m_cold_raw,
    "T_cold_in": T_cold_in,
    "T_cold_out_opt": T_cold_out_opt,
    "cp_cold": cp_cold,
    "density_cold": density_cold,
    "mu_cold": mu_cold,
    "k_cold": k_cold,
    "m_oil": to_kg_s(m_cold_raw if any(k in str(cold_fluid_sel) for k in ["Therminol", "Dowtherm", "Mobiltherm", "Calflo", "Yağ", "Oil"]) else m_hot_raw, u_m_cold if any(k in str(cold_fluid_sel) for k in ["Therminol", "Dowtherm", "Mobiltherm", "Calflo", "Yağ", "Oil"]) else u_m_hot, density_cold if any(k in str(cold_fluid_sel) for k in ["Therminol", "Dowtherm", "Mobiltherm", "Calflo", "Yağ", "Oil"]) else density_hot),
    "m_cp": to_kg_s(m_cold_raw, u_m_cold, density_cold),
    "T_cp_in": T_cold_in,
    "m_flue": to_kg_s(m_hot_raw, u_m_hot, density_hot) if any(k in str(hot_fluid_sel) for k in ["Egzoz", "Flue", "Gaz", "Gas", "Air"]) else None,
    "T_flue_in": T_hot_in if any(k in str(hot_fluid_sel) for k in ["Egzoz", "Flue", "Gaz", "Gas", "Air"]) else None,
    "flue_gas_cp": cp_hot if any(k in str(hot_fluid_sel) for k in ["Egzoz", "Flue", "Gaz", "Gas", "Air"]) else None,
    "flue_gas_rho": density_hot if any(k in str(hot_fluid_sel) for k in ["Egzoz", "Flue", "Gaz", "Gas", "Air"]) else None,
    "flue_gas_mu": mu_hot if any(k in str(hot_fluid_sel) for k in ["Egzoz", "Flue", "Gaz", "Gas", "Air"]) else None,
    "flue_gas_k": k_hot if any(k in str(hot_fluid_sel) for k in ["Egzoz", "Flue", "Gaz", "Gas", "Air"]) else None,
    "oil_fluid_sel": cold_fluid_sel if any(k in str(cold_fluid_sel) for k in ["Therminol", "Dowtherm", "Mobiltherm", "Calflo", "Yağ", "Oil"]) else (hot_fluid_sel if any(k in str(hot_fluid_sel) for k in ["Therminol", "Dowtherm", "Mobiltherm", "Calflo", "Yağ", "Oil"]) else None),
    "orc_fluid_sel": cold_fluid_sel if any(k in str(cold_fluid_sel) for k in ["Cyclopentane", "Pentane", "Butane", "R245fa", "R134a", "Toluene"]) else None,
    "P_evap_bar": st_shell_p_des,
    "P_cond_bar": 2.0 if is_acc else 1.5,
    "U_value": float(get_val("U_value", 500.0) or 500.0),
    "Area": float(get_val("Area", 50.0) or 50.0),
    "pipe_dn_sel": pipe_dn_sel,
    "pipe_di_mm": float(pipe_di_mm),
    "pipe_length_m": float(pipe_length_m),
    "cold_mix_data": st.session_state.get("cold_mix_data", DEFAULT_STATE["cold_mix_data"]),
    "cold_mix_basis": st.session_state.get("cold_mix_basis", DEFAULT_STATE["cold_mix_basis"]),
}

# Hesap Birliği (Calculation Unity): Önceden çalıştırılmış detaylı hesaplama varsa UA parametrelerini aktar
if "calc_cache" in st.session_state and st.session_state["calc_cache"]:
    cc = st.session_state["calc_cache"]
    calc_u = cc.get("U_value") or cc.get("hx_data", {}).get("U")
    calc_a = cc.get("Area") or cc.get("hx_data", {}).get("A")
    if calc_u and calc_a and calc_u > 0 and calc_a > 0:
        ua_val = (calc_u * calc_a) / 1000.0
        if "Evaporatör" in calc_purpose or "Kaynatıcı" in calc_purpose:
            current_data["UA_ph"] = max(10.0, ua_val)
        elif "Süperheater" in calc_purpose or "Kızdırıcı" in calc_purpose:
            current_data["UA_sh"] = max(5.0, ua_val)
        else:
            current_data["UA_ph"] = max(10.0, ua_val * 0.70)
            current_data["UA_sh"] = max(5.0, ua_val * 0.30)
        current_data["U_value"] = calc_u
        current_data["Area"] = calc_a
        current_data["synced_from_calc"] = True

with tab_geom:
    st.subheader("Isı Değiştirici Özellikleri")

    geom_dict: dict[str, Any] = {}
    hot_is_tube = False
    D_o_mm = float(get_val("D_o_mm") or 25.4)
    D_i_mm = float(get_val("D_i_mm") or 21.1)
    pitch_mm = float(get_val("pitch_mm") or round(D_o_mm * 1.25, 2))
    D_shell_mm = float(get_val("D_shell_mm") or 350.0)
    layout_angle = str(get_val("tube_layout_angle") or "30")
    tube_passes = int(get_val("tube_passes") or 2)
    shell_passes = int(get_val("shell_passes") or 1)
    N_tubes = int(get_val("N_tubes") or 100)

    if u_calc_mode == U_MODE_OPTIONS[0]:
        st.info("ℹ️ Basit modda toplam ısı transfer katsayısı (U) ve ısı transfer alanı (A) doğrudan kullanıcı girdisi olarak alınır.")
        c_u1, c_u2 = st.columns(2)
        with c_u1:
            U_value = st.number_input(
                "Toplam Isı Transfer Katsayısı - U (W/m²K)",
                min_value=0.1,
                value=float(get_val("U_value")),
                step=1.0,
            )
        with c_u2:
            Area = st.number_input(
                "Toplam Isı Transfer Alanı - A (m²)",
                min_value=0.1,
                value=float(get_val("Area")),
                step=1.0,
            )
        current_data["U_value"] = U_value
        current_data["Area"] = Area
    else:
        st.success("Geometrik mod aktif: U katsayısı ve ısı transfer alanı boru/gövde geometrisi üzerinden hesaplanacaktır.")
        g1, g2, g3 = st.columns(3)

        with g1:
            st.markdown('<div class="side-card-header" style="background:#f1f5f9; color:#0f3a5d; border-left:4px solid #0f3a5d;">📏 Boru Boyutları</div>', unsafe_allow_html=True)
            bwg_labels = ["Manuel"] + [p["label"] for p in _bwg_presets]
            bwg_sel = st.selectbox(
                "Boru Preseti (BWG)",
                options=bwg_labels,
                index=safe_index(bwg_labels, get_val("bwg_preset") or "Manuel"),
            )
            if bwg_sel != "Manuel":
                for p in _bwg_presets:
                    if p["label"] == bwg_sel:
                        D_o_mm = float(p["D_o_mm"])
                        D_i_mm = float(p["D_i_mm"])
                        break
                current_data["D_o_mm"] = D_o_mm
                current_data["D_i_mm"] = D_i_mm
            else:
                D_o_mm = st.number_input("Dış Çap - Do (mm)", value=float(get_val("D_o_mm")))
                D_i_mm = st.number_input("İç Çap - Di (mm)", value=float(get_val("D_i_mm")))
                current_data.update({"D_o_mm": D_o_mm, "D_i_mm": D_i_mm})
            if D_i_mm >= D_o_mm:
                st.error(f"⚠️ Geometri Hatası: İç çap ({D_i_mm:.1f} mm) dış çaptan ({D_o_mm:.1f} mm) küçük olmalıdır!")
            current_data["bwg_preset"] = bwg_sel
            L_m = st.number_input("Boru Uzunluğu - L (m)", value=float(get_val("L_m")))
            N_tubes = st.number_input("Boru Sayısı", value=int(get_val("N_tubes")), step=1)

            geom_dict["D_o"] = D_o_mm / 1000.0
            geom_dict["D_i"] = D_i_mm / 1000.0
            geom_dict["L"] = L_m
            geom_dict["N_tubes"] = N_tubes

            current_data.update({"L_m": L_m, "N_tubes": N_tubes})

        with g2:
            st.markdown('<div class="side-card-header" style="background:#f1f5f9; color:#0f3a5d; border-left:4px solid #0f3a5d;">🛡️ Malzeme &amp; Gövde</div>', unsafe_allow_html=True)
            mat_options = {f"{k} (k={v:.1f})": v for k, v in TUBE_MATERIALS.items()}
            # Önceki kayıtlarda k değeri formatsız olabilir, isim bazlı eşleştirme:
            curr_mat = get_val("tube_material")
            matched_idx = 0
            if curr_mat:
                for idx, opt in enumerate(mat_options.keys()):
                    if opt == curr_mat or opt.split()[0] == curr_mat.split()[0]:
                        matched_idx = idx
                        break
            tube_material = st.selectbox(
                "Boru Malzemesi",
                options=list(mat_options.keys()),
                index=matched_idx,
            )
            geom_dict["k_wall"] = mat_options[tube_material]
            current_data["tube_material"] = tube_material

            if FLOW_MAP[flow_type].startswith("cross"):
                pitch_mm = st.number_input("Transverse Pitch (mm)", value=float(get_val("pitch_mm")))
                if pitch_mm <= D_o_mm:
                    st.error(f"⚠️ Geometri Hatası: Hatve/Pitch ({pitch_mm:.1f} mm) boru dış çapından ({D_o_mm:.1f} mm) büyük olmalıdır!")
                geom_dict["pitch"] = pitch_mm / 1000.0
                current_data["pitch_mm"] = pitch_mm
            else:
                D_shell_mm = st.number_input("Gövde İç Çapı (mm)", value=float(get_val("D_shell_mm")))
                if D_shell_mm <= D_o_mm:
                    st.error(f"⚠️ Geometri Hatası: Gövde iç çapı ({D_shell_mm:.1f} mm) boru dış çapından ({D_o_mm:.1f} mm) büyük olmalıdır!")
                geom_dict["D_shell"] = D_shell_mm / 1000.0
                current_data["D_shell_mm"] = D_shell_mm

                if exch_type_internal == "shell_and_tube":
                    pitch_mm = st.number_input(
                        "Boru Hatvesi - Pitch (mm)",
                        value=float(get_val("pitch_mm") or round(D_o_mm * 1.25, 2)),
                    )
                    if pitch_mm <= D_o_mm:
                        st.error(f"⚠️ Geometri Hatası: Hatve/Pitch ({pitch_mm:.1f} mm) boru dış çapından ({D_o_mm:.1f} mm) büyük olmalıdır!")
                    geom_dict["pitch"] = pitch_mm / 1000.0
                    current_data["pitch_mm"] = pitch_mm

                    baffle_spacing_mm = st.number_input(
                        "Deflektör Aralığı (mm)", value=float(get_val("baffle_spacing_mm") or 200.0)
                    )
                    baffle_cut = st.number_input(
                        "Deflektör Kesim Oranı", value=float(get_val("baffle_cut") or 0.25), min_value=0.0, max_value=0.5
                    )
                    layout_angle = st.selectbox(
                        "Yerleşim Açısı",
                        options=["30", "45", "60", "90"],
                        index=safe_index(["30", "45", "60", "90"], get_val("tube_layout_angle") or "30"),
                    )
                    shell_passes = st.number_input(
                        "Gövde Geçişi", value=int(get_val("shell_passes") or 1), min_value=1, max_value=16, step=1
                    )
                    tube_passes = st.number_input(
                        "Boru Geçişi", value=int(get_val("tube_passes") or 2), min_value=1, max_value=16, step=1
                    )
                    tema_labels = ["—"] + list(TEMA_DESIGNATIONS.keys())
                    tema_designation = st.selectbox(
                        "TEMA İsimlendirme",
                        options=tema_labels,
                        index=safe_index(tema_labels, get_val("tema_designation") or "—"),
                    )
                    geom_dict["baffle_spacing"] = baffle_spacing_mm / 1000.0
                    geom_dict["baffle_cut"] = baffle_cut
                    geom_dict["tube_layout_angle"] = layout_angle
                    geom_dict["kettle_dome_ratio"] = float(st_kettle_dome_ratio)
                    geom_dict["demister_type"] = st_demister_type
                    geom_dict["shell_passes"] = int(shell_passes)
                    geom_dict["tube_passes"] = int(tube_passes)
                    geom_dict["tema_designation"] = tema_designation
                    current_data.update(
                        {
                            "baffle_spacing_mm": baffle_spacing_mm,
                            "baffle_cut": baffle_cut,
                            "tube_layout_angle": layout_angle,
                            "shell_passes": int(shell_passes),
                            "tube_passes": int(tube_passes),
                            "tema_designation": tema_designation,
                        }
                    )

            hot_is_tube_str = st.radio(
                "İç Boruda Hangi Akışkan Var?",
                ["Soğuk Akışkan", "Sıcak Akışkan"],
                index=safe_index(["Soğuk Akışkan", "Sıcak Akışkan"], get_val("hot_is_tube")),
            )
            hot_is_tube = hot_is_tube_str == "Sıcak Akışkan"
            current_data["hot_is_tube"] = hot_is_tube_str

            fouling_labels = [lbl for lbl, _v in _fouling_presets]
            fouling_sel = st.selectbox(
                "Fouling Preseti (TEMA)",
                options=fouling_labels,
                index=safe_index(fouling_labels, get_val("fouling_preset") or "Temiz (yok)"),
            )
            for lbl, val in _fouling_presets:
                if lbl == fouling_sel:
                    R_f_i = R_f_o = float(val)
                    break
            current_data["fouling_preset"] = fouling_sel
            geom_dict["R_f_i"] = R_f_i
            geom_dict["R_f_o"] = R_f_o
            current_data["R_f_i"] = R_f_i
            current_data["R_f_o"] = R_f_o

        with g3:
            st.markdown('<div class="side-card-header" style="background:#f1f5f9; color:#0f3a5d; border-left:4px solid #0f3a5d;">🪶 Kanatçıklar (Fins)</div>', unsafe_allow_html=True)
            if not FLOW_MAP[flow_type].startswith("cross"):
                st.caption(
                    "Kanatçık alanı özellikle çapraz akış/finned tube ön tasarımı için anlamlıdır; counter/parallel modda hesaba katılmaz."
                )
            is_finned_default = bool(get_val("is_finned"))
            is_finned = st.checkbox("Borular kanatçıklı mı?", value=is_finned_default)
            geom_dict["is_finned"] = is_finned
            current_data["is_finned"] = is_finned

            if is_finned:
                fin_h_mm = st.number_input("Kanatçık Yüksekliği (mm)", value=float(get_val("fin_h_mm")))
                fin_t_mm = st.number_input("Kanatçık Kalınlığı (mm)", value=float(get_val("fin_t_mm")))
                fin_density = st.number_input("Metredeki Kanatçık Sayısı (1/m)", value=int(get_val("fin_density")))
                fin_material = st.selectbox(
                    "Kanatçık Malzemesi",
                    options=["Alüminyum (k=237)", "Karbon Çelik (k=45)"],
                    index=safe_index(["Alüminyum (k=237)", "Karbon Çelik (k=45)"], get_val("fin_material")),
                )

                geom_dict["fin_height"] = fin_h_mm / 1000.0
                geom_dict["fin_thickness"] = fin_t_mm / 1000.0
                geom_dict["fin_density"] = fin_density
                fin_type = st.selectbox(
                    "Kanatçık Tipi",
                    options=["Dairesel (Annular)", "Düz (Rectangular)"],
                    index=safe_index(
                        ["Dairesel (Annular)", "Düz (Rectangular)"], get_val("fin_type") or "Dairesel (Annular)"
                    ),
                )
                fin_attachment = st.selectbox(
                    "API 661 Kanat Tipi",
                    options=ache_fin_names(),
                    index=safe_index(ache_fin_names(), get_val("fin_attachment")),
                )
                geom_dict["k_fin"] = 237.0 if "Alüminyum" in fin_material else 45.0
                geom_dict["fin_type"] = "rectangular" if "Rectangular" in fin_type else "annular"
                geom_dict["fin_attachment"] = fin_attachment
                geom_dict["api661_fin_type"] = fin_attachment

                current_data.update(
                    {
                        "fin_h_mm": fin_h_mm,
                        "fin_t_mm": fin_t_mm,
                        "fin_density": fin_density,
                        "fin_material": fin_material,
                        "fin_type": fin_type,
                        "fin_attachment": fin_attachment,
                    }
                )

        U_value = 0.0
        Area = 0.0

    # ASME Section VIII Div 1 & TEMA Mechanical Parameters (WEB-1.1)
    with st.expander("🛡️ ASME Sec VIII & TEMA Mekanik Tasarım Parametreleri", expanded=False):
        st.caption("Basınçlı kap et kalınlığı (ASME UG-27, UG-34) ve TEMA boru aynası / titreşim doğrulamaları için parametreler:")
        m1, m2, m3 = st.columns(3)
        with m1:
            P_design_bar = st.number_input(
                "Tasarım Basıncı - P_des (bar)",
                min_value=0.1,
                value=float(get_val("P_design_bar") or 10.0),
                step=1.0,
                help="İç tasarım basıncı (gauge)",
            )
            CA_mm = st.number_input(
                "Korozyon Payı - CA (mm)",
                min_value=0.0,
                value=float(get_val("CA_mm") or 3.0),
                step=0.5,
                help="Karbon çelik için genelde 3.0 mm, paslanmaz için 0-1.5 mm",
            )
        with m2:
            S_stress_mpa = st.number_input(
                "İzin Verilen Gerilme - S (MPa)",
                min_value=10.0,
                value=float(get_val("S_stress_mpa") or 118.0),
                step=5.0,
                help="ASME Sec II Part D allowable stress (örn. SA-516 Gr 70 ~118 MPa @ 150°C)",
            )
            tema_classes = ["R (Petrol & Ağır Sanayi)", "C (Genel Ticari Proses)", "B (Kimyasal Proses)"]
            tema_class_str = st.selectbox(
                "TEMA Sınıfı",
                tema_classes,
                index=safe_index(tema_classes, get_val("tema_class_str") or tema_classes[0]),
            )
        with m3:
            joint_effs = ["0.85 (Noktasal RT / Spot)", "1.00 (Tam RT / Full)", "0.70 (RT Yok / No RT)"]
            joint_eff_str = st.selectbox(
                "Kaynak Dikiş Faktörü (E)",
                joint_effs,
                index=safe_index(joint_effs, get_val("joint_eff_str") or joint_effs[0]),
            )

        geom_dict["design_pressure"] = P_design_bar * 1e5
        geom_dict["design_stress"] = S_stress_mpa * 1e6
        geom_dict["corrosion_allowance"] = CA_mm / 1000.0
        geom_dict["joint_efficiency"] = float(joint_eff_str.split()[0])
        geom_dict["tema_class"] = tema_class_str.split()[0]
        current_data.update({
            "P_design_bar": P_design_bar,
            "S_stress_mpa": S_stress_mpa,
            "CA_mm": CA_mm,
            "joint_eff_str": joint_eff_str,
            "tema_class_str": tema_class_str,
        })

    # 2D Tubesheet Tube Layout Preview (WEB-1.5)
    if exch_type_internal == "shell_and_tube":
        with st.expander("🎨 Boru Demeti Yerleşim Önizlemesi (2D Ayna Kesiti)", expanded=True):
            st.caption(
                f"TEMA Boru Aynası Yerleşim Geometrisi: {layout_angle}° açılı hatve, "
                f"Gövde İç Çapı = {D_shell_mm:.1f} mm, Do = {D_o_mm:.1f} mm, "
                f"Pitch = {geom_dict.get('pitch', D_o_mm*1.25/1000.0)*1000.0:.1f} mm | {tube_passes} Geçiş"
            )
            from tubesheet_component import generate_tubesheet_svg
            ts_pitch = geom_dict.get("pitch", (D_o_mm * 1.25) / 1000.0) * 1000.0
            ts_svg = generate_tubesheet_svg(
                D_shell_mm=D_shell_mm,
                D_o_mm=D_o_mm,
                D_i_mm=D_i_mm,
                pitch_mm=ts_pitch,
                layout_angle=layout_angle,
                N_tubes=int(N_tubes),
                tube_passes=int(tube_passes),
                shell_passes=int(shell_passes),
            )
            st.markdown(ts_svg, unsafe_allow_html=True)

with tab_orc:
    st.markdown("### 🏭 Tümleşik ORC & Kızgın Yağ Döngüsü Canlı P&ID ve 3D Dijital İkiz Simülatörü")
    st.caption(
        "Kızgın yağ sirkülasyon hatları, 1-5 adet dinamik atık ısı kazanı (WHRU), boru köprüleri ve mesnetleri (pipe racks & supports), "
        "beton kaideler üzerinde oturan ekipmanlar, sirkülasyon pompası, oransal by-pass vanası ve seri bağlı aşırı kızdırıcı (superheater) ile "
        "ön ısıtıcı/evaporatörü içeren etkileşimli tesis modeli. **2D Şematik** veya **3D Dijital İkiz** modları arasında geçiş yapabilir, "
        "ekipmanlara tıklayarak canlı telemetri değerlerini ve hidrolik manifold dengesini izleyebilirsiniz."
    )
    if current_data.get("synced_from_calc"):
        st.success(
            f"🔗 **Hesap Birliği Aktif:** Tab 1 / Tab 2'de tasarlanan eşanjör geometrisi "
            f"(U = **{current_data['U_value']:.1f} W/m²K**, A = **{current_data['Area']:.1f} m²** "
            f"➜ UA = **{(current_data['U_value']*current_data['Area']/1000.0):.1f} kW/K**) "
            f"ve Darcy-Weisbach boru hattı parametreleri (**{pipe_dn_sel}**, L = **{pipe_length_m:.0f} m**) canlı P&ID simülasyonuna entegre edilmiştir."
        )
    else:
        st.info(
            f"ℹ️ **Hesap Birliği:** Tab 1'deki borulama parametreleri (**{pipe_dn_sel}**, L = **{pipe_length_m:.0f} m**) ve akışkan debileri "
            f"canlı P&ID'ye aktarılmıştır. Tab 2'de hesaplanan özel eşanjör U ve Alan değerlerinin P&ID'ye tam yansıması için "
            f"**'🚀 HESAPLA'** butonunu çalıştırabilirsiniz."
        )
    _st_components.html(get_orc_schematic_html(current_data), height=890, scrolling=True)

st.sidebar.download_button(
    label="💾 Mevcut Girdileri Kaydet (.json)",
    data=save_state(current_data),
    file_name="heat_exchanger_save.json",
    mime="application/json",
    use_container_width=True,
)

validation_errors = []

# 1. Sıcaklık Kontrolleri (Termodinamik 2. Yasa)
if T_hot_in <= T_cold_in:
    validation_errors.append(
        f"Sıcak akışkan giriş sıcaklığı ({T_hot_in:.1f}°C), soğuk akışkan giriş sıcaklığından ({T_cold_in:.1f}°C) yüksek olmalıdır (2. Termodinamik Yasası)."
    )

# 2. Debi Kontrolleri
if m_hot_raw <= 0:
    validation_errors.append("Sıcak akışkan debisi sıfırdan büyük olmalıdır.")
if m_cold_raw <= 0:
    validation_errors.append("Soğuk akışkan debisi sıfırdan büyük olmalıdır.")

# 3. Mevcut Eşanjör (Rating / Kontrol) Modu Sıcaklık Limitleri
if calc_purpose == CALC_PURPOSE_OPTIONS[1]:
    if T_hot_out_opt >= T_hot_in:
        validation_errors.append(
            f"Mevcut eşanjörde sıcak akışkan çıkış sıcaklığı ({T_hot_out_opt:.1f}°C), giriş sıcaklığından ({T_hot_in:.1f}°C) düşük olmalıdır."
        )
    if T_cold_out_opt <= T_cold_in:
        validation_errors.append(
            f"Mevcut eşanjörde soğuk akışkan çıkış sıcaklığı ({T_cold_out_opt:.1f}°C), giriş sıcaklığından ({T_cold_in:.1f}°C) yüksek olmalıdır."
        )
    if T_hot_out_opt < T_cold_in:
        validation_errors.append(
            f"Sıcak akışkan çıkış sıcaklığı ({T_hot_out_opt:.1f}°C), soğuk giriş sıcaklığının ({T_cold_in:.1f}°C) altına inemez."
        )
    if FLOW_MAP.get(flow_type) == "parallel" and T_hot_out_opt < T_cold_out_opt:
        validation_errors.append(
            f"Paralel akışta sıcak çıkış sıcaklığı ({T_hot_out_opt:.1f}°C), soğuk çıkış sıcaklığından ({T_cold_out_opt:.1f}°C) düşük olamaz (sıcaklık kesişmesi)."
        )

# 4. Isı Transferi ve Boyut Kontrolleri
if u_calc_mode == U_MODE_OPTIONS[0]:
    if U_value <= 0:
        validation_errors.append("Toplam ısı transfer katsayısı (U) sıfırdan büyük olmalıdır.")
    if Area <= 0:
        validation_errors.append("Toplam ısı transfer yüzey alanı (A) sıfırdan büyük olmalıdır.")
else:
    d_i = geom_dict.get("D_i", 0.0)
    d_o = geom_dict.get("D_o", 0.0)
    l_tube = geom_dict.get("L", 0.0)
    n_t = geom_dict.get("N_tubes", 0)
    if d_o <= 0 or d_i <= 0:
        validation_errors.append("Boru iç ve dış çapları sıfırdan büyük olmalıdır.")
    elif d_i >= d_o:
        validation_errors.append(
            f"Boru dış çapı ({d_o*1000.0:.1f} mm), iç çapından ({d_i*1000.0:.1f} mm) büyük olmalıdır."
        )
    if l_tube <= 0:
        validation_errors.append("Boru uzunluğu (L) sıfırdan büyük olmalıdır.")
    if n_t < 1:
        validation_errors.append("Boru sayısı en az 1 olmalıdır.")
    if geom_dict.get("k_wall", 0.0) <= 0:
        validation_errors.append("Boru malzemesi ısıl iletkenliği (k_wall) sıfırdan büyük olmalıdır.")
    pitch = geom_dict.get("pitch", 0.0)
    if pitch > 0 and pitch <= d_o:
        validation_errors.append(
            f"Boru hatvesi ({pitch*1000.0:.1f} mm), boru dış çapından ({d_o*1000.0:.1f} mm) büyük olmalıdır."
        )
    d_shell = geom_dict.get("D_shell", 0.0)
    if d_shell > 0 and d_shell <= d_o:
        validation_errors.append(
            f"Gövde iç çapı ({d_shell*1000.0:.1f} mm), boru dış çapından ({d_o*1000.0:.1f} mm) büyük olmalıdır."
        )

# 5. İki-Fazlı (Kondenser / Evaporatör) Kontrolleri
is_cond_chk = "Kondenser" in calc_purpose
is_evap_chk = "Evaporatör" in calc_purpose
if is_cond_chk or is_evap_chk:
    if h_fg <= 0:
        validation_errors.append("İki-fazlı hesaplamalar için buharlaşma gizli ısısı (h_fg) sıfırdan büyük olmalıdır.")
    if glide_c < 0:
        validation_errors.append("Sıcaklık kayması (glide) negatif olamaz.")
    if t_subcool < 0:
        validation_errors.append("Aşırı soğutma derecesi (subcooling) negatif olamaz.")

# 6. Manuel Akışkan Termofiziksel Özellik Kontrolleri
if not hot_data.get("is_coolprop") and not hot_data.get("is_iapws") and (cp_hot <= 0 or density_hot <= 0 or mu_hot <= 0 or k_hot <= 0):
    validation_errors.append("Sıcak akışkan manuel termofiziksel özellikleri (cp, rho, mu, k) sıfırdan büyük olmalıdır.")
if not cold_data.get("is_coolprop") and not cold_data.get("is_iapws") and (cp_cold <= 0 or density_cold <= 0 or mu_cold <= 0 or k_cold <= 0):
    validation_errors.append("Soğuk akışkan manuel termofiziksel özellikleri (cp, rho, mu, k) sıfırdan büyük olmalıdır.")

# 7. WHRU ve Süperkızdırıcı (SH) Yağ Giriş Kontrolleri
t_sh_override_val = current_data.get("orc_sh_t_oil_in_override_c")
if t_sh_override_val is not None:
    try:
        t_sh_float = float(t_sh_override_val)
        if t_sh_float <= T_cold_in:
            validation_errors.append(
                f"Siklopentan Kızdırıcı (SH) kızgın yağ giriş sıcaklığı ({t_sh_float:.1f}°C), soğuk giriş sıcaklığından ({T_cold_in:.1f}°C) yüksek olmalıdır."
            )
    except (ValueError, TypeError):
        pass

hata_var = len(validation_errors) > 0

hot_fluid_obj = None
cold_fluid_obj = None

if not hata_var:
    try:
        if hot_data.get("is_iapws"):
            hot_fluid_obj = Fluid(name=hot_data["name"], is_iapws=True, calc_temp_c=T_hot_in)
        elif hot_data["is_coolprop"]:
            hot_fluid_obj = Fluid(name=hot_data["name"], is_coolprop=True, calc_temp_c=T_hot_in)
        else:
            hot_fluid_obj = build_manual_fluid(hot_data, cp_hot, density_hot, mu_hot, k_hot)

        if cold_data.get("is_iapws"):
            cold_fluid_obj = Fluid(name=cold_data["name"], is_iapws=True, calc_temp_c=T_cold_in)
        elif cold_data["is_coolprop"]:
            cold_fluid_obj = Fluid(name=cold_data["name"], is_coolprop=True, calc_temp_c=T_cold_in)
        else:
            cold_fluid_obj = build_manual_fluid(cold_data, cp_cold, density_cold, mu_cold, k_cold)

        # 1. Şimdi yoğunlukları bildiğimize göre debileri kg/s'e çevirelim
        rho_h = hot_fluid_obj.density
        rho_c = cold_fluid_obj.density
        m_hot = to_kg_s(m_hot_raw, u_m_hot, rho_h)
        m_cold = to_kg_s(m_cold_raw, u_m_cold, rho_c)

    except Exception as exc:
        logger.exception("Fluid property preparation failed.")
        st.error(f"Akışkan özellikleri veya çevrim sırasında hata oluştu: {exc}")
        st.caption(f"Detaylı log dosyası: {LOG_FILE}")
        hata_var = True

# --- ACTION BAR: Belirgin ve Ergonomik Çözüm Paneli ---
st.markdown("---")
c_act_info, c_act_btn = st.columns([3, 1])
with c_act_info:
    if hata_var:
        for err in validation_errors:
            st.error(f"❌ {err}")
    elif "calc_cache" in st.session_state:
        _q_val = st.session_state.calc_cache["res_main"].get("Q [W]", 0.0) / 1000.0
        _eps = st.session_state.calc_cache["res_main"].get("epsilon", 0.0) * 100.0
        st.info(f"💡 **Son Hesaplama:** Q = **{_q_val:.1f} kW** | ε = **%{_eps:.1f}** — Detaylı analiz ve föyler için **'📊 Sonuçlar'** sekmesini açabilirsiniz.")
    else:
        st.caption("ℹ️ Girdilerinizi tamamladıktan sonra hesaplamayı başlatmak için 'HESAPLA' butonuna basın.")

with c_act_btn:
    run_calc = st.button("🚀 HESAPLA", use_container_width=True, type="primary", disabled=hata_var)

if not hata_var and run_calc:
    # --- Logging Setup for this Run ---
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    handler._streamlit_run_handler = True  # type: ignore[attr-defined]
    root_logger.addHandler(handler)

    try:
        root_logger.info("Hesaplama başlatıldı.")
        hx = FinTubeHeatExchanger(
            hot_fluid_obj,  # type: ignore[arg-type]
            cold_fluid_obj,  # type: ignore[arg-type]
            U=1.0,
            A=1.0,
            flow_type=FLOW_MAP[flow_type],
            exchanger_type=exch_type_internal,
        )
        hx.pump_efficiency = float(pump_eff)
        hx.fan_efficiency = float(fan_eff)

        geo_res = None
        if u_calc_mode == U_MODE_OPTIONS[1]:
            if geom_dict["D_i"] >= geom_dict["D_o"]:
                st.error("❌ Mantıksal Hata: Dış Çap, İç Çaptan büyük olmalıdır!")
                st.stop()
            if geom_dict["L"] <= 0 or geom_dict["N_tubes"] < 1:
                st.error("❌ Mantıksal Hata: Boru boyu ve boru sayısı sıfırdan büyük olmalıdır!")
                st.stop()
            try:
                geo_res = hx.calculate_geometric_U(geom_dict, m_hot, m_cold, hot_is_tube)
                U_value = geo_res["U"]
                Area = geo_res["A_total"]
            except Exception as exc:
                root_logger.exception("Geometric calculation failed.")
                st.error(f"Geometrik hesaplama hatası: {exc}")
                st.caption(f"Detaylı log dosyası: {LOG_FILE}")
                st.stop()
        else:
            hx.U = U_value
            hx.A = Area

        try:
            is_condenser = "Kondenser" in calc_purpose
            is_evaporator = "Evaporatör" in calc_purpose
            if is_condenser or is_evaporator:
                if h_fg <= 0:
                    st.error("❌ İki-fazlı hesap için gizli ısı (h_fg) girilmelidir.")
                    st.stop()
                if is_condenser:
                    hx.hot_fluid.h_fg = h_fg
                    if enable_multizone:
                        res_custom = hx.solve_multizone_condenser(
                            m_hot,
                            m_cold,
                            T_hot_in=T_hot_in,
                            T_sat=T_hot_in if glide_c <= 0 else (T_hot_in - glide_c / 2.0),
                            T_cold_in=T_cold_in,
                            h_fg=h_fg,
                            T_subcool=t_subcool,
                        )
                    else:
                        res_custom = hx.solve_condenser(
                            m_hot,
                            m_cold,
                            T_sat=T_hot_in,
                            T_cold_in=T_cold_in,
                            h_fg=h_fg,
                            glide=glide_c,
                        )
                else:
                    hx.cold_fluid.h_fg = h_fg
                    res_custom = hx.solve_evaporator(
                        m_hot,
                        m_cold,
                        T_hot_in=T_hot_in,
                        T_sat=T_cold_in,
                        h_fg=h_fg,
                        glide=glide_c,
                    )
                crosscheck_results = [res_custom]
                res_custom_lmtd = res_ht = res_lmtd = {}
            else:
                # Faz E1: ortalama sıcaklıkta özellik iyileştirmesi (kapsüllendi)
                holder = {"geo_res": geo_res}

                def _rebuild(T_hot_mid, T_cold_mid, _m_hot, _m_cold):
                    hot_data_mid = materialize_fluid_data(get_fluid_data(hot_fluid_sel), T_hot_mid)
                    cold_data_mid = materialize_fluid_data(get_fluid_data(cold_fluid_sel), T_cold_mid)
                    if hot_data_mid.get("is_iapws"):
                        _hf = Fluid(name=hot_data_mid["name"], is_iapws=True, calc_temp_c=T_hot_mid)
                    elif hot_data_mid["is_coolprop"]:
                        _hf = Fluid(name=hot_data_mid["name"], is_coolprop=True, calc_temp_c=T_hot_mid)
                    else:
                        _hf = build_manual_fluid(
                            hot_data_mid,
                            hot_data_mid.get("cp", cp_hot),
                            hot_data_mid.get("density", density_hot),
                            hot_data_mid.get("mu", mu_hot),
                            hot_data_mid.get("k_cond", k_hot),
                        )
                    if cold_data_mid.get("is_iapws"):
                        _cf = Fluid(name=cold_data_mid["name"], is_iapws=True, calc_temp_c=T_cold_mid)
                    elif cold_data_mid["is_coolprop"]:
                        _cf = Fluid(name=cold_data_mid["name"], is_coolprop=True, calc_temp_c=T_cold_mid)
                    else:
                        _cf = build_manual_fluid(
                            cold_data_mid,
                            cold_data_mid.get("cp", cp_cold),
                            cold_data_mid.get("density", density_cold),
                            cold_data_mid.get("mu", mu_cold),
                            cold_data_mid.get("k_cond", k_cold),
                        )
                    _m_hot = to_kg_s(m_hot_raw, u_m_hot, _hf.density)
                    _m_cold = to_kg_s(m_cold_raw, u_m_cold, _cf.density)
                    _hx = FinTubeHeatExchanger(
                        _hf, _cf, U=1.0, A=1.0,
                        flow_type=FLOW_MAP[flow_type],
                        exchanger_type=exch_type_internal,
                    )
                    _hx.pump_efficiency = float(pump_eff)
                    _hx.fan_efficiency = float(fan_eff)
                    if u_calc_mode == U_MODE_OPTIONS[1]:
                        holder["geo_res"] = _hx.calculate_geometric_U(geom_dict, _m_hot, _m_cold, hot_is_tube)
                        _hx.U = holder["geo_res"]["U"]
                        _hx.A = holder["geo_res"]["A_total"]
                    else:
                        _hx.U = U_value
                        _hx.A = Area
                    return _m_hot, _m_cold, _hx

                m_hot, m_cold, hx, crosscheck_results = hx.solve_with_refinement(
                    m_hot, m_cold, T_hot_in, T_cold_in, _rebuild
                )
                res_custom, res_custom_lmtd, res_ht, res_lmtd = crosscheck_results
                geo_res = holder["geo_res"]
                U_value = hx.U
                Area = hx.A

            pychemengg_warning = None
            try:
                crosscheck_results.append(hx.solve_segmented(m_hot, m_cold, T_hot_in, T_cold_in, n_segments=10))
            except Exception as exc:
                root_logger.warning("Segmentli çözücü cross-check hatası: %s", exc)

            try:
                crosscheck_results.append(hx.solve_pychemengg_ntu(m_hot, m_cold, T_hot_in, T_cold_in))
            except ImportError as exc:
                pychemengg_warning = str(exc)
            except Exception as exc:
                pychemengg_warning = f"PyChemEngg doğrulaması çalışmadı: {exc}"
        except Exception as exc:
            root_logger.exception("Calculation engine failed.")
            st.error(f"Hesaplama motoru hatası: {exc}")
            st.caption(f"Detaylı log dosyası: {LOG_FILE}")
            st.stop()

        res_main = res_custom
        if not (is_condenser or is_evaporator):
            if solver_method == SOLVER_OPTIONS[1]:
                res_main = res_custom_lmtd
            elif solver_method == SOLVER_OPTIONS[2]:
                res_main = res_ht
            elif solver_method == SOLVER_OPTIONS[3]:
                res_main = res_lmtd

        has_actual = T_hot_out_opt > -900.0 and T_cold_out_opt > -900.0
        res_actual = None
        if has_actual:
            res_actual = hx.calculate_actual_performance(
                m_hot, m_cold, T_hot_in, T_cold_in, T_hot_out_opt, T_cold_out_opt
            )

        if geo_res:
            geom_dict.setdefault("v_cross", geo_res.get("v_cross", 0.0))
            geom_dict.setdefault("rho_shell", geo_res.get("rho_shell", 0.0))
            geom_dict.setdefault("rho_tube", geo_res.get("rho_tube", 0.0))

        report_context = {
            "methods": {
                "Hesap amacı": calc_purpose,
                "Akış tipi": flow_type,
                "Akış tipi internal": FLOW_MAP[flow_type],
                "Ana çözücü": solver_method,
                "U modu": u_calc_mode,
            },
            "inputs": {
                "m_hot_raw": f"{m_hot_raw} {u_m_hot}",
                "m_cold_raw": f"{m_cold_raw} {u_m_cold}",
                "m_hot_kg_s": m_hot,
                "m_cold_kg_s": m_cold,
                "T_hot_in_C": T_hot_in,
                "T_cold_in_C": T_cold_in,
                "T_hot_out_C": T_hot_out_opt if has_actual else None,
                "T_cold_out_C": T_cold_out_opt if has_actual else None,
                "U": U_value,
                "A": Area,
            },
            "fluids": {
                "hot": fluid_report_data(hot_fluid_sel, hot_data, hot_fluid_obj),
                "cold": fluid_report_data(cold_fluid_sel, cold_data, cold_fluid_obj),
            },
            "geometry": geom_dict,
            "geo_result": geo_res,
            "orc_data": current_data,
            "results": {"main": res_main},
            "actual_result": res_actual,
            "crosscheck_results": crosscheck_results,
        }
        report_text = build_calculation_report(report_context)

        calc_cache = {
            "hx_data": {
                "hot_name": hx.hot_fluid.name,
                "cold_name": hx.cold_fluid.name,
                "U": hx.U,
                "A": hx.A,
                "flow_type": hx.flow_type,
                "exchanger_type": hx.exchanger_type,
            },
            "geo_res": geo_res,
            "res_main": res_main,
            "res_actual": res_actual,
            "crosscheck_results": crosscheck_results,
            "pychemengg_warning": pychemengg_warning,
            "has_actual": has_actual,
            "report_context": report_context,
            "report_text": report_text,
            "log_text": log_stream.getvalue(),
            "U_value": U_value,
            "Area": Area,
            "u_t_hot": u_t_hot,
            "u_t_cold": u_t_cold,
        }
        st.session_state.calc_cache = calc_cache
    finally:
        root_logger.removeHandler(handler)
        handler.close()

    st.rerun()

if "calc_cache" in st.session_state and not hata_var:
    _render_calc_results(st.session_state.calc_cache, tab_results, tab_crosscheck, tab_log)
else:
    with tab_results:
        st.markdown("### 📊 Hesaplama Çıktıları ve Özet")
        st.info(
            "ℹ️ Henüz hesaplama çalıştırılmadı. Girdilerinizi belirledikten sonra alt paneldeki **'🚀 HESAPLA'** "
            "butonuna basarak ısı yükü (Q), sıcaklık profili, U katsayısı ve 1D sayısal dilimli (finite-volume) dağılımı görüntüleyebilirsiniz."
        )
    with tab_crosscheck:
        st.markdown("### 🔍 Çözücü Algoritmaları Çapraz Doğrulama (Cross-Check)")
        st.info(
            "ℹ️ Farklı çözücü yöntemlerinin (Epsilon-NTU, LMTD, HT ve Sayısal Dilimli Çözücü) sonuç karşılaştırma tablosunu "
            "görüntülemek için önce bir hesaplama başlatın."
        )
    with tab_log:
        st.markdown("### 📝 Sistem Logları")
        st.info("ℹ️ Termodinamik ve hidrolik çözücülerin ayrıntılı yürütme logları hesaplama başlatıldığında burada listelenecektir.")
