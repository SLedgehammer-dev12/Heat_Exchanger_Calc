from __future__ import annotations

from typing import Any

import numpy as np

from exceptions import InvalidInputError


def _is_finite(value: float) -> bool:
    return np.isfinite(float(value))


def _require_positive(name: str, value: float | None) -> float:
    if value is None or not _is_finite(value) or float(value) <= 0:
        raise InvalidInputError(f"{name} sıfırdan büyük ve sonlu olmalıdır.")
    return float(value)


def _append_warning(result: dict[str, Any], message: str) -> dict[str, Any]:
    result.setdefault("warnings", []).append(message)
    if result.get("status") == "ok":
        result["status"] = "warning"
    return result


def _append_unique(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)
