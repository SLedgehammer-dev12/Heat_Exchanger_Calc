"""Mekanik tasarım kontrol modülü (Faz C).

ASME Section VIII Division 1 (basınçlı kap) ve API 661 (hava soğutmalı
eşanjör - ACHE) endüstriyel tasarım ön kontrollerini sağlar.

Tüm değerler SI birimindedir (m, Pa, W/m·K, °C).
"""

import math

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


def asme_wall_thickness(
    P: float,
    R: float,
    S: float,
    E: float = ASME_DEFAULT_JOINT_EFFICIENCY,
    CA: float = 0.0,
    use_outer_radius: bool = False,
) -> float:
    """ASME Sec VIII Div.1 UG-27 minimum et kalınlığı [m].

    İç yarıçap ile (UG-27(c)(1), korozyonlu durumdaki R_corroded = R + CA):
      t_min = P·(R + CA) / (S·E − 0.6·P) + CA
    Dış yarıçap (use_outer_radius=True) ile (UG-27(c)(1)):
      t_min = P·R_o / (S·E + 0.4·P) + CA

    *P*: tasarım (iç) basıncı [Pa], *R*: iç veya dış yarıçap [m],
    *S*: izin verilen gerilme [Pa], *E*: kaynak/kaynaşma verimi,
    *CA*: korozyon payı [m].
    """
    if P <= 0 or R <= 0 or S <= 0 or E <= 0:
        raise MechanicalDesignError("ASME girdileri pozitif olmalıdır (P, R, S, E).")
    if P > 0.385 * S * E:
        raise MechanicalDesignError(
            f"Basınç (P={P*1e-5:.1f} bar) ASME UG-27 ince cidar sınırını (0.385·S·E = {0.385*S*E*1e-5:.1f} bar) aşıyor; "
            "Ek 1 kalın cidar formülleri zorunludur."
        )
    r_calc = R if use_outer_radius else (R + CA)
    denom = S * E + 0.4 * P if use_outer_radius else S * E - 0.6 * P
    if denom <= 0:
        raise MechanicalDesignError("ASME: payda ≤ 0; tasarım basıncı izin verilen gerilmeyi aşıyor.")
    if CA < 0:
        raise MechanicalDesignError("Korozyon payı (CA) negatif olamaz.")
    return P * r_calc / denom + CA


def tema_tubesheet_thickness(
    P: float,
    D_shell: float,
    S: float,
    pitch: float,
    D_o: float,
    CA: float = 0.0,
    F: float = 1.0,
    tema_class: str = "R",
) -> float:
    """TEMA RCB-7.13 tüp aynası (tubesheet) minimum kalınlığı [m].

    Bükülme formülü: T = (F * G / 3) * sqrt(P / (eta * S)) + CA
    Ligament verimi: eta = (pitch - D_o) / pitch
    TEMA RCB-7.134 mutlak minimum ayna kalınlığı:
      Sınıf R için 19.05 mm (3/4 in) (Do <= 1 inç) veya 25.4 mm (Do > 1 inç)
      Sınıf C/B için 15.88 mm (5/8 in) (Do <= 1 inç) veya 19.05 mm (Do > 1 inç)
    """
    if P <= 0 or D_shell <= 0 or S <= 0 or pitch <= 0 or D_o <= 0:
        raise MechanicalDesignError("Tüp aynası girdileri pozitif olmalıdır.")
    if pitch <= D_o:
        raise MechanicalDesignError("Hatve (pitch) boru dış çapından büyük olmalıdır.")
    eta = max(0.1, (pitch - D_o) / pitch)
    # Gasket mean diameter yaklaşımı (sabit ayna için yaklaşık D_shell)
    G = D_shell
    t_bending = (F * G / 3.0) * (P / (eta * S)) ** 0.5 + CA
    t_shear = (0.31 * D_shell / eta) * (P / S) + CA
    is_r = str(tema_class).upper().startswith("R")
    t_min_tema = ((0.01905 if D_o <= 0.0254 else 0.0254) if is_r else (0.01588 if D_o <= 0.0254 else 0.01905)) + CA
    return max(t_bending, t_shear, t_min_tema)


