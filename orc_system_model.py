"""ORC (Organic Rankine Cycle) and Thermal Oil Closed-Loop Thermodynamic System Model.

Models:
1. Flue Gas Waste Heat Recovery Boiler (WHRU / Kazan)
2. Thermal Oil Circulation Pump
3. Proportional 3-Way By-Pass Valve & Bypass Line
4. Thermal Oil - Cyclopentane Superheater (Aşırı Kızdırıcı)
5. Thermal Oil - Cyclopentane Preheater & Evaporator (Ön Isıtıcı & Evaporatör) - in SERIES
6. Cyclopentane Thermodynamic State & Net ORC Power Calculation
"""

from __future__ import annotations

import math
from typing import Any


def therminol66_cp(temp_c: float) -> float:
    """Specific heat of Therminol 66 [J/kg.K] as function of T [°C]."""
    # Valid from 0 °C to 350 °C
    t = max(0.0, min(360.0, temp_c))
    return 1450.0 + 3.12 * t


def therminol66_density(temp_c: float) -> float:
    """Density of Therminol 66 [kg/m³] as function of T [°C]."""
    t = max(0.0, min(360.0, temp_c))
    return max(750.0, 1025.0 - 0.72 * t)


def therminol66_vapor_pressure(temp_c: float) -> float:
    """Vapor pressure of Therminol 66 [Pa] as function of T [°C] (Eastman correlation)."""
    t_k = max(273.15, temp_c + 273.15)
    # log10(P_bar) = 4.258 - 2630.0 / T_K
    log10_p_bar = 4.258 - (2630.0 / t_k)
    p_bar = 10.0 ** max(-6.0, min(1.0, log10_p_bar))
    return max(10.0, p_bar * 1e5)


def calc_pipe_darcy(
    di_mm: float,
    length_m: float,
    mass_flow_kg_s: float,
    rho: float,
    mu: float = 0.002,
    roughness_mm: float = 0.045,
) -> dict[str, float]:
    """Calculate Darcy-Weisbach pipe pressure drop with smooth transition zone."""
    d_m = max(0.01, di_mm / 1000.0)
    l_m = max(0.1, length_m)
    rough_m = max(1e-6, roughness_mm / 1000.0)
    area = (math.pi * d_m * d_m) / 4.0
    v = (mass_flow_kg_s / rho) / area if mass_flow_kg_s > 0 and area > 0 and rho > 0 else 0.0
    re = (rho * v * d_m) / mu if v > 0 and mu > 0 else 0.0

    f = 0.02
    if re > 0:
        if re < 2300:
            f = 64.0 / re
        elif re < 4000:
            f_lam_trans = 64.0 / 2300.0
            term1 = (rough_m / d_m) / 3.7
            term2 = 5.74 / (4000.0 ** 0.9)
            f_turb_trans = 0.25 / ((math.log10(term1 + term2)) ** 2)
            weight = (re - 2300.0) / (4000.0 - 2300.0)
            f = (1.0 - weight) * f_lam_trans + weight * f_turb_trans
        else:
            term1 = (rough_m / d_m) / 3.7
            term2 = 5.74 / (re ** 0.9)
            f = 0.25 / ((math.log10(term1 + term2)) ** 2)
            f = max(0.008, min(0.08, f))
    f = max(0.008, f)
    dp_pa = f * (l_m / d_m) * (rho * v * v / 2.0)
    dp_bar = dp_pa / 1e5
    return {"v": v, "re": re, "f": f, "dp_bar": dp_bar, "dp_pa": dp_pa}


def cyclopentane_tsat(p_bar: float) -> float:
    """Saturation temperature of Cyclopentane [°C] at pressure P [bar].

    Calibrated via CoolProp Helmholtz EOS with NIST Antoine fallback.
    """
    p = max(0.2, min(40.0, p_bar))
    try:
        import CoolProp.CoolProp as CP
        return float(CP.PropsSI("T", "P", p * 1e5, "Q", 0, "Cyclopentane") - 273.15)
    except Exception:
        p_mmhg = p * 750.06168
        log_p = math.log10(p_mmhg)
        denom = 6.88676 - log_p
        if denom <= 0.05:
            return 238.6  # Near critical temperature
        return (1121.1 / denom) - 230.56


def cyclopentane_hfg(t_sat_c: float) -> float:
    """Latent heat of vaporization of Cyclopentane [J/kg] at T_sat [°C]."""
    t = max(20.0, min(235.0, t_sat_c))
    try:
        import CoolProp.CoolProp as CP
        t_k = t + 273.15
        h_l = CP.PropsSI("H", "T", t_k, "Q", 0, "Cyclopentane")
        h_v = CP.PropsSI("H", "T", t_k, "Q", 1, "Cyclopentane")
        return max(50000.0, float(h_v - h_l))
    except Exception:
        t_crit = 238.6
        delta_t = max(1.0, t_crit - t)
        return 395000.0 * (delta_t / (t_crit - 49.25)) ** 0.38


