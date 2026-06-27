from typing import Any

import pint

_ureg: Any = pint.UnitRegistry()
_ureg.define("degC = kelvin; offset: 273.15")
_ureg.define("degF = 5/9 * kelvin; offset: 255.37222222")

UNIT_MAP = {
    "kg/s": "kg/s",
    "kg/h": "kg/hour",
    "lb/s": "lb/s",
    "m3/s": "m**3/s",
    "m³/s": "m**3/s",
    "m3/h": "m**3/hour",
    "m³/h": "m**3/hour",
    "CFM": "ft**3/min",
    "\u00b0C": "degC",
    "C": "degC",
    "\u00b0F": "degF",
    "F": "degF",
    "K": "kelvin",
}

_EXTRA_UNIT_MAP = {
    "mÂ³/s": "m**3/s",
    "mÂ³/h": "m**3/hour",
    "Â°C": "degC",
    "Â°F": "degF",
    "Ã‚Â°C": "degC",
    "Ã‚Â°F": "degF",
}


def _resolve_unit(raw):
    unit_str = str(raw)
    if unit_str in UNIT_MAP:
        return UNIT_MAP[unit_str]
    if unit_str in _EXTRA_UNIT_MAP:
        return _EXTRA_UNIT_MAP[unit_str]
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
