"""Centralised engineering constants and configuration for Heat Exchanger Calc."""

ENERGY_BALANCE_WARNING_FRACTION = 0.05

SUPPORTED_FLOW_TYPES = {"parallel", "counter", "cross_unmixed", "cross_mixed_unmixed"}

# Eşanjör tipleri
EXCHANGER_TYPE_FINNED = "finned_tube"
EXCHANGER_TYPE_SHELL = "shell_and_tube"
EXCHANGER_TYPE_DOUBLE = "double_pipe"

EXCHANGER_TYPES = {
    EXCHANGER_TYPE_FINNED: "Kanatçıklı Borulu",
    EXCHANGER_TYPE_SHELL: "Gövde-Boru TEMA",
    EXCHANGER_TYPE_DOUBLE: "Çift Borulu",
}

# Her eşanjör tipi için izin verilen akış konfigürasyonları
EXCHANGER_ALLOWED_FLOWS: dict[str, set[str]] = {
    EXCHANGER_TYPE_FINNED: {"cross_unmixed", "cross_mixed_unmixed"},
    EXCHANGER_TYPE_SHELL: {"counter", "cross_mixed_unmixed"},
    EXCHANGER_TYPE_DOUBLE: {"counter", "parallel"},
}

# Eşanjör tipine göre LMTD F-faktörü hesaplama metodu
EXCHANGER_F_METHOD: dict[str, str] = {
    EXCHANGER_TYPE_FINNED: "crossflow",
    EXCHANGER_TYPE_SHELL: "bowman",
    EXCHANGER_TYPE_DOUBLE: "unity",
}

# Eşanjör tipine göre dış taşınım katsayısı metodu
EXCHANGER_HO_METHOD: dict[str, str] = {
    EXCHANGER_TYPE_FINNED: "briggs_grimison",
    EXCHANGER_TYPE_SHELL: "kern",
    EXCHANGER_TYPE_DOUBLE: "annulus_inner",
}

DEFAULT_N_SEGMENTS = 10

MIN_ALLOWABLE_LMTD_F = 0.5

GNIELINSKI_PR_RANGE = (0.7, 160)

TUBE_WALL_ROUGHNESS = 1.5e-6

FALLBACK_NU_INTERNAL_LAMINAR = 3.66

# Laminer akışta termal giriş bölgesi etkisi (Hausen/Graetz). True ise
# Nu = 3.66 + 0.0668*Gz / (1 + 0.04*Gz^(2/3)) kullanılır (kısa boru / yüksek Pr).
LAMINAR_ENTRANCE_MODEL = True

# Pompa / fan verimlilikleri (hidrolik güç tahmini için)
PUMP_EFFICIENCY = 0.70
FAN_EFFICIENCY = 0.60

# Çok geçişli boru demetlerinde dönüş kafaları + nozul lokal kayıpları
# (velocity head cinsinden, geçiş başına yaklaşık TEMA/uygulama kabulü).
LOCAL_LOSS_VELOCITY_HEADS_PER_PASS = 4.0

# TEMA akış kaynaklı titreşim ön değerlendirmesi
TEMA_RHO_V2_LIMIT = 1500.0  # kg/(m·s^2) — aşımında impingement plate öner
MAX_UNSUPPORTED_SPAN_FACTOR = 60.0  # baffle_spacing / D_o üst sınır (ön tarama)

# Sieder-Tate çeper viskozite düzeltmesi: h *= (mu_b / mu_w)^0.14
# Sadece mu(T) bağımlı akışkanlarda (CoolProp / IAPWS) uygulanır.
SIEDER_TATE_CORRECTION = True
SIEDER_TATE_ITERATIONS = 3  # çeper sıcaklığı sabit nokta iterasyonu sayısı

# Gövde giriş/çıkış nozulları basınç kaybı (velocity head katsayısı, nozul başına)
SHELL_NOZZLE_VELOCITY_HEADS = 1.0
SHELL_NOZZLE_COUNT = 2  # giriş + çıkış

# ASME Section VIII Div.1 mekanik tasarım varsayılanları
ASME_DEFAULT_DESIGN_STRESS = 110.0e6  # tipik karbon çeliği izin verilen gerilme [Pa]
ASME_DEFAULT_JOINT_EFFICIENCY = 0.85  # kaynaklı, kısmi RT
ASME_DEFAULT_CORROSION_ALLOWANCE = 3.0e-3  # 3 mm korozyon payı [m]
ASME_HYDROSTATIC_TEST_FACTOR = 1.3  # ASME UG-99: 1.3 × MAWP

# API 661 (hava soğutmalı eşanjör - ACHE) limitleri
API661_FACE_VELOCITY_LIMIT = 3.5  # m/s — maksimum hava yüzey hızı
API661_TIP_SPEED_LIMIT = 60.0  # m/s — maksimum fan kanat ucu hızı

# Bell-Delaware opsiyonel gövde tarafı modeli (rigorous rating)
# h_o = h_id · J_c · J_l · J_b · J_s · J_r. False iken Kern metodu kullanılır.
USE_BELL_DELAWARE = True


BRIGGS_YOUNG_RE_RANGE = (1100, 18000)

MAX_MIDPOINT_ITERATIONS = 2
MIDPOINT_CONVERGENCE_TOL = 1.0

TUBE_MATERIALS = {
    "Karbon Çelik": 45.0,
    "Paslanmaz Çelik 316": 16.0,
    "Paslanmaz Çelik 304": 16.2,
    "Duplex Paslanmaz 2205": 19.0,
    "Titanyum Gr. 2": 21.9,
    "Bakır": 400.0,
    "Alüminyum": 237.0,
    "Admirallik Pirinci (C44300)": 111.0,
    "Bakır-Nikel 90/10 (C70600)": 45.0,
    "Bakır-Nikel 70/30 (C71500)": 29.0,
    "Inconel 625": 9.8,
}

FIN_MATERIALS = {
    "Alüminyum (k=237)": 237.0,
    "Karbon Çelik (k=45)": 45.0,
}

# TEMA eşanjör isimlendirmeleri (ön başlık - gövde - arka başlık)
TEMA_DESIGNATIONS = {
    "BEM": "Bonnet (B) - Tek geçişli gövde (E) - Sabit tüp sacı (M)",
    "AEL": "Kanallı çıkarılabilir kapak (A) - Tek geçişli gövde (E) - Sabit tüp sacı (L)",
    "AEM": "Kanallı çıkarılabilir kapak (A) - Tek geçişli gövde (E) - Sabit tüp sacı (M)",
    "BES": "Bonnet (B) - Tek geçişli gövde (E) - Yüzer başlık (S)",
    "AES": "Kanallı çıkarılabilir kapak (A) - Tek geçişli gövde (E) - Yüzer başlık (S)",
    "CFU": "Kanallı (C) - İki geçişli gövde (F) - U-tüp (U)",
    "AKU": "Kanallı (A) - Kettle reboiler (K) - U-tüp (U)",
}

GAS_MOLECULAR_WEIGHTS = {
    "Nitrogen": 28.0134,
    "Oxygen": 31.998,
    "CarbonDioxide": 44.0095,
    "Water": 18.0153,
    "Argon": 39.948,
    "CarbonMonoxide": 28.0101,
    "Methane": 16.0425,
    "Hydrogen": 2.01588,
    "SulfurDioxide": 64.066,
}

LOG_FILE_MAX_BYTES = 2_000_000
LOG_FILE_BACKUP_COUNT = 5