def cyclopentane_properties(
    p_evap_bar: float,
    t_sup_c: float | None = None,
    t_in_c: float = 45.0,
    p_cond_bar: float = 1.5,
) -> dict[str, Any]:
    """Calculate real-fluid Helmholtz thermodynamic properties for Cyclopentane.

    Returns saturation temperatures, enthalpy changes (preheater, evaporator latent heat,
    superheat), and isentropic turbine expansion enthalpy drop.
    """
    p_evap = max(1.0, min(38.0, p_evap_bar))
    p_cond = max(0.5, min(p_evap - 0.2, p_cond_bar))
    p_evap_pa = p_evap * 1e5
    p_cond_pa = p_cond * 1e5

    try:
        import CoolProp.CoolProp as CP
        t_sat = float(CP.PropsSI("T", "P", p_evap_pa, "Q", 0, "Cyclopentane") - 273.15)
        h_l = float(CP.PropsSI("H", "P", p_evap_pa, "Q", 0, "Cyclopentane"))
        h_v = float(CP.PropsSI("H", "P", p_evap_pa, "Q", 1, "Cyclopentane"))
        h_fg = max(50000.0, h_v - h_l)
        h_in = float(CP.PropsSI("H", "P", p_evap_pa, "T", t_in_c + 273.15, "Cyclopentane"))
        rho_l_cond = float(CP.PropsSI("D", "P", p_cond_pa, "Q", 0, "Cyclopentane"))

        t_sup = max(t_sat, float(t_sup_c if t_sup_c is not None else t_sat + 15.0))
        if t_sup <= t_sat + 0.1:
            h_sup = h_v
            s_sup = float(CP.PropsSI("S", "P", p_evap_pa, "Q", 1, "Cyclopentane"))
        else:
            h_sup = float(CP.PropsSI("H", "P", p_evap_pa, "T", t_sup + 273.15, "Cyclopentane"))
            s_sup = float(CP.PropsSI("S", "P", p_evap_pa, "T", t_sup + 273.15, "Cyclopentane"))

        # Isentropic turbine expansion to condenser pressure (Cyclopentane is a dry fluid,
        # expanding into superheated vapor region without droplets)
        h_turb_is = float(CP.PropsSI("H", "P", p_cond_pa, "S", s_sup, "Cyclopentane"))
        dh_is = max(10000.0, h_sup - h_turb_is)

        return {
            "T_sat_C": t_sat,
            "h_l": h_l,
            "h_v": h_v,
            "h_fg": h_fg,
            "h_in": h_in,
            "h_sup": h_sup,
            "dh_is": dh_is,
            "rho_l_cond": rho_l_cond,
            "engine": "CoolProp Helmholtz EOS",
        }
    except Exception:
        # Calibrated NIST Antoine & Watson fallback
        t_sat = cyclopentane_tsat(p_evap)
        h_fg = cyclopentane_hfg(t_sat)
        cp_l = 2250.0  # J/kg.K
        cp_v = 1680.0  # J/kg.K
        h_l = cp_l * max(0.0, t_sat - t_in_c)
        h_in = 0.0
        h_v = h_l + h_fg
        t_sup = max(t_sat, float(t_sup_c if t_sup_c is not None else t_sat + 15.0))
        h_sup = h_v + cp_v * max(0.0, t_sup - t_sat)
        pr = max(1.1, p_evap / p_cond)
        gamma = 1.08
        dh_is = max(10000.0, cp_v * (t_sup + 273.15) * (1.0 - (1.0 / pr) ** ((gamma - 1.0) / gamma)))
        return {
            "T_sat_C": t_sat,
            "h_l": h_l,
            "h_v": h_v,
            "h_fg": h_fg,
            "h_in": h_in,
            "h_sup": h_sup,
            "dh_is": dh_is,
            "rho_l_cond": 705.0,
            "engine": "NIST Antoine / Watson Fallback",
        }


