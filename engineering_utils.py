def _normalize_unit(unit):
    normalized = str(unit)
    for marker in ("\u00c2", "\u00c3\u201a", "\ufffd", "?"):
        normalized = normalized.replace(marker, "")
    return normalized


def to_kg_s(val, unit, density):
    normalized_unit = _normalize_unit(unit)
    if normalized_unit == "kg/h":
        return val / 3600.0
    if normalized_unit == "lb/s":
        return val * 0.453592
    if normalized_unit in ("m3/s", "m\u00b3/s", "m/s"):
        return val * density
    if normalized_unit in ("m3/h", "m\u00b3/h", "m/h"):
        return (val / 3600.0) * density
    if normalized_unit == "CFM":
        return (val * 0.000471947) * density
    return val


def to_celsius(val, unit):
    normalized_unit = _normalize_unit(unit)
    if normalized_unit in ("\u00b0F", "F"):
        return (val - 32.0) * 5.0 / 9.0
    if normalized_unit == "K":
        return val - 273.15
    return val


def from_celsius(val, unit):
    normalized_unit = _normalize_unit(unit)
    if normalized_unit in ("\u00b0F", "F"):
        return (val * 9.0 / 5.0) + 32.0
    if normalized_unit == "K":
        return val + 273.15
    return val

def result_warnings(*results):
    warnings = []
    for result in results:
        if not result:
            continue
        for msg in result.get("warnings", []):
            if msg not in warnings:
                warnings.append(msg)
    return warnings


def fluid_report_data(label, fluid_data, fluid_obj):
    fluid_data = fluid_data or {}
    source = (
        fluid_data.get("property_source")
        or getattr(fluid_obj, "property_source", None)
        or ("CoolProp" if getattr(fluid_obj, "is_coolprop", False) else "Manual/Correlation")
    )
    return {
        "label": label,
        "name": getattr(fluid_obj, "name", fluid_data.get("name", label)),
        "source": source,
        "cp": getattr(fluid_obj, "cp", fluid_data.get("cp")),
        "density": getattr(fluid_obj, "density", fluid_data.get("density")),
        "mu": getattr(fluid_obj, "mu", fluid_data.get("mu")),
        "k_cond": getattr(fluid_obj, "k_cond", fluid_data.get("k_cond")),
        "property_source": source,
    }
