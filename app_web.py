import json

import pandas as pd
import streamlit as st
import logging
import io

def to_kg_s(val, unit, density):
    if unit == "kg/h": return val / 3600.0
    if unit == "lb/s": return val * 0.453592
    if unit == "m³/s": return val * density
    if unit == "m³/h": return (val / 3600.0) * density
    if unit == "CFM": return (val * 0.000471947) * density
    return val

def to_celsius(val, unit):
    if unit == "°F": return (val - 32.0) * 5.0 / 9.0
    if unit == "K": return val - 273.15
    return val

def from_celsius(val, unit):
    if unit == "°F": return (val * 9.0 / 5.0) + 32.0
    if unit == "K": return val + 273.15
    return val


from fluids_db import get_fluid_data, get_fluid_list_flat, get_mixture_fluid_data, materialize_fluid_data
from heat_exchanger import FinTubeHeatExchanger, Fluid
from reporting import build_calculation_report
from updater import check_for_update
from version import APP_NAME, VERSION

FLOW_OPTIONS = [
    "Çapraz Akış (Cross Flow Unmixed)",
    "Ters Akış (Counter Flow)",
    "Paralel Akış (Parallel Flow)",
]
FLOW_MAP = {
    "Çapraz Akış (Cross Flow Unmixed)": "cross_unmixed",
    "Ters Akış (Counter Flow)": "counter",
    "Paralel Akış (Parallel Flow)": "parallel",
}
FLOW_MAP_REVERSE = {value: key for key, value in FLOW_MAP.items()}

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
    "cold_fluid_sel": "Therminol 66",
    "m_cold": 5.0,
    "T_cold_in": 120.0,
    "T_cold_out_opt": -999.0,
    "cp_cold": 2000.0,
    "density_cold": 850.0,
    "mu_cold": 0.001,
    "k_cold": 0.15,
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


def save_state(current_data):
    return json.dumps(current_data, indent=4, ensure_ascii=False)


def result_warnings(*results):
    warnings = []
    for result in results:
        if not result:
            continue
        for msg in result.get("warnings", []):
            if msg not in warnings:
                warnings.append(msg)
    return warnings


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


def fluid_report_data(label, fluid_data, fluid_obj):
    return {
        "label": label,
        "name": fluid_obj.name,
        "source": fluid_data.get("property_source") or getattr(fluid_obj, "property_source", None) or ("CoolProp" if fluid_obj.is_coolprop else "Manual/Correlation"),
        "cp": fluid_obj.cp,
        "density": fluid_obj.density,
        "mu": fluid_obj.mu,
        "k_cond": fluid_obj.k_cond,
    }


st.set_page_config(page_title=APP_NAME, page_icon="🌡️", layout="wide")

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
        st.sidebar.error(f"Dosya yüklenemedi: {exc}")

st.sidebar.header("Sürüm ve Güncelleme")
st.sidebar.caption(f"Mevcut sürüm: v{VERSION}")
if "update_checked" not in st.session_state:
    st.session_state["update_checked"] = True
    st.session_state["update_result"] = check_for_update(timeout=3)