def solve_orc_system(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Solve the combined Flue Gas - Thermal Oil Loop - Cyclopentane ORC network.

    Parameters:
        m_flue (float): Flue gas mass flow rate [kg/s] (default 18.0)
        T_flue_in (float): Flue gas inlet temperature [°C] (default 480.0)
        m_oil (float): Total thermal oil circulation flow [kg/s] (default 32.0)
        bypass_ratio (float): Bypass valve opening ratio [0.0 - 1.0] (default 0.0)
        P_evap_bar (float): Cyclopentane evaporation pressure [bar] (default 14.0)
        m_cp (float): Cyclopentane mass flow rate [kg/s] (default 11.5)
        T_cp_in (float): Cyclopentane liquid return from feed pump [°C] (default 45.0)
        UA_boiler_kW_K (float): Flue gas boiler UA [kW/K] (default 35.0)
        UA_sh_kW_K (float): Superheater UA [kW/K] (default 15.0)
        UA_ph_kW_K (float): Preheater & Evaporator UA [kW/K] (default 45.0)
        pump_efficiency (float): Thermal oil pump isentropic/mech efficiency (default 0.75)
        turbine_efficiency (float): Cyclopentane ORC turbine isentropic efficiency (default 0.82)
        enable_dual_whru (bool): Enable twin parallel WHRU waste heat recovery boilers (default False)
        m_flue_1, m_flue_2 (float): Individual flue gas flows for Boiler 1 & 2 [kg/s]
        T_flue_in_1, T_flue_in_2 (float): Inlet flue gas temperatures for Boiler 1 & 2 [°C]
        UA_boiler_1_kW_K, UA_boiler_2_kW_K (float): UA conductances for Boiler 1 & 2 [kW/K]
        split_oil_whru (float): Fraction of thermal oil routed to WHRU-1 [0.0 - 1.0] (default 0.50)
    """
    p = {
        "m_flue": 18.0,
        "T_flue_in": 480.0,
        "m_oil": 32.0,
        "bypass_ratio": 0.0,
        "P_evap_bar": 14.0,
        "m_cp": 11.5,
        "T_cp_in": 45.0,
        "UA_boiler_kW_K": 35.0,
        "UA_sh_kW_K": 15.0,
        "UA_ph_kW_K": 45.0,
        "pump_efficiency": 0.75,
        "turbine_efficiency": 0.82,
        "enable_dual_whru": False,
        "split_oil_whru": 0.50,
    }
    if params:
        p.update(params)

    m_flue = max(0.1, float(p["m_flue"]))
    t_flue_in = max(100.0, float(p["T_flue_in"]))
    m_oil = max(0.5, float(p["m_oil"]))
    bypass = max(0.0, min(1.0, float(p["bypass_ratio"])))
    p_evap = max(1.0, min(35.0, float(p["P_evap_bar"])))
    m_cp = max(0.1, float(p.get("m_cp_kg_s", p.get("m_cp", 11.5))))
    t_cp_in = max(10.0, min(90.0, float(p["T_cp_in"])))
    ua_sh = max(1.0, float(p["UA_sh_kW_K"])) * 1000.0
    eta_pump = max(0.2, min(0.95, float(p["pump_efficiency"])))
    eta_turb = max(0.4, min(0.95, float(p["turbine_efficiency"])))

    # Scalable WHRU Boiler Train (1 to 5 boilers)
    if "n_boilers" in p:
        n_boilers = max(1, min(5, int(p["n_boilers"])))
    elif p.get("enable_dual_whru", False):
        n_boilers = 2
    else:
        n_boilers = 1
    enable_dual_whru = bool(n_boilers > 1)

    raw_splits = []
    boilers_cfg: list[dict[str, Any]] = []
    for i in range(1, n_boilers + 1):
        m_fi = max(0.0, float(p.get(f"m_flue_{i}", m_flue)))
        t_fi_in = max(50.0, float(p.get(f"T_flue_in_{i}", t_flue_in)))
        ua_bi = max(0.0, float(p.get(f"UA_boiler_{i}_kW_K", p["UA_boiler_kW_K"]))) * 1000.0

        if n_boilers == 2 and "split_oil_whru" in p:
            sp = float(p["split_oil_whru"]) if i == 1 else (1.0 - float(p["split_oil_whru"]))
        else:
            sp = float(p.get(f"split_oil_{i}", 1.0 / n_boilers))
        sp = max(0.0, min(1.0, sp))
        raw_splits.append(sp)
        boilers_cfg.append({"m_f": m_fi, "t_f_in": t_fi_in, "ua_b": ua_bi})

    sum_splits = sum(raw_splits)
    norm_splits = [s / sum_splits for s in raw_splits] if sum_splits > 1e-6 else [1.0 / n_boilers] * n_boilers
    for i in range(n_boilers):
        boilers_cfg[i]["split"] = norm_splits[i]
        boilers_cfg[i]["m_oil"] = m_oil * norm_splits[i]

    # Flue gas property
    cp_flue = 1100.0  # J/kg.K

    # Cyclopentane saturation properties via real-fluid EOS / NIST fallback
    cp_props = cyclopentane_properties(p_evap, t_sup_c=None, t_in_c=t_cp_in)
    t_sat = cp_props["T_sat_C"]
    h_fg = cp_props["h_fg"]
    h_l = cp_props["h_l"]
    h_in = cp_props["h_in"]
    cp_cp_vap = 1680.0  # J/kg.K average vapor heat capacity
    cp_cp_liq = max(1800.0, (h_l - h_in) / max(1.0, t_sat - t_cp_in))

    # Conductance split for Evaporator (latent pool boiling) & Preheater (sensible liquid)
    ua_evap = float(p.get("UA_evap_kW_K", p["UA_ph_kW_K"] * 0.65)) * 1000.0
    ua_pre = float(p.get("UA_pre_kW_K", p["UA_ph_kW_K"] * 0.35)) * 1000.0

    # Active oil flow through Superheater, Evaporator and Preheater in series
    m_oil_active = m_oil * (1.0 - bypass)
    m_oil_bypass = m_oil * bypass

    # Superheater hot oil inlet temperature override or pipeline heat loss
    t_oil_sh_in_manual = p.get("T_oil_sh_in_C") or p.get("sh_t_oil_in")
    delta_t_pipe_loss_param = float(p.get("delta_T_pipe_loss_C", p.get("sh_pipe_loss_c", 0.0)))

    # Iterative closed loop solver for T_oil_supply and T_oil_return
    t_oil_supply = min(290.0, max(t_cp_in + 20.0, t_flue_in - 5.0))
    if t_oil_supply >= t_flue_in:
        t_oil_supply = max(t_cp_in + 15.0, t_flue_in - 2.0)
    t_oil_ret_mixed = min(190.0, max(t_cp_in + 5.0, t_oil_supply - 30.0))
    if t_oil_ret_mixed >= t_oil_supply:
        t_oil_ret_mixed = max(t_cp_in, t_oil_supply - 10.0)
    t_oil_sh_in = t_oil_supply
    delta_t_loss = 0.0
    q_pipe_loss = 0.0

    def _calc_hx(c_hot: float, c_cold: float, ua: float, t_h_in: float, t_c_in: float) -> tuple[float, float, float]:
        if c_hot <= 1e-4 or c_cold <= 1e-4 or ua <= 1e-4 or t_h_in <= t_c_in:
            return 0.0, t_h_in, t_c_in
        c_min = min(c_hot, c_cold)
        c_max = max(c_hot, c_cold)
        cr = c_min / c_max if c_max > 0 else 1.0
        ntu = ua / c_min if c_min > 0 else 1.0
        if abs(cr - 1.0) < 1e-4:
            eps = ntu / (1.0 + ntu)
        else:
            exp_term = math.exp(-ntu * (1.0 - cr))
            denom = 1.0 - cr * exp_term
            eps = (1.0 - exp_term) / denom if abs(denom) > 1e-6 else (ntu / (1.0 + ntu))
        eps = max(0.0, min(0.98, eps))
        q = eps * c_min * (t_h_in - t_c_in)
        t_h_out = t_h_in - q / c_hot
        t_c_out = t_c_in + q / c_cold
        return q, t_h_out, t_c_out

    for _ in range(30):
        cp_oil_avg = therminol66_cp((t_oil_supply + t_oil_ret_mixed) / 2.0)

        # 1. Multi-WHRU Boiler Train (1 to 5 units in parallel)
        q_boiler = 0.0
        sum_m_t_oil = 0.0
        sum_m_t_flue = 0.0
        tot_m_flue = 0.0

        for b in boilers_cfg:
            c_f = b["m_f"] * cp_flue
            c_o = b["m_oil"] * cp_oil_avg
            q_i, t_f_out, t_o_out = _calc_hx(c_f, c_o, b["ua_b"], b["t_f_in"], t_oil_ret_mixed)
            b["q"] = q_i
            b["t_f_out"] = t_f_out
            b["t_o_out"] = t_o_out
            q_boiler += q_i
            sum_m_t_oil += b["m_oil"] * t_o_out
            sum_m_t_flue += b["m_f"] * t_f_out
            tot_m_flue += b["m_f"]

        new_t_oil_supply = (sum_m_t_oil / m_oil) if m_oil > 0 else t_oil_ret_mixed
        t_flue_out = (sum_m_t_flue / tot_m_flue) if tot_m_flue > 0 else boilers_cfg[0]["t_f_in"]

        # 2. Bypass and Process Lines (3-Zone Thermal Modeling)
        if m_oil_active < 0.05:
            # Full bypass (100% bypass)
            t_oil_sh_in = new_t_oil_supply
            t_oil_sh_out = new_t_oil_supply
            t_oil_evap_out = new_t_oil_supply
            t_oil_ph_out = new_t_oil_supply
            q_sh = 0.0
            q_evap = 0.0
            q_pre = 0.0
            t_cp_sup = t_sat
            delta_t_pinch = new_t_oil_supply - t_sat
            q_orc_total = 0.0
            new_t_oil_ret_mixed = new_t_oil_supply
            q_pipe_loss = 0.0
            delta_t_loss = 0.0
        else:
            c_oil_active = m_oil_active * cp_oil_avg

            # Calculate actual Superheater oil inlet temperature (accounting for pipe distance heat loss or manual override)
            if t_oil_sh_in_manual is not None:
                t_oil_sh_in = float(t_oil_sh_in_manual)
                delta_t_loss = max(0.0, new_t_oil_supply - t_oil_sh_in)
            else:
                delta_t_loss = max(0.0, delta_t_pipe_loss_param)
                t_oil_sh_in = max(0.0, new_t_oil_supply - delta_t_loss)

            q_pipe_loss = m_oil_active * cp_oil_avg * delta_t_loss  # Watts

            # 3. Superheater (Series stage 1)
            c_cp_vap_flow = m_cp * cp_cp_vap
            c_min_sh = min(c_oil_active, c_cp_vap_flow)
            c_max_sh = max(c_oil_active, c_cp_vap_flow)
            cr_sh = c_min_sh / c_max_sh if c_max_sh > 0 else 1.0
            ntu_sh = ua_sh / c_min_sh
            eps_sh = (1.0 - math.exp(-ntu_sh * (1.0 - cr_sh))) / (1.0 - cr_sh * math.exp(-ntu_sh * (1.0 - cr_sh))) if cr_sh < 1.0 else ntu_sh / (1.0 + ntu_sh)
            eps_sh = max(0.05, min(0.88, eps_sh))

            q_sh_max = c_min_sh * max(0.0, t_oil_sh_in - t_sat)
            q_sh = max(0.0, eps_sh * q_sh_max)
            t_cp_sup = t_sat + q_sh / c_cp_vap_flow
            t_oil_sh_out = t_oil_sh_in - q_sh / c_oil_active

            # 4. Evaporator (Series stage 2a - Pool Boiling)
            q_evap_dem = m_cp * h_fg
            ntu_evap = ua_evap / c_oil_active
            eps_evap = max(0.05, min(0.95, 1.0 - math.exp(-ntu_evap)))
            q_evap_max = c_oil_active * max(0.0, t_oil_sh_out - t_sat)
            q_evap = min(q_evap_dem, eps_evap * q_evap_max)
            t_oil_evap_out = t_oil_sh_out - q_evap / c_oil_active

            # 5. Pinch Point Evaluation (Between Evaporator Exit Oil and Tsat)
            delta_t_pinch = t_oil_evap_out - t_sat

            # 6. Liquid Preheater (Series stage 2b - Sensible Liquid Counterflow)
            q_pre_dem = m_cp * max(0.0, h_l - h_in)
            cp_cp_liq = max(1800.0, (h_l - h_in) / max(1.0, t_sat - t_cp_in))
            c_cp_l = m_cp * cp_cp_liq
            c_min_pre = min(c_oil_active, c_cp_l)
            c_max_pre = max(c_oil_active, c_cp_l)
            cr_pre = c_min_pre / c_max_pre if c_max_pre > 0 else 1.0
            ntu_pre = ua_pre / c_min_pre
            eps_pre = (1.0 - math.exp(-ntu_pre * (1.0 - cr_pre))) / (1.0 - cr_pre * math.exp(-ntu_pre * (1.0 - cr_pre))) if cr_pre < 1.0 else ntu_pre / (1.0 + ntu_pre)
            eps_pre = max(0.05, min(0.92, eps_pre))

            q_pre_max = c_min_pre * max(0.0, t_oil_evap_out - t_cp_in)
            q_pre = min(q_pre_dem, eps_pre * q_pre_max)
            t_oil_ph_out = t_oil_evap_out - q_pre / c_oil_active

            q_orc_total = q_sh + q_evap + q_pre

            # 7. Mixer: Combine bypass oil (at T_oil_supply) with active return oil (at T_oil_ph_out)
            new_t_oil_ret_mixed = (1.0 - bypass) * t_oil_ph_out + bypass * new_t_oil_supply

        diff = max(abs(new_t_oil_supply - t_oil_supply), abs(new_t_oil_ret_mixed - t_oil_ret_mixed))
        if diff < 0.005:
            t_oil_supply = new_t_oil_supply
            t_oil_ret_mixed = new_t_oil_ret_mixed
            converged = True
            break
        t_oil_supply = 0.5 * t_oil_supply + 0.5 * new_t_oil_supply
        t_oil_ret_mixed = 0.5 * t_oil_ret_mixed + 0.5 * new_t_oil_ret_mixed
    else:
        converged = False

    # First Law check: In closed steady loop without external heat source,
    # Q_orc cannot exceed Q_boiler * (1.0 - bypass) - Q_pipe_loss
    q_max_avail_orc = max(0.0, q_boiler * (1.0 - bypass) - q_pipe_loss)
    if q_orc_total > q_max_avail_orc:
        scale_orc = q_max_avail_orc / max(1.0, q_orc_total)
        q_sh *= scale_orc
        q_evap *= scale_orc
        q_pre *= scale_orc
        q_orc_total = q_sh + q_evap + q_pre
        # Recompute oil stream temperatures consistent with scaled heat duties (Energy Conservation)
        if m_oil_active > 0:
            c_oil_act = m_oil_active * cp_oil_avg
            t_oil_sh_out = t_oil_sh_in - (q_sh / max(1e-4, c_oil_act))
            t_oil_evap_out = t_oil_sh_out - (q_evap / max(1e-4, c_oil_act))
            t_oil_ph_out = t_oil_evap_out - (q_pre / max(1e-4, c_oil_act))
            t_oil_ret_mixed = (1.0 - bypass) * t_oil_ph_out + bypass * t_oil_supply

    # Hydraulic and Electrical Calculations
    rho_oil = therminol66_density((t_oil_supply + t_oil_ret_mixed) / 2.0)

    # Parallel Boiler Branch Hydraulic Friction & Balancing
    dp_branches = []
    for b in boilers_cfg:
        dp_i = 0.35 * ((b["m_oil"] / 16.0) ** 1.85) if b["m_oil"] > 0 else 0.0
        b["dp_bar"] = dp_i
        dp_branches.append(dp_i)
    dp_parallel = max(dp_branches) if dp_branches else 0.0
    dp_balance_diff = (max(dp_branches) - min(dp_branches)) if len(dp_branches) > 1 else 0.0

    # Pipe friction using Darcy-Weisbach if pipe parameters provided
    pipe_di_mm = float(p.get("pipe_di_mm", 154.0))
    pipe_length_m = float(p.get("pipe_length_m", 80.0))
    t_ret_c = max(50.0, min(350.0, t_oil_ret_mixed))
    mu_oil = 0.002 * ((200.0 / (t_ret_c + 10.0)) ** 1.5)
    m_oil_loop = m_oil * (1.0 - 0.3 * bypass)
    pipe_res = calc_pipe_darcy(pipe_di_mm, pipe_length_m, m_oil_loop, rho_oil, mu_oil)
    dp_pipe_bar = pipe_res["dp_bar"]

    # Total oil loop pressure drop (piping Darcy loss, parallel boiler branches and heat exchangers base loss)
    dp_oil_bar = 0.45 + dp_pipe_bar + dp_parallel
    dp_oil_pa = dp_oil_bar * 1e5
    vol_flow_m3_s = m_oil / rho_oil
    w_pump_w = (vol_flow_m3_s * dp_oil_pa) / eta_pump
    w_pump_kw = w_pump_w / 1000.0

    # ORC Real Helmholtz Turbine Expansion & Power
    raw_p_cond = float(p.get("P_cond_bar", 1.5))
    p_cond_bar = max(0.5, min(p_evap - 0.2, raw_p_cond))
    condenser_warning = (
        f"Kondenser basıncı ({raw_p_cond:.2f} bar) buharlaşma basıncından ({p_evap:.2f} bar) küçük olmalıdır. {p_cond_bar:.2f} bar değerine sınırlandırıldı."
        if raw_p_cond >= p_evap
        else None
    )
    props_exp = cyclopentane_properties(p_evap, t_sup_c=t_cp_sup, t_in_c=t_cp_in, p_cond_bar=p_cond_bar)
    dh_is = props_exp["dh_is"]
    rho_l_cond = props_exp["rho_l_cond"]

    # Working fluid total specific heat required to heat liquid from T_cp_in, evaporate, and superheat (J/kg)
    dh_cycle_req = cp_cp_liq * max(0.0, t_sat - t_cp_in) + h_fg + cp_cp_vap * max(0.0, t_cp_sup - t_sat)
    # First Law Enforced: Actual vapor mass flow rate to turbine cannot exceed heat absorbed by ORC fluid
    m_cp_actual = min(m_cp, q_orc_total / dh_cycle_req) if (dh_cycle_req > 0 and q_orc_total > 10.0) else 0.0

    # Turbine mechanical/electrical power
    turb_eta_is = float(p.get("turb_eta_is", eta_turb))
    turb_eta_gen = float(p.get("turb_eta_gen", 0.96))
    w_turb_mech_kw = (m_cp_actual * dh_is * turb_eta_is) / 1000.0 if q_orc_total > 10.0 else 0.0
    w_turb_kw = w_turb_mech_kw * turb_eta_gen

    # Second Law Enforced: Carnot ceiling (eta_carnot * Q_orc)
    t_c_sat_k = cyclopentane_tsat(p_cond_bar) + 273.15
    t_h_sup_k = t_cp_sup + 273.15
    eta_carnot = max(0.0, 1.0 - (t_c_sat_k / t_h_sup_k)) if t_h_sup_k > 0 else 0.0
    w_turb_carnot_max = (q_orc_total / 1000.0) * min(0.28, eta_carnot * 0.85)
    w_turb_kw = min(w_turb_kw, w_turb_carnot_max)

    # Cyclopentane liquid feed pump consumption
    dp_cp_pa = max(0.0, (p_evap - p_cond_bar) * 1e5)
    w_cp_pump_kw = ((m_cp_actual * dp_cp_pa) / (rho_l_cond * 0.70) / 1000.0) if q_orc_total > 10.0 else 0.0

    # Condenser Selection: Air-Cooled Condenser (ACC) vs Water-Cooled Condenser
    condenser_type = str(p.get("condenser_type", "water")).lower().strip()
    is_acc = condenser_type in ("air", "acc", "air_cooled", "hava", "hava_sogutmali")

    q_cond_kw = max(0.0, (q_orc_total / 1000.0) - w_turb_mech_kw)
    t_cond_sat_c = cyclopentane_tsat(p_cond_bar)
    subcooling_k = max(0.0, t_cond_sat_c - t_cp_in)

    if is_acc:
        condenser_type = "air"
        t_air_in = float(p.get("T_air_in", 30.0))
        dt_air = max(6.0, min(22.0, (t_cond_sat_c - t_air_in) * 0.60))
        t_air_out = t_air_in + dt_air
        cp_air = 1006.0
        rho_air = 1.15
        m_air_kg_s = (q_cond_kw * 1000.0) / (cp_air * dt_air) if q_cond_kw > 0 else 0.0
        v_air_m3_s = m_air_kg_s / rho_air
        dp_fan_pa = float(p.get("dp_acc_fan_pa", 125.0))
        eta_fan = float(p.get("eta_acc_fan", 0.65))
        w_fan_kw = (v_air_m3_s * dp_fan_pa / eta_fan) / 1000.0 if q_cond_kw > 0 else 0.0
        w_cond_parasitic_kw = w_fan_kw
        fan_count = max(2, int(math.ceil(q_cond_kw / 550.0))) if q_cond_kw > 0 else 2
        m_cw_kg_s = 0.0
        w_cw_pump_kw = 0.0
        t_cw_in = 25.0
        t_cw_out = 25.0
    else:
        condenser_type = "water"
        t_cw_in = float(p.get("T_cw_in", 25.0))
        dt_cw = float(p.get("dT_cw", 8.0))
        t_cw_out = t_cw_in + dt_cw
        m_cw_kg_s = (q_cond_kw * 1000.0) / (4184.0 * dt_cw) if q_cond_kw > 0 else 0.0
        w_cw_pump_kw = ((m_cw_kg_s / 1000.0) * 1.8e5 / 0.75) / 1000.0 if q_cond_kw > 0 else 0.0
        w_cond_parasitic_kw = w_cw_pump_kw
        w_fan_kw = 0.0
        fan_count = 0
        t_air_in = 30.0
        t_air_out = 30.0
        m_air_kg_s = 0.0
        v_air_m3_s = 0.0

    # Thermal Oil Circulation Pump NPSH
    p_tank_bar = float(p.get("P_oil_tank_bar", 2.0))
    p_sat_oil_pa = therminol66_vapor_pressure(t_oil_ret_mixed)
    npsh_a_oil = max(0.0, ((p_tank_bar * 1e5 - p_sat_oil_pa) / (rho_oil * 9.81)) + 1.5 - 0.35)
    npsh_r_oil = 1.8 + 1.2 * ((m_oil / 32.0) ** 2)
    npsh_margin_oil = npsh_a_oil - npsh_r_oil
    oil_cavitation_warning = bool(npsh_margin_oil < 0.5)

    # Cyclopentane Feed Pump NPSH (Condenser hotwell elevation 1.5 m)
    p_sat_cp_bar = max(0.2, min(5.0, 10 ** (6.88676 - 1121.1 / (t_cp_in + 230.56)) / 750.06168))
    p_suction_cp_pa = p_cond_bar * 1e5
    p_sat_cp_pa = p_sat_cp_bar * 1e5
    npsh_a_cp = max(0.0, ((p_suction_cp_pa - p_sat_cp_pa) / (rho_l_cond * 9.81)) + 1.5 - 0.2)
    npsh_r_cp = 1.6 + 1.0 * ((m_cp / 11.5) ** 2)
    npsh_margin_cp = npsh_a_cp - npsh_r_cp
    cp_cavitation_warning = bool(npsh_margin_cp < 0.5)

    w_net_kw = max(0.0, w_turb_kw - w_pump_kw - w_cp_pump_kw - w_cond_parasitic_kw)
    eta_orc_thermal = (w_turb_kw / (q_orc_total / 1000.0)) if q_orc_total > 10.0 else 0.0
    overall_eff_pct = (w_net_kw / (q_boiler / 1000.0) * 100.0) if q_boiler > 0 else 0.0
    pinch_warning = bool(delta_t_pinch < 5.0)

    boilers_res: list[dict[str, Any]] = []
    for idx, b in enumerate(boilers_cfg):
        boilers_res.append({
            "index": idx + 1,
            "name": f"WHRU-{idx + 1}",
            "Q_kW": round(b["q"] / 1000.0, 2),
            "T_flue_in_C": round(b["t_f_in"], 1),
            "T_flue_out_C": round(b["t_f_out"], 1),
            "T_oil_in_C": round(t_oil_ret_mixed, 1),
            "T_oil_out_C": round(b["t_o_out"], 1),
            "m_flue_kg_s": round(b["m_f"], 2),
            "m_oil_kg_s": round(b["m_oil"], 2),
            "split_oil_pct": round((b["m_oil"] / m_oil) * 100.0, 1) if m_oil > 0 else 0.0,
            "dp_bar": round(b["dp_bar"], 2),
            "active": True,
        })

    b1_dict = boilers_res[0]
    b2_dict = boilers_res[1] if n_boilers >= 2 else {
        "index": 2,
        "name": "WHRU-2",
        "Q_kW": 0.0,
        "T_flue_in_C": round(t_flue_in, 1),
        "T_flue_out_C": round(t_flue_in, 1),
        "T_oil_in_C": round(t_oil_ret_mixed, 1),
        "T_oil_out_C": round(t_oil_ret_mixed, 1),
        "m_flue_kg_s": 0.0,
        "m_oil_kg_s": 0.0,
        "split_oil_pct": 0.0,
        "active": False,
        "dp_bar": 0.0,
    }

    return {
        "params": p,
        "boiler": {
            "Q_kW": round(q_boiler / 1000.0, 2),
            "T_flue_in_C": round(
                t_flue_in if n_boilers == 1 else (sum(b["m_f"] * b["t_f_in"] for b in boilers_cfg) / tot_m_flue if tot_m_flue > 0 else t_flue_in),
                1,
            ),
            "T_flue_out_C": round(t_flue_out, 1),
            "T_oil_in_C": round(t_oil_ret_mixed, 1),
            "T_oil_out_C": round(t_oil_supply, 1),
            "m_flue_kg_s": round(m_flue if n_boilers == 1 else tot_m_flue, 2),
            "m_oil_kg_s": round(m_oil, 2),
            "n_boilers": n_boilers,
            "dual_whru": enable_dual_whru,
            "acid_dew_point_warning": bool(t_flue_out < 135.0),
            "dp_parallel_bar": round(dp_parallel, 2),
            "dp_balance_diff_bar": round(dp_balance_diff, 2),
        },
        "boilers": boilers_res,
        "boiler_1": b1_dict,
        "boiler_2": b2_dict,
        "bypass_valve": {
            "opening_pct": round(bypass * 100.0, 1),
            "m_bypass_kg_s": round(m_oil_bypass, 2),
            "m_active_kg_s": round(m_oil_active, 2),
            "T_bypass_oil_C": round(t_oil_supply, 1),
        },
        "superheater": {
            "Q_kW": round(q_sh / 1000.0, 2),
            "T_oil_in_C": round(t_oil_sh_in, 1),
            "T_oil_manifold_out_C": round(t_oil_supply, 1),
            "delta_T_pipe_loss_C": round(delta_t_loss, 1),
            "Q_pipe_loss_kW": round(q_pipe_loss / 1000.0, 2),
            "T_oil_out_C": round(t_oil_sh_out, 1),
            "T_cp_in_C": round(t_sat, 1),
            "T_cp_out_C": round(t_cp_sup, 1),
            "phase": "Buhar Aşırı Kızdırma (Superheating)",
        },
        "evaporator": {
            "Q_kW": round(q_evap / 1000.0, 2),
            "T_oil_in_C": round(t_oil_sh_out, 1),
            "T_oil_out_C": round(t_oil_evap_out, 1),
            "T_cp_sat_C": round(t_sat, 1),
            "delta_T_pinch_C": round(delta_t_pinch, 1),
            "pinch_warning": pinch_warning,
            "phase": "Doymuş Kaynama (Pool Boiling)",
        },
        "preheater": {
            "Q_kW": round(q_pre / 1000.0, 2),
            "Q_sensible_kW": round(q_pre / 1000.0, 2),
            "Q_latent_kW": round(q_evap / 1000.0, 2),
            "T_oil_in_C": round(t_oil_evap_out, 1),
            "T_oil_out_C": round(t_oil_ph_out, 1),
            "T_cp_in_C": round(t_cp_in, 1),
            "T_cp_sat_C": round(t_sat, 1),
            "phase": "Sıvı Ön Isıtma (Sensible Liquid Heating)",
        },
        "condenser": {
            "type": condenser_type,
            "type_label": "Hava Soğutmalı Kondenser (ACC)" if condenser_type == "air" else "Su Soğutmalı Kondenser (Gövde-Boru)",
            "warning": condenser_warning,
            "Q_kW": round(q_cond_kw, 2),
            "P_cond_bar": round(p_cond_bar, 2),
            "T_sat_C": round(t_cond_sat_c, 1),
            "T_liquid_out_C": round(t_cp_in, 1),
            "subcooling_K": round(subcooling_k, 1),
            "coolant_name": "Çevre Havası (Ambient Air)" if condenser_type == "air" else "Soğutma Suyu (Cooling Water)",
            "T_coolant_in_C": round(t_air_in if condenser_type == "air" else t_cw_in, 1),
            "T_coolant_out_C": round(t_air_out if condenser_type == "air" else t_cw_out, 1),
            "m_coolant_kg_s": round(m_air_kg_s if condenser_type == "air" else m_cw_kg_s, 2),
            "m_air_kg_s": round(m_air_kg_s, 2) if condenser_type == "air" else 0.0,
            "m_cw_kg_s": round(m_cw_kg_s, 2) if condenser_type == "water" else 0.0,
            "m_cw_m3_h": round(m_cw_kg_s * 3.6, 1) if condenser_type == "water" else 0.0,
            "V_air_m3_s": round(v_air_m3_s, 1) if condenser_type == "air" else 0.0,
            "fan_count": fan_count,
            "W_parasitic_kW": round(w_cond_parasitic_kw, 2),
            "W_fan_kW": round(w_fan_kw, 2),
            "W_cw_pump_kW": round(w_cw_pump_kw, 2),
            "phase": "Yoğuşma (Kanatçıklı Boru ACC)" if condenser_type == "air" else "Yoğuşma (Su Soğutmalı Gövde-Boru)",
        },
        "pump": {
            "W_el_kW": round(w_pump_kw, 2),
            "dp_bar": round(dp_oil_bar, 2),
            "dp_pipe_bar": round(dp_pipe_bar, 3),
            "m_oil_kg_s": round(m_oil, 2),
            "T_oil_C": round(t_oil_ret_mixed, 1),
            "NPSH_a_m": round(npsh_a_oil, 2),
            "NPSH_r_m": round(npsh_r_oil, 2),
            "NPSH_margin_m": round(npsh_margin_oil, 2),
            "cavitation_warning": oil_cavitation_warning,
        },
        "feed_pump": {
            "W_el_kW": round(w_cp_pump_kw, 2),
            "dp_bar": round(p_evap - p_cond_bar, 2),
            "m_cp_kg_s": round(m_cp, 2),
            "T_fluid_C": round(t_cp_in, 1),
            "NPSH_a_m": round(npsh_a_cp, 2),
            "NPSH_r_m": round(npsh_r_cp, 2),
            "NPSH_margin_m": round(npsh_margin_cp, 2),
            "cavitation_warning": cp_cavitation_warning,
        },
        "orc": {
            "P_evap_bar": round(p_evap, 1),
            "P_cond_bar": round(p_cond_bar, 1),
            "T_sat_C": round(t_sat, 1),
            "T_sup_C": round(t_cp_sup, 1),
            "m_cp_kg_s": round(m_cp, 2),
            "m_cp_actual_kg_s": round(m_cp_actual, 2),
            "Q_total_kW": round(q_orc_total / 1000.0, 2),
            "Q_cond_kW": round(q_cond_kw, 2),
            "subcooling_K": round(subcooling_k, 1),
            "W_turb_kW": round(w_turb_kw, 2),
            "W_turb_mech_kW": round(w_turb_mech_kw, 2),
            "eta_carnot": round(eta_carnot, 3),
            "W_feed_pump_kW": round(w_cp_pump_kw, 2),
            "W_net_kW": round(w_net_kw, 2),
            "cycle_eff_pct": round(eta_orc_thermal * 100.0, 2),
            "plant_eff_pct": round(overall_eff_pct, 2),
            "delta_T_pinch_C": round(delta_t_pinch, 1),
            "pinch_warning": pinch_warning,
            "cp_cavitation_warning": cp_cavitation_warning,
            "dh_is_kJ_kg": round(dh_is / 1000.0, 2),
            "thermo_engine": props_exp["engine"],
            "converged": converged,
            "convergence_diff": round(diff, 4),
            "convergence_warning": None if converged else f"Termal yağ kapalı döngü çözücüsü 30 iterasyonda tam yakınsamadı (kalan fark = {diff:.3f} K).",
        },
    }
