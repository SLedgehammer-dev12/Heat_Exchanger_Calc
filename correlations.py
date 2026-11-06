from __future__ import annotations

import numpy as np

from exceptions import TemperatureCrossError
from helpers import _append_unique


def _bowman_lmtd_factor(
    T_hot_in: float,
    T_cold_in: float,
    T_hot_out: float,
    T_cold_out: float,
    C_h: float,
    C_c: float,
    N_shell_passes: int = 1,
    hot_is_tube: bool = False,
    warnings: list[str] | None = None,
    strict: bool = False,
) -> float:
    """Bowman-Mueller LMTD correction factor for N-2N TEMA shell-and-tube exchangers.

    Implements the industry-standard Bowman-Mueller algebraic solution for N_shell_passes
    shell passes in series with 2n tube passes.

    For R = 1.0 (balanced capacity rates), the standard formula becomes 0/0 indeterminate.
    L'Hospital's rule is applied to derive the correct limit.

    TEMA standard rule: P and R are strictly defined relative to the tube-side fluid.
    When hot_is_tube=True, P = (T_hot_in - T_hot_out) / delta_T_max and R = C_h / C_c.

    F = 0.75 is recommended by TEMA; F < 0.5 raises a strong warning.

    A temperature cross returns the 0.01 floor (needed as a penalty inside root-finders);
    with strict=True it raises TemperatureCrossError instead.
    """

    def _cross() -> float:
        if strict:
            raise TemperatureCrossError(
                "Sıcaklık çakışması (Temperature cross): bu ısıl görev fiziksel olarak imkansızdır."
            )
        return 0.01

    delta_T_max = T_hot_in - T_cold_in
    if delta_T_max <= 0 or C_h <= 0 or C_c <= 0:
        return 1.0

    if hot_is_tube:
        P = (T_hot_in - T_hot_out) / delta_T_max
        R = C_h / C_c
    else:
        P = (T_cold_out - T_cold_in) / delta_T_max
        R = C_c / C_h

    if P >= 1.0:
        if warnings is not None:
            _append_unique(
                warnings,
                f"Sıcaklık çakışması (Temperature cross): Isıl etkinlik P = {P:.3f} >= 1.0 "
                "olup termodinamik açıdan imkansızdır. Mevcut debi ve sıcaklıklarla bu transfer gerçekleştirilemez.",
            )
        return _cross()

    if P <= 0 or R <= 0:
        return 1.0

    sqrt_R2p1 = np.sqrt(R * R + 1.0)
    N_shell_passes = max(1, int(N_shell_passes))

    if abs(R - 1.0) < 1e-4:
        S = P / (N_shell_passes - N_shell_passes * P + P)
    else:
        alpha = np.power(
            max(1e-12, (1.0 - R * P)) / max(1e-12, (1.0 - P)),
            1.0 / N_shell_passes,
        )
        S = (alpha - 1.0) / (alpha - R)

    if S <= 0 or S >= 1.0:
        if S >= 1.0 and warnings is not None:
            _append_unique(
                warnings,
                f"Sıcaklık çakışması (Temperature cross): Tek gövde etkinliği S = {S:.3f} >= 1.0. "
                "Seri gövde sayısını artırın veya akış düzenini değiştirin.",
            )
        return _cross() if S >= 1.0 else 1.0

    if abs(R - 1.0) < 1e-4:
        denom_val = 2.0 - S * (2.0 + sqrt_R2p1)
        num_val = 2.0 - S * (2.0 - sqrt_R2p1)
        if denom_val <= 0 or num_val <= 0:
            if warnings is not None:
                _append_unique(
                    warnings,
                    "Sıcaklık çakışması (Temperature cross): Mevcut gövde geçiş sayısı "
                    "ile bu ısıl görev fiziksel olarak imkansızdır (S >= S_max). Seri gövde sayısını artırın.",
                )
            return _cross()
        denom = np.log(num_val / denom_val)
        if abs(denom) < 1e-15:
            return 1.0
        F = (sqrt_R2p1 * S / (1.0 - S)) / denom
    else:
        denom_val = 2.0 - S * (R + 1.0 + sqrt_R2p1)
        num_val = 2.0 - S * (R + 1.0 - sqrt_R2p1)
        if denom_val <= 0 or num_val <= 0:
            if warnings is not None:
                _append_unique(
                    warnings,
                    "Sıcaklık çakışması (Temperature cross): Mevcut gövde geçiş sayısı "
                    "ile bu ısıl görev fiziksel olarak imkansızdır (S >= S_max). Seri gövde sayısını artırın.",
                )
            return _cross()
        numerator = sqrt_R2p1 * np.log(max(1e-12, (1.0 - S) / (1.0 - R * S)))
        denominator = (R - 1.0) * np.log(max(1e-12, num_val / denom_val))
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
