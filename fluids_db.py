# Kapsamlı Akışkan Veritabanı
# Arayüzlerde (Streamlit ve PyQt5) kullanıcıya seçtirilecek hazır akışkanların listesi.

FLUID_OPTIONS = {
    "Gazlar (Gases)": {
        "Hava (Air)": {"name": "Air", "is_coolprop": True},
        "Doğal Gaz Türbin Egzoz Gazı (Manuel)": {"name": "Exhaust Gas", "is_coolprop": False, "cp": 1100.0, "density": 0.5},
        "Karbondioksit (CO2)": {"name": "CO2", "is_coolprop": True},
        "Metan (CH4)": {"name": "Methane", "is_coolprop": True},
        "Azot (N2)": {"name": "Nitrogen", "is_coolprop": True},
        "Oksijen (O2)": {"name": "Oxygen", "is_coolprop": True},
        "Argon": {"name": "Argon", "is_coolprop": True},
    },
    "Sıvılar (Liquids)": {
        "Su (Water)": {"name": "Water", "is_coolprop": True},
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
        "Mobiltherm 605 (Manuel Yaklaşım)": {"name": "Mobiltherm 605", "is_coolprop": False, "cp": 2200.0, "density": 850.0},
    },
    "Glikol ve Donma Önleyiciler (Glycols)": {
        "Etilen Glikol Karışımı (%50)": {"name": "INCOMP::MEG[0.5]", "is_coolprop": True},
        "Propilen Glikol Karışımı (%50)": {"name": "INCOMP::MPG[0.5]", "is_coolprop": True},
        "Etilen Glikol Karışımı (%30)": {"name": "INCOMP::MEG[0.3]", "is_coolprop": True},
    },
    "Özel (Custom)": {
        "Manuel Giriş (Özel Akışkan)": {"name": "Custom", "is_coolprop": False, "cp": 1000.0, "density": 1000.0},
        "Özel Egzoz Gazı (Kompozisyon)": {"name": "Mixture", "is_coolprop": False, "is_mixture": True}
    }
}

# Thermal Oils JSON Dosyasını Oku
import json
import logging

logger = logging.getLogger(__name__)
import os

THERMO_NAME_MAP = {
    'Nitrogen': 'nitrogen',
    'Oxygen': 'oxygen',
    'CarbonDioxide': 'carbon dioxide',
    'Water': 'water',
    'Argon': 'argon',
    'CarbonMonoxide': 'carbon monoxide',
    'Methane': 'methane',
    'Hydrogen': 'hydrogen',
    'SulfurDioxide': 'sulfur dioxide',
}

def load_external_fluids():
    local_path = os.path.join(os.path.dirname(__file__), "data", "thermal_oils.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
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
                    "density": oil.get("density_kg_m3", 900.0),
                    "t_min_c": oil.get("t_min_c", 0.0),
                    "t_max_c": oil.get("t_max_c", 300.0)
                }
        except Exception as e:
            logger.error(f"thermal_oils.json okunamadı: {e}")

load_external_fluids()

def get_fluid_list_flat():
    """Tüm akışkanları tek boyutlu bir liste olarak döndürür."""
    flat_list = []
    for category, fluids in FLUID_OPTIONS.items():
        for fluid_name in fluids.keys():
            flat_list.append(f"{fluid_name}")
    return flat_list

def get_fluid_data(selected_name):
    """Seçilen akışkan ismine göre sözlükteki verisini döndürür."""
    for category, fluids in FLUID_OPTIONS.items():
        if selected_name in fluids:
            return fluids[selected_name]
    return None


def materialize_fluid_data(fluid_data, T_c=None):
    """Sıcaklığa bağlı korelasyonları hesaplanmış akışkan verisine dönüştürür."""
    if fluid_data is None:
        raise ValueError("Akışkan verisi bulunamadı.")

    data = dict(fluid_data)
    warnings = []

    if data.get("is_correlation"):
        if T_c is None:
            raise ValueError("Korelasyon tabanlı akışkan için sıcaklık gereklidir.")

        t_min = data.get("t_min_c")
        t_max = data.get("t_max_c")
        if t_min is not None and T_c < t_min:
            warnings.append(f"{data.get('name', 'Akışkan')} sıcaklığı alt korelasyon sınırının altında: {T_c:.1f} < {t_min:.1f} °C")
        if t_max is not None and T_c > t_max:
            warnings.append(f"{data.get('name', 'Akışkan')} sıcaklığı üst korelasyon sınırının üstünde: {T_c:.1f} > {t_max:.1f} °C")

        data["cp"] = data.get("cp_a", 1500.0) + data.get("cp_b", 2.0) * T_c
        data["is_coolprop"] = False

    data["warnings"] = warnings
    return data

