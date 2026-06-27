import io
import json
import logging
from typing import Any

import pandas as pd
import streamlit as st

from engineering_utils import (
    fluid_report_data,
    from_celsius,
    to_celsius,
    to_kg_s,
)
from logging_config import setup_logging

LOG_FILE = setup_logging("web")
logger = logging.getLogger(__name__)


from config import EXCHANGER_ALLOWED_FLOWS, EXCHANGER_TYPES
from fluids_db import get_fluid_data, get_fluid_list_flat, get_mixture_fluid_data, materialize_fluid_data
from heat_exchanger import FinTubeHeatExchanger, Fluid
from reporting import build_calculation_report, build_calculation_report_pdf
from updater import check_for_update, default_download_dir, download_release_asset
from version import APP_NAME, VERSION

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
}


def safe_index(options, value, default=0):
    return options.index(value) if value in options else default


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


def get_val(key):
    return st.session_state.get(key, DEFAULT_STATE.get(key))


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
MIXTURE_PRESETS = {
    "Doğal Gaz": {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0},
    "Kömür": {"Nitrogen": 72.0, "Oxygen": 6.0, "Water": 6.0, "CarbonDioxide": 15.0, "SulfurDioxide": 1.0},
    "Biyogaz": {"Nitrogen": 65.0, "Oxygen": 5.0, "Water": 15.0, "CarbonDioxide": 15.0},
}


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
    has_actual = data.get("has_actual", False)
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
        st.success("Hesaplamalar tamamlandı")
        if geo_res:
            st.info(f"Geometrik Mod Sonucu: U = {U_value:.2f} W/m²K, Toplam Alan = {Area:.2f} m²")
            for msg in geo_res.get("warnings", []):
                st.warning(msg)
            c_u1, c_u2, c_u3 = st.columns(3)
            c_u1.metric("İç Taşınım Katsayısı (h_i)", f"{geo_res['h_i']:.1f} W/m²K")
            c_u2.metric("Dış Taşınım Katsayısı (h_o)", f"{geo_res['h_o']:.1f} W/m²K")
            c_u3.metric("Kanatçık Verimi", f"% {geo_res.get('eta_fin', 1.0) * 100:.1f}")

        if has_actual and res_actual:
            st.markdown("### Performans Değerlendirmesi")
            for msg in res_actual.get("warnings", []):
                st.warning(msg)
            c_a1, c_a2, c_a3 = st.columns(3)
            c_a1.metric("Sıcak Taraftan Atılan Isı", f"{res_actual['Q_hot [W]'] / 1000:.2f} kW")
            c_a2.metric("Soğuk Tarafa Alınan Isı", f"{res_actual['Q_cold [W]'] / 1000:.2f} kW")
            enerji_farki = (
                abs(res_actual["Q_hot [W]"] - res_actual["Q_cold [W]"]) / max(abs(res_actual["Q_hot [W]"]), 1.0) * 100.0
            )
            c_a3.metric("Enerji Dengesi Sapması", f"% {enerji_farki:.2f}")
            st.info(f"Gerçekleşen Effectiveness: %{res_actual['epsilon_actual'] * 100:.2f}")
            st.warning(f"Gereken U Katsayısı: {res_actual['U_required']:.2f} W/m²K")
        else:
            st.markdown("### Sistem Tasarımı")
            for msg in res_main.get("warnings", []):
                st.warning(msg)
            t_ho_disp = from_celsius(res_main["T_hot_out [C]"], u_t_hot)
            t_co_disp = from_celsius(res_main["T_cold_out [C]"], u_t_cold)
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Tasarım Isı Yükü", f"{res_main['Q [W]'] / 1000:.2f} kW")
            col_m2.metric("Sıcak Çıkış", f"{t_ho_disp:.2f} {u_t_hot}")
            col_m3.metric("Soğuk Çıkış", f"{t_co_disp:.2f} {u_t_cold}")
            st.info(f"Effectiveness: %{res_main.get('epsilon', 0.0) * 100:.2f}")

        st.markdown("### Isı Değiştirici Akış Şeması")
        st.pyplot(_hx.plot_enhanced_schematic(result=res_main))
        st.markdown("### Sıcaklık Profili")
        st.pyplot(_hx.plot_temperature_profile(res_main))

        st.download_button(
            "Sonuç Raporunu İndir (.txt)",
            report_text,
            file_name="isi_degistirici_raporu.txt",
        )
        st.download_button(
            "Sonuç Raporunu İndir (.pdf)",
            build_calculation_report_pdf(report_context),
            file_name="isi_degistirici_raporu.pdf",
            mime="application/pdf",
        )

    with tab_crosscheck:
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
    .stApp { background-color: #f8fafc; }
    .stPlotlyChart, .stImage, .stTable, .stDataFrame {
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        background: white;
        padding: 8px;
        margin-bottom: 16px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background-color: #1a5276; color: white; }
    .stMetric { background: white; border-radius: 10px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
    .stAlert { border-radius: 10px; }
    .stSidebar .stSelectbox, .stSidebar .stRadio, .stSidebar .stTextInput { margin-bottom: 8px; }
</style>
""",
    unsafe_allow_html=True,
)

st.title(f"🌡️ {APP_NAME}")
st.markdown("Modern ısı değiştirici termodinamik ve geometrik analiz aracı")

fluid_list = get_fluid_list_flat()

st.sidebar.header("Veri Yönetimi")
uploaded_file = st.sidebar.file_uploader("Kayıtlı verileri yükle (.json)", type=["json"])
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
        st.sidebar.error(f"Dosya yüklenemedi: {exc}")

st.sidebar.header("Sürüm ve Güncelleme")
st.sidebar.caption(f"Mevcut sürüm: v{VERSION}")
if "update_checked" not in st.session_state:
    st.session_state["update_checked"] = True
    st.session_state["update_result"] = check_for_update(timeout=3)
update_result = st.session_state.get("update_result")
if update_result and update_result.get("update_available"):
    st.sidebar.warning(update_result["message"])
    target_dir = st.sidebar.text_input(
        "İndirme klasörü",
        value=st.session_state.get("update_download_dir", default_download_dir()),
        key="update_download_dir",
    )
    if st.sidebar.button("Güncelleme Paketini İndir"):
        try:
            with st.sidebar.status("Güncelleme indiriliyor...", expanded=False):
                download_result = download_release_asset(update_result, target_dir, app_kind="web", timeout=120)
            st.sidebar.success(f"İndirildi: {download_result['path']}")
            logger.info("Update downloaded: %s (%s bytes)", download_result["path"], download_result["size"])
        except Exception as exc:
            logger.exception("Update download failed.")
            st.sidebar.error(f"Güncelleme indirilemedi: {exc}")
            st.sidebar.caption(f"Detaylı log dosyası: {LOG_FILE}")
elif update_result and not update_result.get("ok"):
    st.sidebar.info(update_result.get("message"))
if st.sidebar.button("Güncellemeyi Kontrol Et"):
    st.session_state["update_result"] = check_for_update(timeout=5)
    st.rerun()

st.sidebar.header("Genel Ayarlar")
calc_purpose = st.sidebar.radio(
    "Hesaplama Amacı",
    CALC_PURPOSE_OPTIONS,
    index=safe_index(CALC_PURPOSE_OPTIONS, get_val("calc_purpose")),
)
# Eşanjör tipi seçimi
exch_type_label = st.sidebar.selectbox(
    "Eşanjör Tipi",
    options=EXCH_TYPE_OPTIONS,
    index=safe_index(EXCH_TYPE_OPTIONS, get_val("exch_type")),
)
exch_type_internal = EXCH_TYPE_INTERNAL[exch_type_label]

# Akış tipini eşanjör tipine göre filtrele
allowed_flow_labels = _get_allowed_flow_labels(exch_type_internal)
flow_type = st.sidebar.selectbox(
    "Akış Konfigürasyonu",
    options=allowed_flow_labels,
    index=safe_index(allowed_flow_labels, get_val("flow_type")),
)
solver_method = st.sidebar.selectbox(
    "Ana Çözücü Algoritması",
    options=SOLVER_OPTIONS,
    index=safe_index(SOLVER_OPTIONS, get_val("solver_method")),
)
u_calc_mode = st.sidebar.radio(
    "U Katsayısı Belirleme Yöntemi",
    U_MODE_OPTIONS,
    index=safe_index(U_MODE_OPTIONS, get_val("u_calc_mode")),
)

tab_inputs, tab_geom, tab_results, tab_crosscheck, tab_log = st.tabs(
    ["Akışkan Girdileri", "Geometri ve Malzeme", "Sonuçlar", "Cross-Check", "📝 Sistem Logları"]
)

current_data = {
    "exch_type": exch_type_label,
    "calc_purpose": calc_purpose,
    "flow_type": flow_type,
    "solver_method": solver_method,
    "u_calc_mode": u_calc_mode,
}

with tab_inputs:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sıcak Akışkan")
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
        cp_hot = float(get_val("cp_hot") if get_val("cp_hot") is not None else hot_data.get("cp", 1100.0))
        density_hot = float(
            get_val("density_hot") if get_val("density_hot") is not None else hot_data.get("density", 0.5)
        )
        mu_hot = float(get_val("mu_hot") if get_val("mu_hot") is not None else 2e-5)
        k_hot = float(get_val("k_hot") if get_val("k_hot") is not None else 0.03)

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

        current_data.update(
            {
                "hot_fluid_sel": hot_fluid_sel,
                "m_hot": m_hot,
                "T_hot_in": T_hot_in,
                "T_hot_out_opt": T_hot_out_opt,
                "cp_hot": cp_hot,
                "density_hot": density_hot,
                "mu_hot": mu_hot,
                "k_hot": k_hot,
                "hot_mix_data": st.session_state.get("hot_mix_data", DEFAULT_STATE["hot_mix_data"]),
                "hot_mix_basis": st.session_state.get("hot_mix_basis", DEFAULT_STATE["hot_mix_basis"]),
            }
        )

    with col2:
        st.subheader("Soğuk Akışkan")
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
        cp_cold = float(get_val("cp_cold") if get_val("cp_cold") is not None else cold_data.get("cp", 2000.0))
        density_cold = float(
            get_val("density_cold") if get_val("density_cold") is not None else cold_data.get("density", 850.0)
        )
        mu_cold = float(get_val("mu_cold") if get_val("mu_cold") is not None else 0.001)
        k_cold = float(get_val("k_cold") if get_val("k_cold") is not None else 0.15)

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

        current_data.update(
            {
                "cold_fluid_sel": cold_fluid_sel,
                "m_cold": m_cold,
                "T_cold_in": T_cold_in,
                "T_cold_out_opt": T_cold_out_opt,
                "cp_cold": cp_cold,
                "density_cold": density_cold,
                "mu_cold": mu_cold,
                "k_cold": k_cold,
                "cold_mix_data": st.session_state.get("cold_mix_data", DEFAULT_STATE["cold_mix_data"]),
                "cold_mix_basis": st.session_state.get("cold_mix_basis", DEFAULT_STATE["cold_mix_basis"]),
            }
        )

with tab_geom:
    st.subheader("Isı Değiştirici Özellikleri")

    geom_dict: dict[str, Any] = {}
    hot_is_tube = False

    if u_calc_mode == U_MODE_OPTIONS[0]:
        st.info("Basit modda U katsayısı doğrudan kullanıcıdan alınır.")
        U_value = st.number_input(
            "Toplam Isı Transfer Katsayısı - U (W/m²K)",
            min_value=0.1,
            value=float(get_val("U_value")),
            step=1.0,
        )
        Area = st.number_input(
            "Toplam Isı Transfer Alanı - A (m²)",
            min_value=0.1,
            value=float(get_val("Area")),
            step=1.0,
        )
        current_data["U_value"] = U_value
        current_data["Area"] = Area
    else:
        st.success("Geometrik mod aktif. U katsayısı arka planda hesaplanacaktır.")
        g1, g2, g3 = st.columns(3)

        with g1:
            D_o_mm = st.number_input("Dış Çap - Do (mm)", value=float(get_val("D_o_mm")))
            D_i_mm = st.number_input("İç Çap - Di (mm)", value=float(get_val("D_i_mm")))
            L_m = st.number_input("Boru Uzunluğu - L (m)", value=float(get_val("L_m")))
            N_tubes = st.number_input("Boru Sayısı", value=int(get_val("N_tubes")), step=1)

            geom_dict["D_o"] = D_o_mm / 1000.0
            geom_dict["D_i"] = D_i_mm / 1000.0
            geom_dict["L"] = L_m
            geom_dict["N_tubes"] = N_tubes

            current_data.update({"D_o_mm": D_o_mm, "D_i_mm": D_i_mm, "L_m": L_m, "N_tubes": N_tubes})

        with g2:
            mat_options = {
                "Karbon Çelik (k=45)": 45.0,
                "Paslanmaz Çelik 316 (k=16)": 16.0,
                "Bakır (k=400)": 400.0,
                "Alüminyum (k=237)": 237.0,
            }
            tube_material = st.selectbox(
                "Boru Malzemesi",
                options=list(mat_options.keys()),
                index=safe_index(list(mat_options.keys()), get_val("tube_material")),
            )
            geom_dict["k_wall"] = mat_options[tube_material]
            current_data["tube_material"] = tube_material

            if FLOW_MAP[flow_type].startswith("cross"):
                pitch_mm = st.number_input("Transverse Pitch (mm)", value=float(get_val("pitch_mm")))
                geom_dict["pitch"] = pitch_mm / 1000.0
                current_data["pitch_mm"] = pitch_mm
            else:
                D_shell_mm = st.number_input("Gövde İç Çapı (mm)", value=float(get_val("D_shell_mm")))
                geom_dict["D_shell"] = D_shell_mm / 1000.0
                current_data["D_shell_mm"] = D_shell_mm

            hot_is_tube_str = st.radio(
                "İç Boruda Hangi Akışkan Var?",
                ["Soğuk Akışkan", "Sıcak Akışkan"],
                index=safe_index(["Soğuk Akışkan", "Sıcak Akışkan"], get_val("hot_is_tube")),
            )
            hot_is_tube = hot_is_tube_str == "Sıcak Akışkan"
            current_data["hot_is_tube"] = hot_is_tube_str

            R_f_i = st.number_input("Fouling İç (m2K/W)", value=float(get_val("R_f_i") or 0.0), format="%.6f")
            R_f_o = st.number_input("Fouling Dış (m2K/W)", value=float(get_val("R_f_o") or 0.0), format="%.6f")
            geom_dict["R_f_i"] = R_f_i
            geom_dict["R_f_o"] = R_f_o
            current_data["R_f_i"] = R_f_i
            current_data["R_f_o"] = R_f_o

        with g3:
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
                    "Kanat??k Tipi",
                    options=["Dairesel (Annular)", "Düz (Rectangular)"],
                    index=safe_index(
                        ["Dairesel (Annular)", "Düz (Rectangular)"], get_val("fin_type") or "Dairesel (Annular)"
                    ),
                )
                geom_dict["k_fin"] = 237.0 if "Alüminyum" in fin_material else 45.0
                geom_dict["fin_type"] = "rectangular" if "Rectangular" in fin_type else "annular"

                current_data.update(
                    {
                        "fin_h_mm": fin_h_mm,
                        "fin_t_mm": fin_t_mm,
                        "fin_density": fin_density,
                        "fin_material": fin_material,
                        "fin_type": fin_type,
                    }
                )

        U_value = 0.0
        Area = 0.0

st.sidebar.download_button(
    label="Mevcut Girdileri Kaydet",
    data=save_state(current_data),
    file_name="heat_exchanger_save.json",
    mime="application/json",
)

hata_var = False
if T_hot_in <= T_cold_in:
    st.error("❌ Mantıksal Hata: Sıcak akışkan giriş sıcaklığı, soğuk akışkan giriş sıcaklığından büyük olmalıdır.")
    hata_var = True
if m_hot_raw <= 0 or m_cold_raw <= 0:
    st.error("❌ Mantıksal Hata: Debi değerleri sıfırdan büyük olmalıdır.")
    hata_var = True
if calc_purpose == CALC_PURPOSE_OPTIONS[1]:
    if T_hot_out_opt > T_hot_in:
        st.error("❌ Mantıksal Hata: Sıcak akışkanın çıkışı, girişinden büyük olamaz.")
        hata_var = True
    if T_cold_out_opt < T_cold_in:
        st.error("❌ Mantıksal Hata: Soğuk akışkanın çıkışı, girişinden küçük olamaz.")
        hata_var = True

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

if not hata_var and st.button("HESAPLA", use_container_width=True, type="primary"):
    # --- Logging Setup for this Run ---
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for h in root_logger.handlers[:]:
        if getattr(h, "_streamlit_run_handler", False):
            root_logger.removeHandler(h)
    handler._streamlit_run_handler = True  # type: ignore[attr-defined]
    root_logger.addHandler(handler)

    with st.spinner("Termodinamik ve ısı transferi denklemleri çözülüyor..."):
        root_logger.info("Hesaplama başlatıldı.")
        hx = FinTubeHeatExchanger(
            hot_fluid_obj,  # type: ignore[arg-type]
            cold_fluid_obj,  # type: ignore[arg-type]
            U=1.0,
            A=1.0,
            flow_type=FLOW_MAP[flow_type],
            exchanger_type=exch_type_internal,
        )

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
            res_custom = hx.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="custom")
            res_custom_lmtd = hx.solve_custom_lmtd(m_hot, m_cold, T_hot_in, T_cold_in)
            res_ht = hx.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="ht")
            res_lmtd = hx.solve_lmtd(m_hot, m_cold, T_hot_in, T_cold_in, source="ht")
            crosscheck_results = [res_custom, res_custom_lmtd, res_ht, res_lmtd]

            for _iter in range(2):
                t_ho = res_custom["T_hot_out [C]"]
                t_co = res_custom["T_cold_out [C]"]
                T_hot_mid = (T_hot_in + t_ho) / 2.0
                T_cold_mid = (T_cold_in + t_co) / 2.0
                if abs(T_hot_mid - T_hot_in) < 1.0 and abs(T_cold_mid - T_cold_in) < 1.0:
                    break

                hot_data_mid = materialize_fluid_data(get_fluid_data(hot_fluid_sel), T_hot_mid)
                cold_data_mid = materialize_fluid_data(get_fluid_data(cold_fluid_sel), T_cold_mid)
                if hot_data_mid.get("is_iapws"):
                    hot_fluid_obj = Fluid(name=hot_data_mid["name"], is_iapws=True, calc_temp_c=T_hot_mid)
                elif hot_data_mid["is_coolprop"]:
                    hot_fluid_obj = Fluid(name=hot_data_mid["name"], is_coolprop=True, calc_temp_c=T_hot_mid)
                else:
                    hot_fluid_obj = build_manual_fluid(hot_data_mid, cp_hot, density_hot, mu_hot, k_hot)
                if cold_data_mid.get("is_iapws"):
                    cold_fluid_obj = Fluid(name=cold_data_mid["name"], is_iapws=True, calc_temp_c=T_cold_mid)
                elif cold_data_mid["is_coolprop"]:
                    cold_fluid_obj = Fluid(name=cold_data_mid["name"], is_coolprop=True, calc_temp_c=T_cold_mid)
                else:
                    cold_fluid_obj = build_manual_fluid(cold_data_mid, cp_cold, density_cold, mu_cold, k_cold)

                m_hot = to_kg_s(m_hot_raw, u_m_hot, hot_fluid_obj.density)
                m_cold = to_kg_s(m_cold_raw, u_m_cold, cold_fluid_obj.density)
                hx = FinTubeHeatExchanger(
                    hot_fluid_obj,  # type: ignore[arg-type]
                    cold_fluid_obj,  # type: ignore[arg-type]
                    U=1.0,
                    A=1.0,
                    flow_type=FLOW_MAP[flow_type],
                    exchanger_type=exch_type_internal,
                )
                if u_calc_mode == U_MODE_OPTIONS[1]:
                    geo_res = hx.calculate_geometric_U(geom_dict, m_hot, m_cold, hot_is_tube)
                    U_value = geo_res["U"]
                    Area = geo_res["A_total"]
                else:
                    hx.U = U_value
                    hx.A = Area
                res_custom = hx.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="custom")
                res_custom_lmtd = hx.solve_custom_lmtd(m_hot, m_cold, T_hot_in, T_cold_in)
                res_ht = hx.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="ht")
                res_lmtd = hx.solve_lmtd(m_hot, m_cold, T_hot_in, T_cold_in, source="ht")
                crosscheck_results = [res_custom, res_custom_lmtd, res_ht, res_lmtd]

            pychemengg_warning = None
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
        st.rerun()

if "calc_cache" in st.session_state and not hata_var:
    _render_calc_results(st.session_state.calc_cache, tab_results, tab_crosscheck, tab_log)
