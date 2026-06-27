from __future__ import annotations

from typing import Any

from units import from_celsius, to_celsius, to_kg_s  # noqa: F401 — re-export for backwards compat


def _normalize_unit(unit: str) -> str:  # pragma: no cover — retained for backward compatibility
    return str(unit)


def result_warnings(*results: dict[str, Any] | None) -> list[str]:
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