def get_chedl_mixture_fluid_data(comps, mole_fracs, T_c, P_pa):
    from thermo import Mixture

    ids = [THERMO_NAME_MAP.get(name, name) for name in comps.keys()]
    zs = [mole_fracs[name] for name in comps.keys()]
    mix = Mixture(IDs=ids, zs=zs, T=T_c + 273.15, P=P_pa)
    return {
        'name': 'Mixture (ChEDL/thermo)',
        'is_coolprop': False,
        'cp': mix.Cp,
        'density': mix.rho,
        'mu': mix.mu,
        'k_cond': mix.k,
        'property_source': 'ChEDL/thermo'
    }

def get_mixture_fluid_data(components, comp_type='mole', T_c=200.0, P_pa=101325.0):
    T_k = T_c + 273.15
    MW_map = {
        'Nitrogen': 28.0134, 'Oxygen': 31.998, 'CarbonDioxide': 44.0095, 
        'Water': 18.0153, 'Argon': 39.948, 'CarbonMonoxide': 28.0101,
        'Methane': 16.0425, 'Hydrogen': 2.01588, 'SulfurDioxide': 64.066
    }
    
    comps = {k: v for k, v in components.items() if v > 0}
    if not comps:
        return {'cp': 1000.0, 'density': 1.0, 'mu': 2e-5, 'k_cond': 0.03}
        
    total_val = sum(comps.values())
    
    if comp_type == 'mass':
        mass_fracs = {k: v/total_val for k, v in comps.items()}
        total_moles = sum(mass_fracs[k] / MW_map.get(k, 28.0) for k in comps)
        mole_fracs = {k: (mass_fracs[k] / MW_map.get(k, 28.0)) / total_moles for k in comps}
    else:
        mole_fracs = {k: v/total_val for k, v in comps.items()}
        total_mass = sum(mole_fracs[k] * MW_map.get(k, 28.0) for k in comps)
        mass_fracs = {k: (mole_fracs[k] * MW_map.get(k, 28.0)) / total_mass for k in comps}
        
    # HEOS karisim stringi olustur
    heos_str = 'HEOS::' + '&'.join([f'{k}[{mole_fracs[k]:.4f}]' for k in comps.keys()])
    logger.info(f"HEOS Karışım Stringi: {heos_str}")
    
    try:
        import CoolProp.CoolProp as CP
        # HEOS gercek gaz modeli
        cp_mix = CP.PropsSI('C', 'T', T_k, 'P', P_pa, heos_str)
        rho_mix = CP.PropsSI('D', 'T', T_k, 'P', P_pa, heos_str)
        mu_mix = CP.PropsSI('V', 'T', T_k, 'P', P_pa, heos_str)
        k_mix = CP.PropsSI('L', 'T', T_k, 'P', P_pa, heos_str)
        
        return {
            'name': 'Mixture (HEOS)',
            'is_coolprop': False,
            'cp': cp_mix,
            'density': rho_mix,
            'mu': mu_mix,
            'k_cond': k_mix
        }
    except Exception as e:
        logger.info(f"CoolProp HEOS faz dengesi bu gaz karışımı için kararsız (Normal). İdeal Gaz Karışım (Wilke) modeline geçiliyor...")
        cp_mix = 0.0
        rho_mix_inv = 0.0
        mu_mix = 0.0
        k_mix = 0.0
        
        try:
            for name in comps.keys():
                cp_i = CP.PropsSI('C', 'T', T_k, 'P', P_pa, name)
                rho_i = CP.PropsSI('D', 'T', T_k, 'P', P_pa, name)
                mu_i = CP.PropsSI('V', 'T', T_k, 'P', P_pa, name)
                k_i = CP.PropsSI('L', 'T', T_k, 'P', P_pa, name)

                cp_mix += mass_fracs[name] * cp_i
                rho_mix_inv += mass_fracs[name] / rho_i
                mu_mix += mole_fracs[name] * mu_i
                k_mix += mole_fracs[name] * k_i

            return {
                'name': 'Mixture (Ideal CoolProp)',
                'is_coolprop': False,
                'cp': cp_mix,
                'density': 1.0 / rho_mix_inv if rho_mix_inv > 0 else 1.0,
                'mu': mu_mix,
                'k_cond': k_mix,
                'property_source': 'CoolProp ideal mixture'
            }
        except Exception as cp_fallback_error:
            logger.info(f"CoolProp ideal karışım fallback başarısız: {cp_fallback_error}. ChEDL/thermo karışım modeline geçiliyor...")
            return get_chedl_mixture_fluid_data(comps, mole_fracs, T_c, P_pa)
