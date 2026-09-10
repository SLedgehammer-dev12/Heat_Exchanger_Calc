"""Standart üretici verileri: BWG boru çizelgesi ve TEMA kirlilik (fouling) tablosu.

Arayüzlerde kullanıcıya açılır liste (preset) olarak sunulur; milimetre /
kirlilik direnci elle aranmasını ortadan kaldırır.
"""

from __future__ import annotations

# BWG et kalınlığı [mm] (Birmingham Wire Gauge)
BWG_WALL_THICKNESS_MM: dict[int, float] = {
    10: 3.404,
    11: 3.048,
    12: 2.769,
    13: 2.413,
    14: 2.108,
    15: 1.829,
    16: 1.651,
    17: 1.473,
    18: 1.245,
    20: 0.889,
}

# TEMA standart boru dış çapları [mm]
STANDARD_TUBE_OD_MM: list[float] = [19.05, 25.4, 31.75, 38.1, 50.8]

# Yaygın (OD, BWG) kombinasyonları -> et kalınlığı çıkarılıp iç çap hesaplanır.
COMMON_TUBE_SPECS: list[tuple[float, int]] = [
    (19.05, 12),
    (19.05, 14),
    (19.05, 16),
    (19.05, 18),
    (25.4, 12),
    (25.4, 14),
    (25.4, 16),
    (25.4, 18),
    (31.75, 12),
    (31.75, 14),
    (38.1, 12),
    (38.1, 14),
]


def tube_preset_options() -> list[dict]:
    """[(label, D_o_mm, D_i_mm)] listesi döndürür."""
    options: list[dict] = []
    for d_o, bwg in COMMON_TUBE_SPECS:
        wall = BWG_WALL_THICKNESS_MM[bwg]
        d_i = d_o - 2.0 * wall
        options.append(
            {
                "label": f"{d_o:.2f} mm OD × BWG {bwg} ({d_i:.2f} mm ID)",
                "D_o_mm": d_o,
                "D_i_mm": d_i,
            }
        )
    return options


# TEMA kirlilik (fouling) dirençleri [m²·K/W] (TEMA RGP-T-2.4 tipik değerleri)
TEMA_FOULING_FACTORS: dict[str, float] = {
    "Temiz (yok)": 0.0,
    "Soğutma Kulesi Suyu (artılmış)": 0.000176,
    "Soğutma Kulesi Suyu (artılmamış)": 0.000528,
    "Deniz Suyu": 0.000088,
    "Şehir/Kuyu Suyu": 0.000352,
    "Fuel Oil": 0.00088,
    "Motor Yağı": 0.000176,
    "Termal Yağ": 0.000176,
    "Temiz Buhar": 0.00009,
    "Basınçlı Hava / Gaz": 0.000352,
    "Proses Sıvıları (genel)": 0.000352,
}


def fouling_preset_options() -> list[tuple[str, float]]:
    return list(TEMA_FOULING_FACTORS.items())


# API 661 / ISO 13706 Hava Soğutmalı Eşanjör (ACHE) Kanat Tipleri,
# Sürekli Çalışma Sıcaklık Limitleri ve Tipik Temas Dirençleri [m²·K/W]
API661_FIN_TYPES: dict[str, dict] = {
    "L-Fin (Wrap-on)": {
        "max_temp_c": 130.0,
        "contact_resistance": 0.00007,
        "description": "Boru üzerine gerilerek sarılmış L-ayaklı alüminyum kanat. Ekonomik, düşük/orta sıcaklık.",
    },
    "LL-Fin (Overlapped L)": {
        "max_temp_c": 170.0,
        "contact_resistance": 0.00005,
        "description": "Çift binili L-ayaklı kanat; boru yüzeyini korozyona karşı tam örter.",
    },
    "KL-Fin (Knurled L)": {
        "max_temp_c": 250.0,
        "contact_resistance": 0.00003,
        "description": "Tırtıklı boru yüzeyine sarılmış L-ayaklı kanat; yüksek titreşim ve orta sıcaklık.",
    },
    "G-Fin (Embedded / Gömülü)": {
        "max_temp_c": 400.0,
        "contact_resistance": 0.0,
        "description": "Boru dış yüzeyine açılan yive gömülen kanat; yüksek sıcaklık ve ağır hizmet.",
    },
    "Extruded (Bimetalik Ekstrüzyon)": {
        "max_temp_c": 300.0,
        "contact_resistance": 0.0,
        "description": "Dış alüminyum borudan haddelenerek çıkarılmış yekpare kanat; mükemmel korozyon dayanımı.",
    },
}


def ache_fin_options() -> list[dict]:
    """[(label, max_temp_c, contact_resistance)] listesi döndürür."""
    return [
        {
            "name": k,
            "max_temp_c": v["max_temp_c"],
            "contact_resistance": v["contact_resistance"],
            "desc": v["description"],
        }
        for k, v in API661_FIN_TYPES.items()
    ]


def ache_fin_names() -> list[str]:
    """API 661 kanat tipi isim listesini döndürür."""
    return list(API661_FIN_TYPES.keys())


