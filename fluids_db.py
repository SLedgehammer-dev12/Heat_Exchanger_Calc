from __future__ import annotations

import json
import logging
import os

from exceptions import FluidPropertyError

# Kapsamlı Akışkan Veritabanı
# Arayüzlerde (Streamlit ve PyQt5) kullanıcıya seçtirilecek hazır akışkanların listesi.

FLUID_OPTIONS: dict = {
    "Gazlar (Gases)": {
        "Hava (Air)": {"name": "Air", "is_coolprop": True},
        "Doğal Gaz Türbin Egzoz Gazı (Manuel)": {
            "name": "Exhaust Gas Mixture",
            "is_coolprop": False,
            "is_mixture": True,
            "cp": 1100.0,
            "density": 0.5,
        },
        "Karbondioksit (CO2)": {"name": "CO2", "is_coolprop": True},
        "Metan (CH4)": {"name": "Methane", "is_coolprop": True},
        "Azot (N2)": {"name": "Nitrogen", "is_coolprop": True},
        "Oksijen (O2)": {"name": "Oxygen", "is_coolprop": True},
        "Argon": {"name": "Argon", "is_coolprop": True},
    },
    "Sıvılar (Liquids)": {
        "Su (Water)": {"name": "Water", "is_coolprop": True},
        "Su (IAPWS-IF97)": {"name": "Water", "is_coolprop": False, "is_iapws": True},
        "Amonyak (R717)": {"name": "Ammonia", "is_coolprop": True},
        "R134a (Soğutucu)": {"name": "R134a", "is_coolprop": True},
        "Propan (R290)": {"name": "Propane", "is_coolprop": True},
        "İzobütan (R600a)": {"name": "IsoButane", "is_coolprop": True},
    },
    "Isı Transfer Yağları (Thermal Oils)": {
        "Therminol 66": {"name": "INCOMP::T66", "is_coolprop": True},
        "Therminol 55": {"name": "INCOMP::T55", "is_coolprop": True},
        "Therminol VP-1": {"name": "INCOMP::TVP1", "is_coolprop": True},
        "Dowtherm A": {"name": "INCOMP::DowA", "is_coolprop": True},
        "Dowtherm J": {"name": "INCOMP::DowJ", "is_coolprop": True},
        "Dowtherm Q": {"name": "INCOMP::DowQ", "is_coolprop": True},
        "Paratherm NF": {"name": "INCOMP::PNF", "is_coolprop": True},
        "Syltherm 800": {"name": "INCOMP::S800", "is_coolprop": True},
        "Mobiltherm 605 (Manuel Yaklaşım)": {
            "name": "Mobiltherm 605",
            "is_coolprop": False,
            "cp": 2200.0,
            "density": 850.0,
        },
    },
    "Glikol ve Donma Önleyiciler (Glycols)": {
        "Etilen Glikol Karışımı (%50)": {"name": "INCOMP::MEG[0.5]", "is_coolprop": True},
        "Propilen Glikol Karışımı (%50)": {"name": "INCOMP::MPG[0.5]", "is_coolprop": True},
        "Etilen Glikol Karışımı (%30)": {"name": "INCOMP::MEG[0.3]", "is_coolprop": True},
    },
    "Özel (Custom)": {
        "Manuel Giriş (Özel Akışkan)": {"name": "Custom", "is_coolprop": False, "cp": 1000.0, "density": 1000.0},
        "Özel Egzoz Gazı (Kompozisyon)": {"name": "Mixture", "is_coolprop": False, "is_mixture": True},
    },
}
logger = logging.getLogger(__name__)

THERMO_NAME_MAP = {
    "Nitrogen": "nitrogen",
    "Oxygen": "oxygen",
    "CarbonDioxide": "carbon dioxide",
    "Water": "water",
    "Argon": "argon",
    "CarbonMonoxide": "carbon monoxide",
    "Methane": "methane",
    "Hydrogen": "hydrogen",
    "SulfurDioxide": "sulfur dioxide",
}