def asme_formed_head_thickness(
    P: float,
    D: float,
    S: float,
    E: float = ASME_DEFAULT_JOINT_EFFICIENCY,
    CA: float = 0.0,
    head_type: str = "2:1_ellipsoidal",
) -> float:
    """ASME Sec VIII Div 1 UG-32 bombeli kafa et kalınlığı [m].

    - 2:1 Ellipsoidal (UG-32(d)): t = P * D / (2 * S * E - 0.2 * P) + CA
    - Torispherical (UG-32(e)): t = 0.885 * P * D / (S * E - 0.1 * P) + CA
    """
    if P <= 0 or D <= 0 or S <= 0 or E <= 0:
        raise MechanicalDesignError("ASME UG-32 kafa girdileri pozitif olmalıdır.")
    d_corroded = D + 2.0 * CA
    if head_type.lower() in ("torispherical", "asme_fd", "flanged_dished"):
        denom = S * E - 0.1 * P
        if denom <= 0:
            raise MechanicalDesignError("ASME UG-32: Basınç izin verilen gerilmeye göre çok yüksek (S*E <= 0.1*P).")
        return (0.885 * P * d_corroded) / denom + CA
    else:
        denom = 2.0 * S * E - 0.2 * P
        if denom <= 0:
            raise MechanicalDesignError("ASME UG-32: Basınç izin verilen gerilmeye göre çok yüksek (2*S*E <= 0.2*P).")
        return (P * d_corroded) / denom + CA


def asme_flat_cover_thickness(
    P: float,
    d: float,
    S: float,
    E: float = ASME_DEFAULT_JOINT_EFFICIENCY,
    CA: float = 0.0,
    C: float = 0.3,
) -> float:
    """ASME UG-34 düz kanal kapağı (flat head / channel cover) et kalınlığı [m].

    t = d * sqrt(C * P / (S * E)) + CA
    """
    if P <= 0 or d <= 0 or S <= 0 or E <= 0:
        raise MechanicalDesignError("Düz kapak girdileri pozitif olmalıdır.")
    return d * ((C * P) / (S * E)) ** 0.5 + CA


def tema_min_shell_thickness(D_shell: float, tema_class: str = "R") -> float:
    """TEMA Tablo RCB-3.13 standardına göre karbon çelik gövde mutlak minimum et kalınlığı [m]."""
    d_mm = D_shell * 1000.0
    is_r = tema_class.upper().startswith("R")
    if d_mm <= 305.0:
        return 0.0048  # Schedule standard pipe
    elif d_mm <= 737.0:
        return 0.0095 if is_r else 0.00635
    elif d_mm <= 965.0:
        return 0.0111 if is_r else 0.0079
    else:
        return 0.0127 if is_r else 0.0095


def hydrostatic_test_pressure(
    MAWP: float,
    S_test: float = 1.0,
    S_design: float = 1.0,
    factor: float = ASME_HYDROSTATIC_TEST_FACTOR,
) -> float:
    """ASME UG-99(b) hidrostatik test basıncı [Pa] = factor × MAWP × (S_test / S_design)."""
    if MAWP <= 0 or S_test <= 0 or S_design <= 0:
        raise MechanicalDesignError("MAWP ve gerilme değerleri pozitif olmalıdır.")
    if factor <= 1.0:
        raise MechanicalDesignError("Hidrostatik test faktörü 1.0'dan büyük olmalıdır.")
    stress_ratio = max(1.0, S_test / S_design)
    return factor * MAWP * stress_ratio


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


def api661_fan_coverage_check(
    fan_diameter: float,
    num_fans: int,
    bundle_width: float,
    bundle_length: float,
) -> tuple[bool, float, float]:
    """API 661 Madde 7.2.8.2 fan yüzey kaplama oranı kontrolü (Afan/Aface ≥ 0.40)."""
    if fan_diameter <= 0 or num_fans <= 0 or bundle_width <= 0 or bundle_length <= 0:
        raise MechanicalDesignError("Fan ve demet boyutları pozitif olmalıdır.")
    a_fans = num_fans * (math.pi * fan_diameter**2 / 4.0)
    a_face = bundle_width * bundle_length
    coverage = a_fans / max(1e-6, a_face)
    return coverage >= 0.40, coverage, 0.40


def api661_noise_level(
    tip_speed: float,
    fan_power_kw: float,
    distance_m: float = 1.0,
) -> tuple[float, float]:
    """API 661 / GPSA tahmini ses seviyesi (PWL ve SPL [dBA])."""
    if tip_speed <= 0 or fan_power_kw <= 0:
        return 0.0, 0.0
    pwl = 40.0 + 10.0 * math.log10(max(0.1, fan_power_kw)) + 20.0 * math.log10(max(1.0, tip_speed))
    dist = max(0.5, distance_m)
    spl = pwl - 10.0 * math.log10(max(1.0, 2.0 * math.pi * dist**2))
    return pwl, spl


