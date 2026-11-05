import logging
import unicodedata

logger = logging.getLogger(__name__)

UNIT_MAP = {
    "kg/s": "kg/s",
    "kg/h": "kg/hour",
    "lb/s": "lb/s",
    "lb/h": "lb/hour",
    "m3/s": "m**3/s",
    "m³/s": "m**3/s",
    "m3/h": "m**3/hour",
    "m³/h": "m**3/hour",
    "CFM": "ft**3/min",
    "°C": "degC",
    "C": "degC",
    "°F": "degF",
    "F": "degF",
    "K": "kelvin",
}

# Geriye dönük uyumluluk ve mojibake onarımı için eski bozuk encoding haritası
_EXTRA_UNIT_MAP = {
    "mÂ³/s": "m**3/s",
    "mÂ³/h": "m**3/hour",
    "Â°C": "degC",
    "Â°F": "degF",
    "Ã‚Â°C": "degC",
    "Ã‚Â°F": "degF",
}


def _resolve_unit(raw):
    if raw is None:
        return None
    unit_str = str(raw).strip()
    if unit_str in UNIT_MAP:
        return UNIT_MAP[unit_str]
    if unit_str in _EXTRA_UNIT_MAP:
        return _EXTRA_UNIT_MAP[unit_str]

    # NFKC normalizasyonu (ör. üst simge ³ -> 3 veya derece simgesi normalizasyonu)
    norm = unicodedata.normalize("NFKC", unit_str)
    if norm in UNIT_MAP:
        return UNIT_MAP[norm]

    # Olası UTF-8 / latin-1 çift encoding hatasını onarma
    try:
        repaired = unit_str.encode("latin1").decode("utf-8")
        if repaired in UNIT_MAP:
            return UNIT_MAP[repaired]
        repaired_norm = unicodedata.normalize("NFKC", repaired)
        if repaired_norm in UNIT_MAP:
            return UNIT_MAP[repaired_norm]
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return None


def to_kg_s(val, unit, density=1.0):
    u = _resolve_unit(unit)
    v = float(val)
    rho = float(density) if density is not None else 1.0
    if u == "kg/s":
        return v
    if u == "kg/hour":
        return v / 3600.0
    if u == "lb/s":
        return v * 0.45359237
    if u == "lb/hour":
        return (v * 0.45359237) / 3600.0
    if u == "m**3/s":
        return v * rho
    if u == "m**3/hour":
        return (v * rho) / 3600.0
    if u == "ft**3/min":
        return (v * 0.028316846592 * rho) / 60.0
    if u is None and unit is not None:
        logger.warning("Bilinmeyen debi birimi '%s', ham değer dönülüyor.", unit)
    return v


def to_celsius(val, unit):
    u = _resolve_unit(unit)
    v = float(val)
    if u == "degC":
        return v
    if u == "degF":
        return (v - 32.0) * 5.0 / 9.0
    if u == "kelvin":
        return v - 273.15
    if u is None and unit is not None:
        logger.warning("Bilinmeyen sıcaklık birimi '%s', ham değer dönülüyor.", unit)
    return v


def from_celsius(val, unit):
    u = _resolve_unit(unit)
    v = float(val)
    if u == "degC":
        return v
    if u == "degF":
        return (v * 9.0 / 5.0) + 32.0
    if u == "kelvin":
        return v + 273.15
    if u is None and unit is not None:
        logger.warning("Bilinmeyen sıcaklık birimi '%s', ham değer dönülüyor.", unit)
    return v