def load_external_fluids():
    local_path = os.path.join(os.path.dirname(__file__), "data", "thermal_oils.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, encoding="utf-8") as f:
                oils = json.load(f)

            for oil in oils:
                name = oil.get("display_name", oil.get("id"))
                logger.debug(f"Yüklenen yağ: {name}")
                FLUID_OPTIONS["Isı Transfer Yağları (Thermal Oils)"][name] = {
                    "name": oil.get("id"),
                    "is_coolprop": False,
                    "is_correlation": True,
                    "cp_a": oil.get("cp_a", 1500.0),
                    "cp_b": oil.get("cp_b", 2.0),
                    "cp_c": oil.get("cp_c", 0.0),
                    "density": oil.get("density_kg_m3", 900.0),
                    "mu_a": oil.get("mu_a"),
                    "mu_b": oil.get("mu_b", 0.0),
                    "k_a": oil.get("k_a"),
                    "k_b": oil.get("k_b", 0.0),
                    "t_min_c": oil.get("t_min_c", 0.0),
                    "t_max_c": oil.get("t_max_c", 300.0),
                }
        except Exception as e:
            logger.error(f"thermal_oils.json okunamadı: {e}")


load_external_fluids()


def get_fluid_list_flat():
    """Tüm akışkanları tek boyutlu bir liste olarak döndürür."""
    flat_list = []
    for _category, fluids in FLUID_OPTIONS.items():
        for fluid_name in fluids:
            flat_list.append(f"{fluid_name}")
    return flat_list


def get_fluid_data(selected_name):
    """Seçilen akışkan ismine göre sözlükteki verisini döndürür."""
    for _category, fluids in FLUID_OPTIONS.items():
        if selected_name in fluids:
            return fluids[selected_name]
    return None


def materialize_fluid_data(fluid_data, T_c=None):
    """Sıcaklığa bağlı korelasyonları hesaplanmış akışkan verisine dönüştürür.

    Desteklenen korelasyon formatları:
      - Linear cp:    cp = cp_a + cp_b * T
      - Quadratic cp:  cp = cp_a + cp_b * T + cp_c * T^2
      - Linear mu:     mu = mu_a + mu_b * T   (Pa·s)
      - Linear k:      k = k_a + k_b * T      (W/m·K)
    """
    if fluid_data is None:
        raise FluidPropertyError("Akışkan verisi bulunamadı.")

    data = dict(fluid_data)
    warnings = []

    if data.get("is_correlation"):
        if T_c is None:
            raise FluidPropertyError("Korelasyon tabanlı akışkan için sıcaklık gereklidir.")

        t_min = data.get("t_min_c")
        t_max = data.get("t_max_c")
        if t_min is not None and T_c < t_min:
            warnings.append(
                f"{data.get('name', 'Akışkan')} sıcaklığı alt korelasyon sınırının altında: {T_c:.1f} < {t_min:.1f} °C"
            )
        if t_max is not None and T_c > t_max:
            warnings.append(
                f"{data.get('name', 'Akışkan')} sıcaklığı üst korelasyon sınırının üstünde: {T_c:.1f} > {t_max:.1f} °C"
            )

        # Heat capacity: quadratic with linear fallback
        cp_a = data.get("cp_a", 1500.0)
        cp_b = data.get("cp_b", 2.0)
        cp_c = data.get("cp_c", 0.0)
        data["cp"] = cp_a + cp_b * T_c + cp_c * T_c * T_c

        # Dynamic viscosity: linear correlation if available
        if data.get("mu_a") is not None:
            mu_a = data["mu_a"]
            mu_b = data.get("mu_b", 0.0)
            data["mu"] = max(1e-6, mu_a + mu_b * T_c)
        if data.get("k_a") is not None:
            k_a = data["k_a"]
            k_b = data.get("k_b", 0.0)
            data["k_cond"] = max(0.01, k_a + k_b * T_c)

        data["is_coolprop"] = False

    data["warnings"] = warnings
    return data


def get_chedl_mixture_fluid_data(comps, mole_fracs, T_c, P_pa):
    try:
        from thermo import Mixture

        ids = [THERMO_NAME_MAP.get(name, name) for name in comps]
        zs = [mole_fracs[name] for name in comps]
        mix = Mixture(IDs=ids, zs=zs, T=T_c + 273.15, P=P_pa)
        return {
            "name": "Mixture (ChEDL/thermo)",
            "is_coolprop": False,
            "cp": mix.Cp,
            "density": mix.rho,
            "mu": mix.mu,
            "k_cond": mix.k,
            "property_source": "ChEDL/thermo",
        }
    except FileNotFoundError as exc:
        logger.exception(
            "ChEDL/thermo veri dosyası bulunamadı. PyInstaller build komutunda chemicals/thermo data dosyaları eksik olabilir."
        )
        raise FileNotFoundError(
            f"{exc}. Paketleme hatası: ChEDL/thermo/chemicals veri dosyaları exe içine dahil edilmemiş. "
            "Release paketini --collect-data chemicals --collect-data thermo --collect-data fluids ile yeniden oluşturun."
        ) from exc


def get_mixture_fluid_data(components, comp_type="mole", T_c=200.0, P_pa=101325.0):
    T_k = T_c + 273.15
    from config import GAS_MOLECULAR_WEIGHTS as MW_map

    comps = {k: v for k, v in components.items() if v > 0}
    if not comps:
        raise FluidPropertyError("Karışım kompozisyonu boş. En az bir bileşen için pozitif oran girilmelidir.")
    unknown = sorted(k for k in comps if k not in MW_map)
    if unknown:
        raise FluidPropertyError(f"Karışım molekül ağırlığı bilinmeyen bileşen içeriyor: {', '.join(unknown)}")

    total_val = sum(comps.values())

    if comp_type == "mass":
        mass_fracs = {k: v / total_val for k, v in comps.items()}
        total_moles = sum(mass_fracs[k] / MW_map[k] for k in comps)
        mole_fracs = {k: (mass_fracs[k] / MW_map[k]) / total_moles for k in comps}
    else:
        mole_fracs = {k: v / total_val for k, v in comps.items()}
        total_mass = sum(mole_fracs[k] * MW_map[k] for k in comps)
        mass_fracs = {k: (mole_fracs[k] * MW_map[k]) / total_mass for k in comps}

    # HEOS karisim stringi olustur
    heos_str = "HEOS::" + "&".join([f"{k}[{mole_fracs[k]:.4f}]" for k in comps])
    logger.info(f"HEOS Karışım Stringi: {heos_str}")

    try:
        import CoolProp.CoolProp as CP

        # HEOS gercek gaz modeli
        cp_mix = CP.PropsSI("C", "T", T_k, "P", P_pa, heos_str)
        rho_mix = CP.PropsSI("D", "T", T_k, "P", P_pa, heos_str)
        mu_mix = CP.PropsSI("V", "T", T_k, "P", P_pa, heos_str)
        k_mix = CP.PropsSI("L", "T", T_k, "P", P_pa, heos_str)

        return {
            "name": "Mixture (HEOS)",
            "is_coolprop": False,
            "cp": cp_mix,
            "density": rho_mix,
            "mu": mu_mix,
            "k_cond": k_mix,
            "property_source": "CoolProp HEOS mixture",
        }
    except Exception:
        logger.info("CoolProp HEOS kararsız. Wilke (viskozite) + Wassiljewa (iletkenlik) karışım modeline geçiliyor...")
        cp_mix = 0.0
        rho_mix_inv = 0.0
        mu_mix = 0.0
        k_mix = 0.0

        try:
            comp_names = list(comps.keys())
            n_c = len(comp_names)
            cp_i_list = []
            rho_i_list = []
            mu_i_list = []
            k_i_list = []
            MW_i_list = []
            x_i_list = []
            w_i_list = []

            for name in comp_names:
                cp_i = CP.PropsSI("C", "T", T_k, "P", P_pa, name)
                rho_i = CP.PropsSI("D", "T", T_k, "P", P_pa, name)
                mu_i = CP.PropsSI("V", "T", T_k, "P", P_pa, name)
                k_i = CP.PropsSI("L", "T", T_k, "P", P_pa, name)

                cp_i_list.append(cp_i)
                rho_i_list.append(rho_i)
                mu_i_list.append(mu_i)
                k_i_list.append(k_i)
                MW_i_list.append(MW_map[name])
                x_i_list.append(mole_fracs[name])
                w_i_list.append(mass_fracs[name])

            cp_mix = sum(w_i_list[i] * cp_i_list[i] for i in range(n_c))
            rho_mix_inv = sum(w_i_list[i] / rho_i_list[i] for i in range(n_c))

            # Wilke φ_ij matrix
            phi = [[1.0] * n_c for _ in range(n_c)]
            for i in range(n_c):
                for j in range(n_c):
                    if i == j:
                        continue
                    num = (1.0 + (mu_i_list[i] / mu_i_list[j]) ** 0.5 * (MW_i_list[j] / MW_i_list[i]) ** 0.25) ** 2
                    den = (8.0 * (1.0 + MW_i_list[i] / MW_i_list[j])) ** 0.5
                    phi[i][j] = num / den if den > 1e-15 else 1.0

            mu_mix = 0.0
            k_mix = 0.0
            for i in range(n_c):
                denom = sum(x_i_list[j] * phi[i][j] for j in range(n_c))
                if denom > 1e-15:
                    mu_mix += x_i_list[i] * mu_i_list[i] / denom
                    k_mix += x_i_list[i] * k_i_list[i] / denom

            return {
                "name": "Mixture (Wilke/Wassiljewa)",
                "is_coolprop": False,
                "cp": cp_mix,
                "density": 1.0 / rho_mix_inv if rho_mix_inv > 0 else 1.0,
                "mu": mu_mix,
                "k_cond": k_mix,
                "property_source": "Wilke viscosity + Wassiljewa conductivity",
            }
        except Exception as cp_fallback_error:
            logger.info(
                f"CoolProp ideal karışım fallback başarısız: {cp_fallback_error}. ChEDL/thermo karışım modeline geçiliyor..."
            )
            return get_chedl_mixture_fluid_data(comps, mole_fracs, T_c, P_pa)
