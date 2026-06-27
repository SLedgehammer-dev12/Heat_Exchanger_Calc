from __future__ import annotations

import numpy as np

from helpers import _append_unique


def _bowman_lmtd_factor(
    T_hot_in: float,
    T_cold_in: float,
    T_hot_out: float,
    T_cold_out: float,
    C_h: float,
    C_c: float,
    N_shell_passes: int = 1,
    warnings: list[str] | None = None,
) -> float:
    """Bowman-Mueller LMTD correction factor for 1–N TEMA shell-and-tube exchangers.

    Implements the industry-standard Bowman-Mueller algebraic solution for a single
    shell pass with N_shell_passes tube passes.

    For R = 1.0 (balanced capacity rates), the standard formula becomes 0/0 indeterminate.
    L'Hospital's rule is applied to derive the correct limit.

    F = 0.75 is recommended by TEMA; F < 0.5 raises a strong warning.
    """
    delta_T_max = T_hot_in - T_cold_in
    if delta_T_max <= 0 or C_h <= 0:
        return 1.0

    P = (T_cold_out - T_cold_in) / delta_T_max
    if P <= 0 or P >= 1.0:
        return 1.0

    R = C_c / C_h if C_h > 0 else 1.0
    if R <= 0:
        return 1.0

    sqrt_R2p1 = np.sqrt(R * R + 1.0)

    if abs(R - 1.0) < 1e-9:
        S = P / (N_shell_passes - N_shell_passes * P + P)
    else:
        alpha = np.power(
            max(1e-12, (1.0 - R * P)) / max(1e-12, (1.0 - P)),
            1.0 / N_shell_passes,
        )
        S = (alpha - 1.0) / (alpha - R)

    if S <= 0 or S >= 1.0:
        return 1.0

    if abs(R - 1.0) < 1e-9:
        arg_inner = max(
            1e-12,
            (2.0 - S * (2.0 - sqrt_R2p1)) / (2.0 - S * (2.0 + sqrt_R2p1)),
        )
        denom = np.log(arg_inner)
        if abs(denom) < 1e-15:
            return 1.0
        F = (sqrt_R2p1 * S / (1.0 - S)) / denom
    else:
        numerator = sqrt_R2p1 * np.log(max(1e-12, (1.0 - S) / (1.0 - R * S)))
        arg = max(
            1e-12,
            (2.0 - S * (R + 1.0 - sqrt_R2p1)) / (2.0 - S * (R + 1.0 + sqrt_R2p1)),
        )
        denominator = (R - 1.0) * np.log(arg)
        if denominator == 0:
            return 1.0
        F = numerator / denominator

    F = max(0.01, min(1.0, F))

    if F < 0.5 and warnings is not None:
        _append_unique(
            warnings,
            f"Bowman LMTD düzeltme faktörü F = {F:.3f} < 0.5 "
            f"— ısı değiştirici geometrisi uygun değil "
            f"(TEMA F = 0.75 önerir). Seri shell eklemeyi veya "
            f"counterflow düzenlemesini değerlendirin.",
        )
    return F
