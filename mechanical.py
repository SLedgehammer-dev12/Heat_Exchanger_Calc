"""Mekanik tasarım kontrol modülü (Faz C).

ASME Section VIII Division 1 (basınçlı kap) ve API 661 (hava soğutmalı
eşanjör - ACHE) endüstriyel tasarım ön kontrollerini sağlar.

Tüm değerler SI birimindedir (m, Pa, W/m·K, °C).
"""

from config import (
    API661_FACE_VELOCITY_LIMIT,
    API661_TIP_SPEED_LIMIT,
    ASME_DEFAULT_CORROSION_ALLOWANCE,
    ASME_DEFAULT_DESIGN_STRESS,
    ASME_DEFAULT_JOINT_EFFICIENCY,
    ASME_HYDROSTATIC_TEST_FACTOR,
)


class MechanicalDesignError(ValueError):
    """Mekanik tasarım hesabında geçersiz girdi."""


def asme_wall_thickness(P: float, R: float, S: float, E: float = ASME_DEFAULT_JOINT_EFFICIENCY, CA: float = 0.0) -> float:
    """ASME Sec VIII Div.1 UG-27 minimum et kalınlığı [m].

    t_min = P·R / (S·E − 0.6·P) + CA

    *P*: tasarım (iç) basıncı [Pa], *R*: iç yarıçap [m],
    *S*: izin verilen gerilme [Pa], *E*: kaynak/kaynaşma verimi,
    *CA*: korozyon payı [m].
    """
    if P <= 0 or R <= 0 or S <= 0 or E <= 0:
        raise MechanicalDesignError("ASME girdileri pozitif olmalıdır (P, R, S, E).")
    denom = S * E - 0.6 * P
    if denom <= 0:
        raise MechanicalDesignError("ASME: S·E − 0.6·P ≤ 0; tasarım basıncı izin verilen gerilmeyi aşıyor.")
    if CA < 0:
        raise MechanicalDesignError("Korozyon payı (CA) negatif olamaz.")
    return P * R / denom + CA


def hydrostatic_test_pressure(MAWP: float, factor: float = ASME_HYDROSTATIC_TEST_FACTOR) -> float:
    """ASME UG-99 hidrostatik test basıncı [Pa] = factor × MAWP."""
    if MAWP <= 0:
        raise MechanicalDesignError("MAWP pozitif olmalıdır.")
    if factor <= 1.0:
        raise MechanicalDesignError("Hidrostatik test faktörü 1.0'dan büyük olmalıdır.")
    return factor * MAWP


def api661_face_velocity_check(v_face: float) -> tuple[bool, float]:
    """API 661 maksimum hava yüzey hızı kontrolü [m/s] (limit 3.5 m/s)."""
    if v_face < 0:
        raise MechanicalDesignError("Yüzey hızı (v_face) negatif olamaz.")
    return v_face <= API661_FACE_VELOCITY_LIMIT, API661_FACE_VELOCITY_LIMIT


def api661_tip_speed_check(v_tip: float) -> tuple[bool, float]:
    """API 661 fan kanat ucu hızı kontrolü [m/s] (limit 60 m/s)."""
    if v_tip < 0:
        raise MechanicalDesignError("Kanat ucu hızı (v_tip) negatif olamaz.")
    return v_tip <= API661_TIP_SPEED_LIMIT, API661_TIP_SPEED_LIMIT


def mechanical_design_report(geom: dict) -> list[dict]:
    """Geometri/hesap girdilerinden mekanik tasarım rapor satırlarını üretir.

    Her satır: {"label", "value", "status", "ok"} biçimindedir.
    Tasarım basıncı/temperature girilmediyse boş liste döner.
    """
    design_pressure = float(geom.get("design_pressure", 0.0) or 0.0)  # Pa (gauge)
    rows: list[dict] = []
    if design_pressure <= 0:
        return rows

    design_stress = float(geom.get("design_stress", 0.0) or 0.0)
    if design_stress <= 0:
        design_stress = ASME_DEFAULT_DESIGN_STRESS
    joint_eff = float(geom.get("joint_efficiency", 0.0) or 0.0)
    if joint_eff <= 0:
        joint_eff = ASME_DEFAULT_JOINT_EFFICIENCY
    ca = float(geom.get("corrosion_allowance", -1.0) or 0.0)
    if ca < 0:
        ca = ASME_DEFAULT_CORROSION_ALLOWANCE

    R_shell = float(geom.get("D_shell", 0.0) or 0.0) / 2.0
    D_o = float(geom.get("D_o", 0.0) or 0.0)
    if R_shell > 0:
        try:
            t_shell = asme_wall_thickness(design_pressure, R_shell, design_stress, joint_eff, ca)
            p_hydro = hydrostatic_test_pressure(design_pressure)
            rows.append({"label": "Gövde min. et kalınlığı (ASME UG-27)", "value": f"{t_shell*1000:.2f} mm", "status": "ok", "ok": True})
            rows.append({"label": "Hidrostatik test basıncı (1.3×MAWP)", "value": f"{p_hydro/1e6:.2f} MPa", "status": "ok", "ok": True})
        except MechanicalDesignError as exc:
            rows.append({"label": "Gövde et kalınlığı", "value": "—", "status": f"HATA: {exc}", "ok": False})

    if D_o > 0:
        R_tube = (D_o / 2.0)
        try:
            t_tube = asme_wall_thickness(design_pressure, R_tube, design_stress, joint_eff, ca)
            rows.append({"label": "Boru min. et kalınlığı (ASME UG-27)", "value": f"{t_tube*1000:.2f} mm", "status": "ok", "ok": True})
        except MechanicalDesignError as exc:
            rows.append({"label": "Boru et kalınlığı", "value": "—", "status": f"HATA: {exc}", "ok": False})

    # API 661 ACHE — fan / hava soğutmalı kontrolleri
    v_face = float(geom.get("api_face_velocity", 0.0) or 0.0)
    v_tip = float(geom.get("api_tip_speed", 0.0) or 0.0)
    if v_face > 0:
        ok, lim = api661_face_velocity_check(v_face)
        rows.append(
            {
                "label": f"API 661 hava yüzey hızı (≤ {lim} m/s)",
                "value": f"{v_face:.2f} m/s",
                "status": "OK" if ok else f"AŞIM: {v_face:.2f} > {lim} m/s",
                "ok": ok,
            }
        )
    if v_tip > 0:
        ok, lim = api661_tip_speed_check(v_tip)
        rows.append(
            {
                "label": f"API 661 fan kanat ucu hızı (≤ {lim} m/s)",
                "value": f"{v_tip:.2f} m/s",
                "status": "OK" if ok else f"AŞIM: {v_tip:.2f} > {lim} m/s",
                "ok": ok,
            }
        )
    return rows
