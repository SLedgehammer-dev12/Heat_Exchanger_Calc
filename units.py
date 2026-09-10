import unicodedata
from typing import Any

import pint

_ureg: Any = pint.UnitRegistry()
_ureg.define("degC = kelvin; offset: 273.15")
_ureg.define("degF = 5/9 * kelvin; offset: 255.37222222")

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


def to_kg_s(val, unit, density):
    pint_unit = _resolve_unit(unit)
    if pint_unit in ("m**3/s", "m**3/hour", "ft**3/min"):
        q_vol = _ureg.Quantity(val, pint_unit)
        q_mass = q_vol * _ureg.Quantity(density, "kg/m**3")
        return q_mass.to("kg/s").magnitude
    if pint_unit:
        return _ureg.Quantity(val, pint_unit).to("kg/s").magnitude
    return float(val)


def to_celsius(val, unit):
    pint_unit = _resolve_unit(unit)
    if pint_unit:
        return _ureg.Quantity(val, pint_unit).to("degC").magnitude
    return float(val)


def from_celsius(val, unit):
    pint_unit = _resolve_unit(unit)
    if pint_unit:
        return _ureg.Quantity(val, "degC").to(pint_unit).magnitude
    return float(val)