update_result = st.session_state.get("update_result")
if update_result and update_result.get("update_available"):
    st.sidebar.warning(update_result["message"])
    st.sidebar.link_button("Release sayfasını aç", update_result.get("release_url"))
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
flow_type = st.sidebar.selectbox(
    "Akış Konfigürasyonu",
    options=FLOW_OPTIONS,
    index=safe_index(FLOW_OPTIONS, get_val("flow_type")),
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
            T_hot_out_opt_raw = col_to_val.number_input("Sıcak Çıkış", value=float(get_val("T_hot_out_opt") if get_val("T_hot_out_opt") != -999.0 else 200.0), step=1.0)
            u_t_hot_out = col_to_u.selectbox("Birim", ["°C", "°F", "K"], key="u_t_hot_out")
            T_hot_out_opt = to_celsius(T_hot_out_opt_raw, u_t_hot_out)
        else:
            T_hot_out_opt = -999.0
            
        T_hot_in = to_celsius(T_hot_in_raw, u_t_hot)
        m_hot = m_hot_raw # We will convert to kg/s later when density is known

        hot_data = materialize_fluid_data(get_fluid_data(hot_fluid_sel), T_hot_in)
        for msg in hot_data.get("warnings", []):
            st.warning(msg)
        cp_hot = float(get_val("cp_hot") if get_val("cp_hot") is not None else hot_data.get("cp", 1100.0))
        density_hot = float(
            get_val("density_hot") if get_val("density_hot") is not None else hot_data.get("density", 0.5)
        )
        mu_hot = float(get_val("mu_hot") if get_val("mu_hot") is not None else 2e-5)
        k_hot = float(get_val("k_hot") if get_val("k_hot") is not None else 0.03)

        if hot_data.get("is_mixture"):
            with st.expander("🔧 Kompozisyon Ayarları", expanded=True):
                c1, c2, c3 = st.columns(3)
                if c1.button("Doğal Gaz"):
                    st.session_state["hot_mix"] = {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0}
                if c2.button("Kömür"):
                    st.session_state["hot_mix"] = {"Nitrogen": 72.0, "Oxygen": 6.0, "Water": 6.0, "CarbonDioxide": 15.0, "SulfurDioxide": 1.0}
                if c3.button("Biyogaz"):
                    st.session_state["hot_mix"] = {"Nitrogen": 65.0, "Oxygen": 5.0, "Water": 15.0, "CarbonDioxide": 15.0}
                    
                if "hot_mix" not in st.session_state:
                    st.session_state["hot_mix"] = {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0}
                
                df_mix = pd.DataFrame(list(st.session_state["hot_mix"].items()), columns=["Bileşen", "Molar Yüzde (%)"])
                edited_df = st.data_editor(df_mix, num_rows="dynamic", column_config={"Bileşen": st.column_config.SelectboxColumn(options=["Nitrogen", "Oxygen", "CarbonDioxide", "Water", "Argon", "CarbonMonoxide", "Methane", "Hydrogen", "SulfurDioxide"])})
                
                new_mix = {}
                for _, row in edited_df.iterrows():
                    if pd.notna(row["Bileşen"]) and pd.notna(row["Molar Yüzde (%)"]):
                        gas = str(row["Bileşen"])
                        val = float(row["Molar Yüzde (%)"])
                        new_mix[gas] = new_mix.get(gas, 0.0) + val
                st.session_state["hot_mix"] = new_mix
                
                hot_mix_data = get_mixture_fluid_data(new_mix, comp_type="mole", T_c=T_hot_in, P_pa=101325.0)
                cp_hot = hot_mix_data["cp"]
                density_hot = hot_mix_data["density"]
                mu_hot = hot_mix_data["mu"]
                k_hot = hot_mix_data["k_cond"]
                st.success(f"Hesaplanan Karışım Özellikleri: Cp={cp_hot:.1f} J/kgK, Rho={density_hot:.3f} kg/m3")

        elif not hot_data["is_coolprop"]:
            st.warning("Bu akışkanın özellikleri manuel girilmelidir")
            cp_hot = st.number_input("Hot Cp (J/kg.K)", value=cp_hot)
            density_hot = st.number_input("Hot Density (kg/m³)", min_value=0.001, value=density_hot, format="%.3f")
            if u_calc_mode == U_MODE_OPTIONS[1]:
                mu_hot = st.number_input("Hot Dynamic Viscosity (Pa.s)", value=mu_hot, format="%.6f")
                k_hot = st.number_input("Hot Thermal Conductivity (W/m.K)", value=k_hot, format="%.4f")

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
            T_cold_out_opt_raw = col_tco_val.number_input("Soğuk Çıkış", value=float(get_val("T_cold_out_opt") if get_val("T_cold_out_opt") != -999.0 else 200.0), step=1.0)
            u_t_cold_out = col_tco_u.selectbox("Birim", ["°C", "°F", "K"], key="u_t_cold_out")
            T_cold_out_opt = to_celsius(T_cold_out_opt_raw, u_t_cold_out)
        else:
            T_cold_out_opt = -999.0
            
        T_cold_in = to_celsius(T_cold_in_raw, u_t_cold)
        m_cold = m_cold_raw # Will convert later

        cold_data = materialize_fluid_data(get_fluid_data(cold_fluid_sel), T_cold_in)
        for msg in cold_data.get("warnings", []):
            st.warning(msg)
        cp_cold = float(get_val("cp_cold") if get_val("cp_cold") is not None else cold_data.get("cp", 2000.0))
        density_cold = float(
            get_val("density_cold") if get_val("density_cold") is not None else cold_data.get("density", 850.0)
        )
        mu_cold = float(get_val("mu_cold") if get_val("mu_cold") is not None else 0.001)
        k_cold = float(get_val("k_cold") if get_val("k_cold") is not None else 0.15)

        if not cold_data["is_coolprop"]:
            st.warning("Bu akışkanın özellikleri manuel girilmelidir")
            cp_cold = st.number_input("Cold Cp (J/kg.K)", value=cp_cold)
            density_cold = st.number_input(
                "Cold Density (kg/m³)", min_value=0.001, value=density_cold, format="%.3f"
            )
            if u_calc_mode == U_MODE_OPTIONS[1]:
                mu_cold = st.number_input("Cold Dynamic Viscosity (Pa.s)", value=mu_cold, format="%.6f")
                k_cold = st.number_input("Cold Thermal Conductivity (W/m.K)", value=k_cold, format="%.4f")

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
            }
        )

