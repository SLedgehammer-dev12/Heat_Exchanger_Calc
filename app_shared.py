"""Shared UI components, preset definitions, and mappings for desktop and web applications."""

from typing import Any

# Akış tipi etiket eşleştirmeleri
FLOW_LABEL_TO_INTERNAL: dict[str, str] = {
    "Çapraz Akış (Cross Flow Unmixed)": "cross_unmixed",
    "Ters Akış (Counter Flow)": "counter",
    "Paralel Akış (Parallel Flow)": "parallel",
    "Çapraz Akış (Mixed/Unmixed)": "cross_mixed_unmixed",
}
FLOW_INTERNAL_TO_LABEL: dict[str, str] = {
    value: key for key, value in FLOW_LABEL_TO_INTERNAL.items()
}

# Eşanjör tipi etiket eşleştirmeleri
EXCHANGER_LABEL_TO_INTERNAL: dict[str, str] = {
    "Kanatçıklı Boru (Finned Tube)": "finned_tube",
    "Gövde-Boru (Shell & Tube)": "shell_and_tube",
    "Çift Borulu (Double Pipe)": "double_pipe",
}
EXCHANGER_INTERNAL_TO_LABEL: dict[str, str] = {
    value: key for key, value in EXCHANGER_LABEL_TO_INTERNAL.items()
}

# Gaz karışım hazır şablonları (bileşen yüzdeleri)
MIXTURE_PRESETS: dict[str, dict[str, float]] = {
    "Doğal Gaz": {
        "Nitrogen": 76.0,
        "Oxygen": 11.0,
        "Water": 6.0,
        "CarbonDioxide": 7.0,
    },
    "Kömür": {
        "Nitrogen": 72.0,
        "Oxygen": 6.0,
        "Water": 6.0,
        "CarbonDioxide": 15.0,
        "SulfurDioxide": 1.0,
    },
    "Biyogaz": {
        "Nitrogen": 65.0,
        "Oxygen": 5.0,
        "Water": 15.0,
        "CarbonDioxide": 15.0,
    },
}

# Snapshot / Durum yükleme alanı takma adları
LOAD_KEY_ALIASES: dict[str, str] = {
    "calc_purpose": "purpose",
    "u_calc_mode": "u_mode",
    "hot_fluid_sel": "hot_fluid",
    "cold_fluid_sel": "cold_fluid",
    "T_hot_in": "t_hot_in",
    "T_cold_in": "t_cold_in",
    "T_hot_out_opt": "t_hot_out_opt",
    "T_cold_out_opt": "t_cold_out_opt",
    "U_value": "U",
    "Area": "A",
    "D_o_mm": "Do",
    "D_i_mm": "Di",
    "L_m": "L",
    "N_tubes": "Nt",
    "hot_is_tube": "hot_tube",
    "tube_material": "tube_mat",
    "fin_material": "fin_mat",
    "fin_h_mm": "fin_h",
    "fin_t_mm": "fin_t",
    "fin_density": "fin_dens",
}


def safe_index(options: list[Any], value: Any, default: int = 0) -> int:
    """Güvenli liste indeksi bulma; eşleşme yoksa varsayılan indeksi döndürür."""
    try:
        return options.index(value)
    except (ValueError, KeyError, IndexError):
        return default