def api661_fan_power_check(
    v_air_m3_s: float,
    dp_static_pa: float,
    fan_efficiency: float = 0.65,
    drive_efficiency: float = 0.95,
    num_fans: int = 1,
) -> dict[str, float]:
    """API 661 / GPSA hava soğutmalı eşanjör fan aerodinamik güç ve motor seçim hesabı.

    API 661 Madde 7.2.3 uyarınca motor anma gücü mil fren gücünün (BHP) en az %110'u olmalıdır.
    """
    if v_air_m3_s <= 0 or dp_static_pa <= 0 or fan_efficiency <= 0 or drive_efficiency <= 0:
        raise MechanicalDesignError("API 661 fan aerodinamik girdileri pozitif olmalıdır.")
    n_fans = max(1, int(num_fans))
    p_air_w = v_air_m3_s * dp_static_pa
    bhp_w = p_air_w / (fan_efficiency * drive_efficiency)
    bhp_kw = bhp_w / 1000.0
    per_fan_bhp_kw = bhp_kw / n_fans
    motor_kw = bhp_kw * 1.10
    return {
        "air_power_kw": p_air_w / 1000.0,
        "fan_brake_power_kw": bhp_kw,
        "per_fan_brake_power_kw": per_fan_bhp_kw,
        "recommended_motor_kw": motor_kw,
    }