with tab_geom:
    st.subheader("Isı Değiştirici Özellikleri")

    geom_dict = {}
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

            current_data.update(
                {"D_o_mm": D_o_mm, "D_i_mm": D_i_mm, "L_m": L_m, "N_tubes": N_tubes}
            )

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

            if flow_type == FLOW_OPTIONS[0]:
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

        with g3:
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
                geom_dict["k_fin"] = 237.0 if "Alüminyum" in fin_material else 45.0

                current_data.update(
                    {
                        "fin_h_mm": fin_h_mm,
                        "fin_t_mm": fin_t_mm,
                        "fin_density": fin_density,
                        "fin_material": fin_material,
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
        if hot_data["is_coolprop"]:
            hot_fluid_obj = Fluid(name=hot_data["name"], is_coolprop=True, calc_temp_c=T_hot_in)
        else:
            hot_fluid_obj = build_manual_fluid(hot_data, cp_hot, density_hot, mu_hot, k_hot)

        if cold_data["is_coolprop"]:
            cold_fluid_obj = Fluid(name=cold_data["name"], is_coolprop=True, calc_temp_c=T_cold_in)
        else:
            cold_fluid_obj = build_manual_fluid(cold_data, cp_cold, density_cold, mu_cold, k_cold)
            
        # 1. Şimdi yoğunlukları bildiğimize göre debileri kg/s'e çevirelim
        rho_h = hot_fluid_obj.density
        rho_c = cold_fluid_obj.density
        m_hot = to_kg_s(m_hot_raw, u_m_hot, rho_h)
        m_cold = to_kg_s(m_cold_raw, u_m_cold, rho_c)
        
    except Exception as exc:
        st.error(f"Akışkan özellikleri veya çevrim sırasında hata oluştu: {exc}")
        hata_var = True

if not hata_var and st.button("HESAPLA", use_container_width=True, type="primary"):
    
    # --- Logging Setup for this Run ---
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S'))
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    # Remove old handlers to prevent duplicate lines on rerun
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    # ----------------------------------

    with st.spinner("Termodinamik ve ısı transferi denklemleri çözülüyor..."):
        root_logger.info("Hesaplama başlatıldı.")
        hx = FinTubeHeatExchanger(
            hot_fluid_obj,
            cold_fluid_obj,
            U=1.0,
            A=1.0,
            flow_type=FLOW_MAP[flow_type],
        )

        geo_res = None
        if u_calc_mode == U_MODE_OPTIONS[1]:
            if geom_dict['D_i'] >= geom_dict['D_o']:
                st.error("❌ Mantıksal Hata: Dış Çap, İç Çaptan büyük olmalıdır!")
                st.stop()
            if geom_dict['L'] <= 0 or geom_dict['N_tubes'] < 1:
                st.error("❌ Mantıksal Hata: Boru boyu ve boru sayısı sıfırdan büyük olmalıdır!")
                st.stop()
            try:
                geo_res = hx.calculate_geometric_U(geom_dict, m_hot, m_cold, hot_is_tube)
                U_value = geo_res["U"]
                Area = geo_res["A_total"]
            except Exception as exc:
                st.error(f"Geometrik hesaplama hatası: {exc}")
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
            pychemengg_warning = None
            try:
                crosscheck_results.append(hx.solve_pychemengg_ntu(m_hot, m_cold, T_hot_in, T_cold_in))
            except ImportError as exc:
                pychemengg_warning = str(exc)
            except Exception as exc:
                pychemengg_warning = f"PyChemEngg doğrulaması çalışmadı: {exc}"
        except Exception as exc:
            st.error(f"Hesaplama motoru hatası: {exc}")
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

        with tab_results:
            st.success("Hesaplamalar tamamlandı")

            if geo_res:
                st.info(
                    f"Geometrik Mod Sonucu: U = {U_value:.2f} W/m²K, Toplam Alan = {Area:.2f} m²"
                )
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
                enerji_farki = abs(res_actual["Q_hot [W]"] - res_actual["Q_cold [W]"]) / max(
                    abs(res_actual["Q_hot [W]"]), 1.0
                ) * 100.0
                c_a3.metric("Enerji Dengesi Sapması", f"% {enerji_farki:.2f}")

                st.info(f"Gerçekleşen Effectiveness: %{res_actual['epsilon_actual'] * 100:.2f}")
                st.warning(f"Gereken U Katsayısı: {res_actual['U_required']:.2f} W/m²K")
            else:
                st.markdown("### Sistem Tasarımı")
                for msg in res_main.get("warnings", []):
                    st.warning(msg)
                
                # Çıkış sıcaklıklarını kullanıcı birimlerine çevir
                t_ho_disp = from_celsius(res_main['T_hot_out [C]'], u_t_hot)
                t_co_disp = from_celsius(res_main['T_cold_out [C]'], u_t_cold)
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Tasarım Isı Yükü", f"{res_main['Q [W]'] / 1000:.2f} kW")
                col_m2.metric("Sıcak Çıkış", f"{t_ho_disp:.2f} {u_t_hot}")
                col_m3.metric("Soğuk Çıkış", f"{t_co_disp:.2f} {u_t_cold}")
                st.info(f"Effectiveness: %{res_main.get('epsilon', 0.0) * 100:.2f}")

            st.markdown("### Isı Değiştirici Akış Şeması")
            st.pyplot(hx.plot_schematic())

            report_text = build_calculation_report({
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
            })

            st.download_button(
                "Sonuç Raporunu İndir (.txt)",
                report_text,
                file_name="isi_degistirici_raporu.txt",
            )

        with tab_crosscheck:
            if pychemengg_warning:
                st.info(pychemengg_warning)
            # Display Logs
            with tab_log:
                st.markdown("### Hesaplama Logları")
                
                # Get log text
                log_text = log_stream.getvalue()
                
                # We can't interactively filter easily without rerunning the calc, 
                # but we can provide a quick radio to show everything. 
                # Since streamlit clears variables, we just show raw DEBUG/INFO logs
                st.code(log_text, language="log")
                
            df = pd.DataFrame(
                [crosscheck_row(r, reference_q=res_main["Q [W]"]) for r in crosscheck_results]
            )
            st.table(df)