def tema_fiv_analysis(
    D_o: float,
    t_wall: float,
    L_b: float,
    pitch: float,
    v_cross: float,
    rho_shell: float,
    rho_tube: float = 1000.0,
    rho_metal: float = 7850.0,
    E_modulus: float = 2.0e11,
    c_sonic: float | None = None,
    D_shell: float | None = None,
) -> dict:
    """TEMA Bölüm 5 Akış Kaynaklı Titreşim (FIV) analizi."""
    if D_o <= 0 or t_wall <= 0 or L_b <= 0 or pitch <= D_o or rho_shell <= 0:
        raise MechanicalDesignError("TEMA FIV girdileri pozitif ve tutarlı olmalıdır.")
    D_i = max(1e-4, D_o - 2.0 * t_wall)
    I_tube = (math.pi / 64.0) * (D_o**4 - D_i**4)
    m_tube = rho_metal * (math.pi / 4.0) * (D_o**2 - D_i**2)
    m_fluid_in = rho_tube * (math.pi / 4.0) * (D_i**2)
    p_ratio = pitch / D_o
    c_m = min(5.0, max(1.0, (p_ratio**2 + 1.0) / max(1e-4, p_ratio**2 - 1.0)))
    m_hydro = c_m * rho_shell * (math.pi / 4.0) * (D_o**2)
    m_e = m_tube + m_fluid_in + m_hydro

    c_n = 1.57  # Basit mesnetli açıklık
    fn = (c_n / (L_b**2)) * math.sqrt(max(1e-6, E_modulus * I_tube / max(1e-6, m_e)))
    st = 0.22  # Tipik boru demeti Strouhal sayısı
    fv = (st * max(0.0, v_cross)) / D_o if D_o > 0 else 0.0

    freq_ratio = fv / max(1e-6, fn)
    vortex_resonance_risk = 0.8 <= freq_ratio <= 1.2

    beta = 3.0
    delta_0 = 0.05
    v_crit = beta * fn * D_o * math.sqrt(max(1e-6, m_e * delta_0 / max(1e-6, rho_shell * D_o**2)))
    instability_ratio = v_cross / max(1e-6, v_crit)
    fluidelastic_risk = instability_ratio >= 1.0

    acoustic_risk = False
    fa = None
    if c_sonic and D_shell and D_shell > 0 and c_sonic > 0:
        fa = c_sonic / (2.0 * D_shell)
        if 0.8 <= (fv / max(1e-6, fa)) <= 1.2:
            acoustic_risk = True

    return {
        "f_n": fn,
        "f_v": fv,
        "freq_ratio": freq_ratio,
        "vortex_resonance_risk": vortex_resonance_risk,
        "v_crit": v_crit,
        "instability_ratio": instability_ratio,
        "fluidelastic_risk": fluidelastic_risk,
        "f_a": fa,
        "acoustic_risk": acoustic_risk,
        "m_e": m_e,
    }


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
    pitch = float(geom.get("pitch", 0.0) or 0.0)
    if pitch <= 0 and D_o > 0:
        pitch = D_o * 1.25  # TEMA default pitch assumption

    if R_shell > 0:
        try:
            t_shell = asme_wall_thickness(design_pressure, R_shell, design_stress, joint_eff, ca)
            p_hydro = hydrostatic_test_pressure(design_pressure)
            t_tema_shell = tema_min_shell_thickness(R_shell * 2.0, geom.get("tema_class", "R"))
            rows.append({"label": "Gövde min. et kalınlığı (ASME UG-27)", "value": f"{t_shell*1000:.2f} mm", "status": "ok", "ok": True})
            rows.append({"label": "TEMA min. gövde et kalınlığı (Tablo RCB-3.13)", "value": f"{t_tema_shell*1000:.2f} mm", "status": "ok", "ok": True})
            rows.append({"label": "Hidrostatik test basıncı (1.3×MAWP)", "value": f"{p_hydro/1e6:.2f} MPa", "status": "ok", "ok": True})

            if D_o > 0 and pitch > D_o:
                t_ts = tema_tubesheet_thickness(design_pressure, R_shell * 2.0, design_stress, pitch, D_o, ca, tema_class=geom.get("tema_class", "R"))
                rows.append({"label": "Tüp aynası min. kalınlığı (TEMA RCB-7)", "value": f"{t_ts*1000:.2f} mm", "status": "ok", "ok": True})

            t_ellip = asme_formed_head_thickness(design_pressure, R_shell * 2.0, design_stress, joint_eff, ca, head_type="2:1_ellipsoidal")
            rows.append({"label": "2:1 Elipsoidal kafa min. kalınlığı (ASME UG-32(d))", "value": f"{t_ellip*1000:.2f} mm", "status": "ok", "ok": True})

            t_cover = asme_flat_cover_thickness(design_pressure, R_shell * 2.0, design_stress, joint_eff, ca)
            rows.append({"label": "Kanal kapağı min. kalınlığı (ASME UG-34)", "value": f"{t_cover*1000:.2f} mm", "status": "ok", "ok": True})
        except MechanicalDesignError as exc:
            rows.append({"label": "Gövde et kalınlığı", "value": "—", "status": f"HATA: {exc}", "ok": False})

    if D_o > 0:
        R_tube_o = D_o / 2.0
        try:
            # TEMA RCB-1.511: Borularda korozyon payı aranmaz (CA = 0.0). Boru dış çapına göre ASME formülü.
            t_tube = asme_wall_thickness(
                design_pressure, R_tube_o, design_stress, joint_eff, CA=0.0, use_outer_radius=True
            )
            rows.append(
                {
                    "label": "Boru min. et kalınlığı (ASME UG-27, CA=0)",
                    "value": f"{t_tube*1000:.2f} mm",
                    "status": "ok",
                    "ok": True,
                }
            )
        except MechanicalDesignError as exc:
            rows.append({"label": "Boru et kalınlığı", "value": "—", "status": f"HATA: {exc}", "ok": False})

    # TEMA FIV akış kaynaklı titreşim kontrolü
    v_cross = float(geom.get("v_cross", 0.0) or 0.0)
    L_b = float(geom.get("baffle_spacing", 0.0) or 0.0)
    t_wall = float(geom.get("t_wall", 0.0) or ((D_o - float(geom.get("D_i", 0.0) or 0.0)) / 2.0 if D_o > 0 else 0.0))
    rho_shell = float(geom.get("rho_shell", 0.0) or 0.0)
    if v_cross > 0 and L_b > 0 and t_wall > 0 and D_o > 0 and rho_shell > 0 and pitch > D_o:
        try:
            c_sonic = float(geom.get("c_sonic", 0.0) or 0.0)
            d_shell_val = R_shell * 2.0
            fiv = tema_fiv_analysis(
                D_o=D_o,
                t_wall=t_wall,
                L_b=L_b,
                pitch=pitch,
                v_cross=v_cross,
                rho_shell=rho_shell,
                rho_tube=float(geom.get("rho_tube", 1000.0) or 1000.0),
                c_sonic=c_sonic if c_sonic > 0 else None,
                D_shell=d_shell_val if d_shell_val > 0 else None,
            )
            fn = fiv["f_n"]
            fv = fiv["f_v"]
            vcrit = fiv["v_crit"]
            v_ok = not fiv["vortex_resonance_risk"]
            fei_ok = not fiv["fluidelastic_risk"]
            rows.append({
                "label": "TEMA Doğal Frekans (fn) / Girdap Frekansı (fv)",
                "value": f"{fn:.1f} Hz / {fv:.1f} Hz",
                "status": "OK" if v_ok else "UYARI: Rezonans Riski (0.8 < fv/fn < 1.2)",
                "ok": v_ok,
            })
            rows.append({
                "label": "TEMA Akışkan-Elastik Kararsızlık (v/vcrit < 1)",
                "value": f"{v_cross:.2f} m/s (vcrit={vcrit:.2f} m/s)",
                "status": "OK" if fei_ok else "AŞIM: Dinamik Kararsızlık Riski!",
                "ok": fei_ok,
            })
            if fiv.get("f_a") is not None:
                fa = fiv["f_a"]
                ac_ok = not fiv["acoustic_risk"]
                rows.append({
                    "label": "TEMA Akustik Rezonans (fa) / Girdap Frekansı (fv)",
                    "value": f"{fa:.1f} Hz / {fv:.1f} Hz",
                    "status": "OK" if ac_ok else "UYARI: Akustik Rezonans Riski (0.8 < fv/fa < 1.2)",
                    "ok": ac_ok,
                })
        except Exception as exc:
            rows.append({"label": "TEMA Titreşim Analizi", "value": "—", "status": f"HATA: {exc}", "ok": False})

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
    d_fan = float(geom.get("fan_diameter", 0.0) or 0.0)
    n_fans = int(geom.get("num_fans", 0) or 0)
    w_bundle = float(geom.get("bundle_width", 0.0) or 0.0)
    l_bundle = float(geom.get("bundle_length", 0.0) or 0.0)
    if d_fan > 0 and n_fans > 0 and w_bundle > 0 and l_bundle > 0:
        try:
            cov_ok, cov_val, cov_lim = api661_fan_coverage_check(d_fan, n_fans, w_bundle, l_bundle)
            rows.append({
                "label": f"API 661 Fan Kaplama Oranı (Afan/Aface ≥ {cov_lim:.0%})",
                "value": f"{cov_val:.1%}",
                "status": "OK" if cov_ok else f"YETERSİZ: {cov_val:.1%} < {cov_lim:.0%}",
                "ok": cov_ok,
            })
        except Exception as exc:
            rows.append({"label": "API 661 Fan Kaplama", "value": "—", "status": f"HATA: {exc}", "ok": False})
    p_fan_kw = float(geom.get("fan_power_kw", 0.0) or 0.0)
    if v_tip > 0 and p_fan_kw > 0:
        try:
            pwl, spl = api661_noise_level(v_tip, p_fan_kw, float(geom.get("noise_distance_m", 1.0) or 1.0))
            rows.append({
                "label": "API 661 / GPSA Tahmini Gürültü (SPL @ 1m)",
                "value": f"{spl:.1f} dB(A) (PWL={pwl:.1f})",
                "status": "OK" if spl <= 85.0 else f"YÜKSEK: {spl:.1f} > 85 dB(A)",
                "ok": spl <= 85.0,
            })
        except Exception as exc:
            rows.append({"label": "API 661 Gürültü", "value": "—", "status": f"HATA: {exc}", "ok": False})

    v_air_m3_s = float(geom.get("v_air_m3_s", 0.0) or 0.0)
    dp_fan_pa = float(geom.get("dp_acc_fan_pa", geom.get("dp_static_pa", 0.0)) or 0.0)
    if v_air_m3_s > 0 and dp_fan_pa > 0:
        try:
            fan_res = api661_fan_power_check(
                v_air_m3_s=v_air_m3_s,
                dp_static_pa=dp_fan_pa,
                fan_efficiency=float(geom.get("eta_fan", 0.65) or 0.65),
                num_fans=max(1, int(geom.get("num_fans", 1) or 1)),
            )
            rows.append({
                "label": "API 661 Fan Mil Gücü (BHP) / Önerilen Motor",
                "value": f"{fan_res['fan_brake_power_kw']:.1f} kW (Motor ≥ {fan_res['recommended_motor_kw']:.1f} kW)",
                "status": "OK (API 661 %110 Motor Emniyeti Dahil)",
                "ok": True,
            })
        except Exception as exc:
            rows.append({"label": "API 661 Fan Gücü", "value": "—", "status": f"HATA: {exc}", "ok": False})
    return rows
