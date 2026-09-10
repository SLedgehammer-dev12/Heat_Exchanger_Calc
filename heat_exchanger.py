from __future__ import annotations

import logging
import warnings
from typing import Any

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import scipy.optimize as opt

logger = logging.getLogger(__name__)
import ht

from correlations import _bowman_lmtd_factor
from plot_theme import PALETTE, SCHEMATIC_SIZE, TEMP_PROFILE_SIZE, apply_theme
from standards import API661_FIN_TYPES

apply_theme()
from exceptions import (
    ConvergenceError,
    FluidPropertyError,
    InvalidExchangerTypeError,
    InvalidFlowTypeError,
    InvalidGeometryError,
    InvalidInputError,
    MissingDependencyError,
)
from helpers import _append_unique, _append_warning, _is_finite, _require_positive

try:
    import CoolProp.CoolProp as CP

    COOLPROP_AVAILABLE = True
except ImportError:
    COOLPROP_AVAILABLE = False

try:
    from thermo import Chemical

    THERMO_AVAILABLE = True
except ImportError:
    THERMO_AVAILABLE = False

try:
    import fluids
    import fluids.core as fluids_core

    FLUIDS_AVAILABLE = True
except ImportError:
    FLUIDS_AVAILABLE = False

try:
    from iapws import IAPWS97

    IAPWS_AVAILABLE = True
except ImportError:
    IAPWS_AVAILABLE = False

import contextlib

from config import (
    BRIGGS_YOUNG_RE_RANGE,
    ENERGY_BALANCE_WARNING_FRACTION,
    EXCHANGER_ALLOWED_FLOWS,
    EXCHANGER_F_METHOD,
    EXCHANGER_TYPE_DOUBLE,
    EXCHANGER_TYPE_FINNED,
    EXCHANGER_TYPE_SHELL,
    EXCHANGER_TYPES,
    FAN_EFFICIENCY,
    GNIELINSKI_PR_RANGE,
    LAMINAR_ENTRANCE_MODEL,
    LOCAL_LOSS_VELOCITY_HEADS_PER_PASS,
    MAX_UNSUPPORTED_SPAN_FACTOR,
    PUMP_EFFICIENCY,
    SHELL_NOZZLE_COUNT,
    SHELL_NOZZLE_VELOCITY_HEADS,
    SIEDER_TATE_CORRECTION,
    SIEDER_TATE_ITERATIONS,
    SUPPORTED_FLOW_TYPES,
    TEMA_RHO_V2_LIMIT,
    TUBE_WALL_ROUGHNESS,
    USE_BELL_DELAWARE,
)

SUPPORTED_FLOW_TYPES = SUPPORTED_FLOW_TYPES
SUPPORTED_EXCHANGER_TYPES = set(EXCHANGER_TYPES.keys())
ENERGY_BALANCE_WARNING_FRACTION = ENERGY_BALANCE_WARNING_FRACTION
CHEDL_NAME_MAP = {
    "Air": "air",
    "CO2": "CO2",
    "INCOMP::T66": None,
    "INCOMP::T55": None,
    "INCOMP::TVP1": None,
    "INCOMP::DowA": None,
    "INCOMP::DowJ": None,
    "INCOMP::DowQ": None,
    "INCOMP::PNF": None,
    "INCOMP::S800": None,
}


def _properties_from_chedl(
    name: str, calc_temp_c: float, pressure: float
) -> tuple[float, float, float | None, float | None]:
    if not THERMO_AVAILABLE:
        raise MissingDependencyError("thermo kütüphanesi bulunamadı.")
    T_K = calc_temp_c + 273.15
    chedl_name = CHEDL_NAME_MAP.get(name, name)
    if chedl_name is None:
        raise FluidPropertyError(f"'{name}' ChEDL/thermo tarafında desteklenmiyor.")
    if chedl_name == "air":
        from thermo import Mixture

        mix = Mixture(
            IDs=["nitrogen", "oxygen", "argon", "carbon dioxide"],
            zs=[0.78084, 0.20946, 0.00934, 0.00036],
            T=T_K,
            P=pressure,
        )
        return mix.Cp, mix.rho, mix.mu, mix.k
    chem = Chemical(chedl_name, T=T_K, P=pressure)
    return chem.Cp, chem.rho, chem.mu, chem.k


def _properties_from_iapws(calc_temp_c: float, pressure: float) -> tuple[float, float, float | None, float | None]:
    if not IAPWS_AVAILABLE:
        raise MissingDependencyError("iapws kütüphanesi bulunamadı. pip install iapws")
    T_K = calc_temp_c + 273.15
    P_MPa = pressure / 1e6
    steam = IAPWS97(T=T_K, P=P_MPa)
    cp = steam.cp  # kJ/kgK -> J/kgK (iapws returns in kJ)
    cp *= 1000.0
    rho = 1.0 / steam.v
    # IAPWS-IF97 does not provide mu/k natively; use IAPWS supplementary release if available
    mu = None
    k = None
    try:
        from iapws import IAPWS97_Transport

        transp = IAPWS97_Transport(T=T_K)
        mu = transp.mu
        k = transp.k
    except (ImportError, Exception):
        pass
    # Fallback: use CoolProp for transport properties if IAPWS transport unavailable
    if mu is None and COOLPROP_AVAILABLE:
        with contextlib.suppress(Exception):
            mu = CP.PropsSI("V", "T", T_K, "P", pressure, "Water")
    if k is None and COOLPROP_AVAILABLE:
        with contextlib.suppress(Exception):
            k = CP.PropsSI("L", "T", T_K, "P", pressure, "Water")
    return cp, rho, mu, k


def _fin_efficiency(
    fin_type: str,
    h_o: float,
    k_fin: float,
    fin_thickness: float,
    fin_height: float,
    D_o: float,
    pitch: float | None = None,
    pitch_parallel: float | None = None,
) -> float:
    """Fin efficiency for annular, rectangular or continuous plate fins.

    Annular: Kern-Kraus (ht) -> Bessel-fallback via scipy.
    Rectangular:  tanh(m*L)/(m*L) formula.
    Plate (Schmidt 1949): equivalent annular radius for continuous plate fin on
        round tube, then the same annular efficiency treatment.
    """
    if fin_type == "plate" and pitch is not None and pitch_parallel is not None:
        r_o = D_o / 2.0
        x_m = pitch / 2.0
        x_l = pitch_parallel / 2.0
        beta = x_l / x_m
        if x_m > 0 and beta > 0.2:
            psi = x_m / r_o
            r_eq = 1.28 * psi * np.sqrt(beta - 0.2) * r_o
            fin_height = max(r_eq - r_o, 1e-9)
            fin_type = "annular"
    if fin_type == "annular":
        try:
            return ht.fin_efficiency_Kern_Kraus(
                Do=D_o, D_fin=D_o + 2.0 * fin_height, t_fin=fin_thickness, k_fin=k_fin, h=h_o
            )
        except Exception as exc:
            warnings.warn(f"Annular fin Kern-Kraus failed; trying Bessel fallback: {exc}", RuntimeWarning, stacklevel=2)
        try:
            from scipy.special import i0, i1, k0, k1

            r_o = D_o / 2.0
            r_fin = r_o + fin_height
            if r_fin <= r_o:
                return 1.0
            m_fin = np.sqrt(2.0 * h_o / (k_fin * fin_thickness))
            if m_fin <= 0:
                return 1.0
            mr_o = m_fin * r_o
            mr_fin = m_fin * r_fin
            C1 = i1(mr_fin) * k1(mr_o) - k1(mr_fin) * i1(mr_o)
            C2 = i0(mr_o) * k1(mr_fin) + k0(mr_o) * i1(mr_fin)
            if C2 <= 0:
                return 0.5
            eta = (2.0 * r_o / m_fin) * C1 / ((r_fin**2 - r_o**2) * C2)
            return max(0.05, min(1.0, float(eta)))
        except Exception as exc2:
            warnings.warn(
                f"Bessel annular fin fallback failed: {exc2}; using rectangular approx.", RuntimeWarning, stacklevel=2
            )
    m_fin = np.sqrt(2 * h_o / (k_fin * fin_thickness))
    if m_fin * fin_height < 1e-9:
        return 1.0
    return np.tanh(m_fin * fin_height) / (m_fin * fin_height)


def _bell_delaware_shell_h(
    Nu_ideal: float,
    k_shell: float,
    D_o: float,
    D_shell: float,
    baffle_cut: float,
    tube_count: int,
    L: float,
    baffle_spacing: float,
    Re_shell: float = 5000.0,
) -> tuple[float, dict[str, float]]:
    """Bell-Delaware (University of Delaware) gövde tarafı h_o modeli.

    h_o = h_id · J_c · J_l · J_b · J_s · J_r

    ht kütüphanesinin analitik Bell-Delaware fonksiyonları (spline interpolasyonu)
    ile TEMA geometrik toleransları üzerinden hesaplanır:
      J_c — ht.baffle_correction_Bell (deflektör kesimi etkisi)
      J_l — ht.baffle_leakage_Bell (gövde/boru deflektör sızıntıları)
      J_b — ht.bundle_bypassing_Bell (boru demeti bypass'ı)
      J_s — ht.unequal_baffle_spacing_Bell (giriş/çıkış deflektör aralığı)
      J_r — ht.laminar_correction_Bell (laminer sıcaklık gradyanı)
    Döndürür: (h_o, {"J_c":..,"J_l":..,"J_b":..,"J_s":..,"J_r":..})
    """
    h_id = Nu_ideal * k_shell / max(D_o, 1e-9)
    bc = max(0.05, min(0.45, baffle_cut))

    try:
        # J_c: Deflektör penceresi dışındaki çapraz akış tüp kesri Fc ~ 1 - 2*bc
        Fc = max(0.1, min(0.9, 1.0 - 2.0 * bc))
        J_c = float(ht.baffle_correction_Bell(crossflow_tube_fraction=Fc))

        # J_s: Deflektör aralığı düzeltmesi
        N_b = max(1, int(L / max(baffle_spacing, 1e-9) - 1))
        J_s = float(ht.unequal_baffle_spacing_Bell(baffles=N_b, baffle_spacing=baffle_spacing))

        # J_b: Demet bypass düzeltmesi (F_bp: bypass alan kesri ~0.15, N_ss=0, N_c: çapraz akış sıra sayısı)
        N_c = max(1, int(np.sqrt(max(1, tube_count)) * (1.0 - 2.0 * bc)))
        J_b = float(ht.bundle_bypassing_Bell(bypass_area_fraction=0.15, seal_strips=0, crossflow_rows=N_c))

        # J_l: Deflektör sızıntıları (S_sb: gövde-deflektör, S_tb: boru-deflektör, S_m: çapraz akış alanı)
        c_sb = float(ht.shell_clearance(DShell=D_shell))
        S_sb = np.pi * D_shell * c_sb * (1.0 - bc / 2.0)
        c_tb = 0.0008  # TEMA standart 0.8 mm boru-delik radyal boşluğu
        S_tb = tube_count * (1.0 - bc) * (np.pi / 4.0) * ((D_o + c_tb) ** 2 - D_o**2)
        S_m = max(1e-6, baffle_spacing * (D_shell - D_o * np.sqrt(tube_count) * 0.8))
        J_l = float(ht.baffle_leakage_Bell(Ssb=max(1e-6, S_sb), Stb=max(1e-6, S_tb), Sm=max(1e-6, S_m)))

        # J_r: Laminer akış düzeltmesi
        if Re_shell < 100:
            J_r = float(ht.laminar_correction_Bell(Re=max(1.0, Re_shell), total_row_passes=max(1, N_c * N_b)))
        else:
            J_r = 1.0

    except Exception:
        # Güvenli fallback
        J_c = max(0.6, min(1.0, 0.55 + 0.72 * (1.0 - 2.0 * bc)))
        N_b = max(1, int(L / max(baffle_spacing, 1e-9) - 1))
        J_l = max(0.6, min(1.0, 1.0 - 0.12 * np.log1p(N_b)))
        tube_rows = max(1, int(np.sqrt(tube_count)))
        J_b = max(0.7, min(1.0, 1.0 - 0.02 * tube_rows))
        J_s = 1.0
        J_r = 1.0

    # Katsayıları sınırla (fiziksel mühendislik aralığı: 0.5 <= J <= 1.0)
    J_c = max(0.5, min(1.0, J_c))
    J_l = max(0.5, min(1.0, J_l))
    J_b = max(0.5, min(1.0, J_b))
    J_s = max(0.5, min(1.0, J_s))
    J_r = max(0.5, min(1.0, J_r))

    h_o = h_id * J_c * J_l * J_b * J_s * J_r
    return float(h_o), {"J_c": J_c, "J_l": J_l, "J_b": J_b, "J_s": J_s, "J_r": J_r}


class Fluid:
    def __init__(
        self,
        name: str = "Generic",
        cp: float | None = None,
        density: float | None = None,
        mu: float | None = None,
        k_cond: float | None = None,
        is_coolprop: bool = False,
        is_iapws: bool = False,
        calc_temp_c: float | None = None,
        pressure: float = 101325,
        h_fg: float | None = None,
    ):
        self.name = name
        self.is_coolprop = is_coolprop
        self.is_iapws = is_iapws
        self.pressure = pressure
        self.calc_temp_c = calc_temp_c
        self.mu = mu
        self.k_cond = k_cond
        self.t_crit = None
        self.t_sat_at_p = None
        self.single_phase = True
        self.h_fg = h_fg  # gizli (latent) ısı [J/kg] — iki-faz çözücü için

        if is_iapws:
            if calc_temp_c is None:
                raise FluidPropertyError(
                    "IAPWS kullanıldığında referans sıcaklık (calc_temp_c) °C cinsinden girilmelidir."
                )
            self.cp, self.density, self.mu, self.k_cond = _properties_from_iapws(calc_temp_c, pressure)
            self.property_source = "IAPWS-IF97"
            self.t_crit = 373.946
            self.t_sat_at_p = IAPWS97(P=pressure / 1e6, x=0).T - 273.15 if IAPWS_AVAILABLE else None

        elif is_coolprop:
            if calc_temp_c is None:
                raise FluidPropertyError(
                    "CoolProp kullanıldığında referans sıcaklık (calc_temp_c) °C cinsinden girilmelidir."
                )
            if not COOLPROP_AVAILABLE:
                self.cp, self.density, self.mu, self.k_cond = _properties_from_chedl(name, calc_temp_c, pressure)
                self.is_coolprop = False
                self.property_source = "ChEDL/thermo"
            else:
                T_K = calc_temp_c + 273.15
                try:
                    self.cp = CP.PropsSI("C", "T", T_K, "P", pressure, name)
                    self.density = CP.PropsSI("D", "T", T_K, "P", pressure, name)
                    # Try fetching viscosity and conductivity
                    try:
                        self.mu = CP.PropsSI("V", "T", T_K, "P", pressure, name)
                        self.k_cond = CP.PropsSI("L", "T", T_K, "P", pressure, name)
                    except ValueError:
                        self.mu = None
                        self.k_cond = None
                    # Phase-change detection for pure fluids
                    try:
                        self.t_crit = CP.PropsSI("Tcrit", "", 0, "", 0, name) - 273.15
                    except (ValueError, Exception):
                        self.t_crit = None
                    try:
                        self.t_sat_at_p = CP.PropsSI("T", "P", pressure, "Q", 0, name) - 273.15
                    except (ValueError, Exception):
                        self.t_sat_at_p = None
                except ValueError:
                    try:
                        incomp_name = name if name.startswith("INCOMP::") else f"INCOMP::{name}"
                        self.cp = CP.PropsSI("C", "T", T_K, "P", pressure, incomp_name)
                        self.density = CP.PropsSI("D", "T", T_K, "P", pressure, incomp_name)
                        try:
                            self.mu = CP.PropsSI("V", "T", T_K, "P", pressure, incomp_name)
                            self.k_cond = CP.PropsSI("L", "T", T_K, "P", pressure, incomp_name)
                        except ValueError:
                            self.mu = None
                            self.k_cond = None
                        self.t_crit = None
                        self.t_sat_at_p = None
                    except ValueError as e:
                        try:
                            self.cp, self.density, self.mu, self.k_cond = _properties_from_chedl(
                                name, calc_temp_c, pressure
                            )
                            self.is_coolprop = False
                            self.property_source = "ChEDL/thermo"
                        except Exception as chedl_exc:
                            raise FluidPropertyError(
                                f"'{name}' CoolProp içerisinde bulunamadı. Hata: {e}. ChEDL/thermo fallback hatası: {chedl_exc}"
                            ) from chedl_exc
        else:
            if cp is None:
                raise FluidPropertyError("Manuel kullanımda cp değeri zorunludur.")
            self.cp = cp
            self.density = density  # type: ignore[assignment]

        self.cp = _require_positive(f"{self.name} cp", self.cp)
        if self.density is not None:
            self.density = _require_positive(f"{self.name} yoğunluk", self.density)
        if self.mu is not None:
            self.mu = _require_positive(f"{self.name} viskozite", self.mu)
        if self.k_cond is not None:
            self.k_cond = _require_positive(f"{self.name} ısıl iletkenlik", self.k_cond)

    def viscosity_at(self, T_c: float) -> float | None:
        """Çeper sıcaklığında viskoziteyi yeniden değerlendirir.

        Sieder-Tate düzeltmesi için kullanılır. Sadece sıcaklık bağımlı kaynağı
        (CoolProp / IAPWS) olan akışkanlarda anlamlıdır; manuel akışkanda μ(T)
        bağımlılığı olmadığından None döner (düzeltme uygulanmaz).
        """
        try:
            if self.is_iapws and IAPWS_AVAILABLE:
                from iapws import IAPWS97_Transport

                return IAPWS97_Transport(T=T_c + 273.15).mu
            if self.is_coolprop and COOLPROP_AVAILABLE:
                T_K = T_c + 273.15
                if self.name.startswith("INCOMP::"):
                    return CP.PropsSI("V", "T", T_K, "P", self.pressure, self.name)
                try:
                    return CP.PropsSI("V", "T", T_K, "P", self.pressure, self.name)
                except ValueError:
                    return CP.PropsSI("V", "T", T_K, "P", self.pressure, f"INCOMP::{self.name}")
        except Exception:
            return None
        return None


class FinTubeHeatExchanger:
    def __init__(
        self,
        hot_fluid: Fluid,
        cold_fluid: Fluid,
        U: float,
        A: float,
        flow_type: str = "cross_unmixed",
        exchanger_type: str = "finned_tube",
    ):
        self.hot_fluid = hot_fluid
        self.cold_fluid = cold_fluid
        self.U = _require_positive("U", U)
        self.A = _require_positive("A", A)
        if flow_type not in SUPPORTED_FLOW_TYPES:
            raise InvalidFlowTypeError(f"Desteklenmeyen akış tipi: {flow_type}")
        self.flow_type = flow_type
        if exchanger_type not in SUPPORTED_EXCHANGER_TYPES:
            raise InvalidExchangerTypeError(f"Desteklenmeyen eşanjör tipi: {exchanger_type}")
        self.exchanger_type = exchanger_type
        self.shell_passes: int = 1
        self.tube_passes: int = 2
        self.baffle_cut: float = 0.25
        # Ayarlanabilir hidrolik verimler (Faz F1) — UI'dan değiştirilebilir
        self.pump_efficiency: float = PUMP_EFFICIENCY
        self.fan_efficiency: float = FAN_EFFICIENCY
        allowed_flows = EXCHANGER_ALLOWED_FLOWS.get(exchanger_type)
        if allowed_flows and flow_type not in allowed_flows:
            raise InvalidFlowTypeError(
                f"'{EXCHANGER_TYPES.get(exchanger_type, exchanger_type)}' için "
                f"izin verilmeyen akış tipi: '{flow_type}'. "
                f"İzin verilen: {', '.join(sorted(allowed_flows))}"
            )

    def _calc_lmtd_F(
        self,
        T_hot_in: float,
        T_cold_in: float,
        T_hot_out: float,
        T_cold_out: float,
        C_h: float,
        C_c: float,
        warnings: list[str] | None = None,
    ) -> float:
        E = EXCHANGER_F_METHOD.get(self.exchanger_type, "bowman")
        if E == "unity":
            return 1.0
        elif E == "bowman":
            # Bowman F: N = boru geçiş sayısı (tube passes). Tek geçiş saf counterflow => F=1.
            if self.tube_passes <= 1:
                return 1.0
            return _bowman_lmtd_factor(
                T_hot_in,
                T_cold_in,
                T_hot_out,
                T_cold_out,
                C_h,
                C_c,
                N_shell_passes=self.tube_passes,
                warnings=warnings,
            )
        elif E == "crossflow":
            return self._calc_crossflow_F(T_hot_in, T_cold_in, T_hot_out, T_cold_out, C_h, C_c, warnings)
        return 1.0

    def _calc_crossflow_F(
        self,
        T_hot_in: float,
        T_cold_in: float,
        T_hot_out: float,
        T_cold_out: float,
        C_h: float,
        C_c: float,
        warnings: list[str] | None = None,
    ) -> float:
        """Cross-flow F-factor derived from ε-NTU relationship: F = NTU_counter / NTU_actual.

        Falls back to F=1.0 for non-cross flow types.
        """
        if "cross" not in self.flow_type:
            return 1.0
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        Cr = C_min / C_max if C_max > 0 else 0.0
        Q_actual = C_h * (T_hot_in - T_hot_out)
        if Q_actual <= 0 or C_min <= 0:
            return 1.0
        epsilon = Q_actual / (C_min * (T_hot_in - T_cold_in))
        epsilon = max(1e-12, min(0.9999, epsilon))
        if Cr < 1e-12:
            NTU_actual = -np.log(1.0 - epsilon)
        elif self.flow_type == "cross_unmixed":

            def _f_eps(ntu):
                return 1.0 - np.exp((1.0 / Cr) * (ntu**0.22) * (np.exp(-Cr * ntu**0.78) - 1.0)) - epsilon

            try:
                NTU_actual = opt.brentq(_f_eps, 1e-6, 20.0)
            except (ValueError, RuntimeError):
                NTU_actual = -np.log(1.0 - epsilon) / Cr if Cr > 0 else -np.log(1.0 - epsilon)
        elif self.flow_type == "cross_mixed_unmixed":
            # solve_ntu ile tutarlı: C_h >= C_c ise Cmax karışmış, aksi halde Cmin karışmış.
            if C_h >= C_c:

                def _f_eps_mix(ntu):
                    return (1.0 / Cr) * (1.0 - np.exp(-Cr * (1.0 - np.exp(-ntu)))) - epsilon

            else:

                def _f_eps_mix(ntu):
                    return 1.0 - np.exp(-(1.0 / Cr) * (1.0 - np.exp(-Cr * ntu))) - epsilon

            try:
                NTU_actual = opt.brentq(_f_eps_mix, 1e-6, 20.0)
            except (ValueError, RuntimeError):
                NTU_actual = -np.log(1.0 - epsilon) / Cr if Cr > 0 else -np.log(1.0 - epsilon)
        else:
            NTU_actual = -np.log(1.0 - epsilon) / Cr if Cr > 0 else -np.log(1.0 - epsilon)

        if Cr < 1e-12:
            NTU_counter = NTU_actual
        elif abs(Cr - 1.0) < 1e-9:
            NTU_counter = epsilon / (1.0 - epsilon)
        else:
            NTU_counter = (
                (1.0 / (Cr - 1.0)) * np.log((epsilon - 1.0) / (Cr * epsilon - 1.0)) if Cr * epsilon < 1.0 else 10.0
            )

        F = NTU_counter / max(NTU_actual, 1e-12)
        F = max(0.01, min(1.0, F))
        if F < 0.5 and warnings is not None:
            _append_unique(warnings, f"Çapraz akış F-faktörü = {F:.3f} < 0.5 — geometri uygun değil.")
        return float(F)

    def _capacity_rates(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float) -> tuple[float, float]:
        m_hot = _require_positive("Sıcak akışkan debisi", m_hot)
        m_cold = _require_positive("Soğuk akışkan debisi", m_cold)
        _require_positive("Sıcak akışkan cp", self.hot_fluid.cp)
        _require_positive("Soğuk akışkan cp", self.cold_fluid.cp)
        _require_positive("U", self.U)
        _require_positive("A", self.A)
        if not _is_finite(T_hot_in) or not _is_finite(T_cold_in):
            raise InvalidInputError("Giriş sıcaklıkları sonlu olmalıdır.")
        if T_hot_in <= T_cold_in:
            raise InvalidInputError("Sıcak akışkan giriş sıcaklığı soğuk akışkan giriş sıcaklığından büyük olmalıdır.")
        C_h = m_hot * self.hot_fluid.cp
        C_c = m_cold * self.cold_fluid.cp
        return C_h, C_c

    def _check_phase_change(
        self, T_hot_in: float, T_cold_in: float, T_hot_out: float | None = None, T_cold_out: float | None = None
    ) -> list[str]:
        """Check whether phase change is occurring and return appropriate warnings."""
        phase_warnings = []
        for fluid, T_in, T_out, label in [
            (self.hot_fluid, T_hot_in, T_hot_out, "Sıcak akışkan"),
            (self.cold_fluid, T_cold_in, T_cold_out, "Soğuk akışkan"),
        ]:
            if not fluid.is_coolprop:
                continue
            if fluid.t_crit is not None and fluid.t_crit > 0 and max(T_in, T_out or T_in) > fluid.t_crit:
                phase_warnings.append(
                    f"{label} ({fluid.name}): T_max = {max(T_in, T_out or T_in):.1f} °C > T_crit = {fluid.t_crit:.1f} °C. "
                    "Kritik üstü bölgede akışkan özellikleri hızla değişir; ε-NTU tek-faz varsayımı geçersiz olabilir."
                )
            if fluid.t_sat_at_p is not None and T_out is not None:
                t_min = min(T_in, T_out)
                t_max = max(T_in, T_out)
                if t_min < fluid.t_sat_at_p < t_max:
                    phase_warnings.append(
                        f"{label} ({fluid.name}): Sıcaklık aralığı ({t_min:.1f}–{t_max:.1f} °C) "
                        f"doyma sıcaklığını ({fluid.t_sat_at_p:.1f} °C) kesiyor. "
                        "İki-fazlı akış olabilir; ε-NTU/LMTD tek-faz varsayımı güvenilir değildir. "
                        "Segment-wise veya iki-faz korelasyonları kullanın."
                    )
        return phase_warnings

    def _map_ht_flow_type(self, C_h: float, C_c: float) -> str:
        """Kendi flow_type değişkenimizi ht kütüphanesinin subtype formatına çevirir."""
        if self.flow_type == "parallel":
            return "parallel"
        if self.flow_type == "counter":
            return "counterflow"
        if self.flow_type == "cross_unmixed":
            return "crossflow"
        if self.flow_type == "cross_mixed_unmixed":
            return "crossflow, mixed Cmax" if C_h >= C_c else "crossflow, mixed Cmin"
        return "counterflow"

    def _terminal_temperature_differences(
        self, T_hot_in: float, T_cold_in: float, T_hot_out: float, T_cold_out: float
    ) -> tuple[float, float]:
        """Akis tipine gore LMTD terminal sicaklik farklarini dondur."""
        if self.flow_type == "parallel":
            return T_hot_in - T_cold_in, T_hot_out - T_cold_out
        return T_hot_in - T_cold_out, T_hot_out - T_cold_in

    def solve_ntu(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, source: str = "custom"):
        """Epsilon-NTU metodunu kullanarak çıkış sıcaklıklarını hesaplar."""
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        C_r = C_min / C_max
        NTU = (self.U * self.A) / C_min

        epsilon = 0.0

        if source == "custom":
            if self.flow_type == "parallel":
                epsilon = (1 - np.exp(-NTU * (1 + C_r))) / (1 + C_r)
            elif self.flow_type == "counter":
                if C_r < 1.0:
                    epsilon = (1 - np.exp(-NTU * (1 - C_r))) / (1 - C_r * np.exp(-NTU * (1 - C_r)))
                else:
                    epsilon = NTU / (1 + NTU)
            elif self.flow_type == "cross_unmixed":
                epsilon = 1 - np.exp((1 / C_r) * (NTU**0.22) * (np.exp(-C_r * (NTU**0.78)) - 1))
            elif self.flow_type == "cross_mixed_unmixed":
                if C_h >= C_c:
                    epsilon = (1 / C_r) * (1 - np.exp(-C_r * (1 - np.exp(-NTU))))
                else:
                    epsilon = 1 - np.exp(-(1 / C_r) * (1 - np.exp(-C_r * NTU)))

        elif source == "ht":
            ht_subtype = self._map_ht_flow_type(C_h, C_c)
            epsilon = ht.hx.effectiveness_from_NTU(NTU=NTU, Cr=C_r, subtype=ht_subtype)
        else:
            raise InvalidInputError(f"Desteklenmeyen NTU kaynağı: {source}")

        if not _is_finite(epsilon) or epsilon < 0 or epsilon > 1.0 + 1e-9:
            raise ConvergenceError(f"Hesaplanan effectiveness fiziksel aralık dışında: {epsilon}")
        epsilon = min(max(float(epsilon), 0.0), 1.0)

        q_max = C_min * (T_hot_in - T_cold_in)
        q = epsilon * q_max
        T_hot_out = T_hot_in - (q / C_h)
        T_cold_out = T_cold_in + (q / C_c)

        result = {
            "Method": "Epsilon-NTU",
            "Source": source,
            "Q [W]": q,
            "epsilon": epsilon,
            "T_hot_in [C]": T_hot_in,
            "T_cold_in [C]": T_cold_in,
            "T_hot_out [C]": T_hot_out,
            "T_cold_out [C]": T_cold_out,
            "NTU": NTU,
            "C_r": C_r,
            "status": "ok",
            "warnings": [],
        }
        if self.flow_type == "cross_unmixed" and source == "custom":
            _append_warning(
                result,
                "Çapraz akış/unmixed NTU bağıntısı yaklaşık korelasyondur; kritik tasarımda ht/tam çözüm ile karşılaştırın.",
            )

        phase_warnings = self._check_phase_change(T_hot_in, T_cold_in, T_hot_out, T_cold_out)
        for pw in phase_warnings:
            _append_warning(result, pw)

        return result

    def solve_pychemengg_ntu(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float):
        """PyChemEngg kuruluysa bağımsız Effectiveness-NTU doğrulaması yapar."""
        try:
            from pychemengg.heattransfer import heatexchangers as pce_hx
        except ImportError as exc:
            raise MissingDependencyError(
                "PyChemEngg kurulu değil. Opsiyonel doğrulama için `pip install pychemengg` çalıştırılabilir."
            ) from exc

        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        C_r = C_min / C_max
        NTU = (self.U * self.A) / C_min
        solver = pce_hx.EffNTU(Cmin=C_min, Cmax=C_max, NTU=NTU, effectiveness="?")
        warnings = []

        if self.flow_type == "parallel":
            epsilon = solver.doublepipe_parallelflow()
        elif self.flow_type == "counter":
            epsilon = solver.doublepipe_counterflow()
        elif self.flow_type == "cross_unmixed":
            epsilon = solver.crossflow_bothfluids_unmixed()
            warnings.append("PyChemEngg çapraz akış both-unmixed bağıntısı da yaklaşık NTU korelasyonudur.")
        elif self.flow_type == "cross_mixed_unmixed":
            epsilon = solver.crossflow_Cmin_unmixed()
            warnings.append("PyChemEngg doğrulamasında cross_mixed_unmixed için Cmin-unmixed varsayımı kullanıldı.")
        else:
            raise InvalidInputError(f"PyChemEngg doğrulaması bu akış tipi için desteklenmiyor: {self.flow_type}")

        if epsilon is None or not _is_finite(epsilon) or epsilon < 0 or epsilon > 1.0 + 1e-9:
            raise ConvergenceError(f"PyChemEngg effectiveness sonucu fiziksel aralık dışında: {epsilon}")
        epsilon = min(max(float(epsilon), 0.0), 1.0)

        q_max = C_min * (T_hot_in - T_cold_in)
        q = epsilon * q_max
        return {
            "Method": "Epsilon-NTU",
            "Source": "PyChemEngg",
            "Q [W]": q,
            "epsilon": epsilon,
            "T_hot_in [C]": T_hot_in,
            "T_cold_in [C]": T_cold_in,
            "T_hot_out [C]": T_hot_in - (q / C_h),
            "T_cold_out [C]": T_cold_in + (q / C_c),
            "NTU": NTU,
            "C_r": C_r,
            "status": "warning" if warnings else "ok",
            "warnings": warnings,
        }

    def solve_lmtd(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, source: str = "ht"):
        """LMTD metodunu iterasyon (root finding) ile kullanarak çıkış sıcaklıklarını hesaplar."""
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)

        def lmtd_residual(Q):
            if Q <= 0:
                return 1e6
            T_h_o = T_hot_in - Q / C_h
            T_c_o = T_cold_in + Q / C_c

            # Fiziksel olmayan sıcaklıkları engelle
            if T_h_o < T_cold_in or T_c_o > T_hot_in:
                return 1e6

            dt1, dt2 = self._terminal_temperature_differences(T_hot_in, T_cold_in, T_h_o, T_c_o)
            if dt1 <= 0 or dt2 <= 0:
                return 1e6

            try:
                LMTD = dt1 if abs(dt1 - dt2) < 1e-06 else (dt1 - dt2) / np.log(dt1 / dt2)
            except ValueError:
                return 1e6

            F = self._calc_lmtd_F(T_hot_in, T_cold_in, T_h_o, T_c_o, C_h, C_c, warnings=warnings)

            Q_lmtd = self.U * self.A * LMTD * F
            return Q - Q_lmtd

        Q_max = min(C_h, C_c) * (T_hot_in - T_cold_in)
        warnings = []
        status = "ok"
        try:
            q_found = opt.brentq(lmtd_residual, 1.0, Q_max * 0.9999)
        except ValueError as exc:
            q_found = 0.0
            status = "failed"
            warnings.append(f"LMTD kök bulma başarısız oldu: {exc}. Sonuç geçersiz kabul edilmelidir.")

        T_hot_out = T_hot_in - (q_found / C_h)
        T_cold_out = T_cold_in + (q_found / C_c)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        q_max = C_min * (T_hot_in - T_cold_in)
        epsilon = q_found / q_max if q_max > 0 else 0.0
        NTU = (self.U * self.A) / C_min if C_min > 0 else 0.0

        phase_warnings_lmtd = self._check_phase_change(T_hot_in, T_cold_in, T_hot_out, T_cold_out)
        for pw in phase_warnings_lmtd:
            _append_unique(warnings, pw)

        return {
            "Method": "LMTD Iteration",
            "Source": source,
            "Q [W]": q_found,
            "T_hot_in [C]": T_hot_in,
            "T_cold_in [C]": T_cold_in,
            "T_hot_out [C]": T_hot_out,
            "T_cold_out [C]": T_cold_out,
            "epsilon": epsilon,
            "NTU": NTU,
            "C_r": C_min / C_max if C_max > 0 else 0.0,
            "status": "warning" if status == "ok" and warnings else status,
            "warnings": warnings,
        }

    def solve_custom_lmtd(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float):
        """
        Kendi (Custom) LMTD Çözücümüz.
        Epsilon-NTU yerine, çıkış sıcaklığını tahmin ederek Q_lmtd = Q_gerçek olana kadar
        Brent metodu ile LMTD iterasyonu yapar.
        """
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)

        Q_max = C_min * (T_hot_in - T_cold_in)

        max_eps = C_min / (C_h + C_c) if self.flow_type == "parallel" else 0.999
        warnings: list[str] = []

        def objective(eps):
            Q = eps * Q_max
            T_h_out = T_hot_in - Q / C_h
            T_c_out = T_cold_in + Q / C_c

            dt1, dt2 = self._terminal_temperature_differences(T_hot_in, T_cold_in, T_h_out, T_c_out)

            if dt1 <= 0 or dt2 <= 0:
                return 1e9  # Fizik dışı sıcaklık çakışması

            LMTD = dt1 if abs(dt1 - dt2) < 1e-06 else (dt1 - dt2) / np.log(dt1 / dt2)

            F = self._calc_lmtd_F(T_hot_in, T_cold_in, T_h_out, T_c_out, C_h, C_c, warnings=warnings)

            Q_lmtd = self.U * self.A * LMTD * F
            return Q - Q_lmtd

        try:
            # Kök bulma
            eps_found = opt.brentq(objective, 1e-5, max_eps - 1e-5)
            Q_found = eps_found * Q_max
            T_h_out = T_hot_in - Q_found / C_h
            T_c_out = T_cold_in + Q_found / C_c

            phase_warnings_clmtd = self._check_phase_change(T_hot_in, T_cold_in, T_h_out, T_c_out)
            for pw in phase_warnings_clmtd:
                _append_unique(warnings, pw)

            return {
                "Method": "LMTD Iteration",
                "Source": "custom",
                "Q [W]": Q_found,
                "T_hot_in [C]": T_hot_in,
                "T_cold_in [C]": T_cold_in,
                "T_hot_out [C]": T_h_out,
                "T_cold_out [C]": T_c_out,
                "epsilon": eps_found,
                "NTU": (self.U * self.A) / C_min if C_min > 0 else 0.0,
                "C_r": C_min / C_max if C_max > 0 else 0.0,
                "status": "warning" if warnings else "ok",
                "warnings": warnings,
            }
        except Exception as exc:
            # İterasyon çakarsa NTU'ya düş (yedek güvenlik)
            result = self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="custom")
            result["Method"] = "LMTD Iteration"
            result["Source"] = "custom-fallback-NTU"
            result["status"] = "fallback"
            result.setdefault("warnings", []).append(f"Custom LMTD çözücü yakınsamadı; NTU sonucuna düşüldü: {exc}")
            return result

    def solve_condenser(self, m_hot: float, m_cold: float, T_sat: float, T_cold_in: float, h_fg: float | None = None):
        """Yoğuşturucu (kondenser): sıcak akışkan T_sat'de yoğuşur (C_h → ∞, Cr=0).

        ε = 1 - exp(-NTU), NTU = U·A / C_cold. Gizli ısı kapasitesi ile sınırlanır.
        """
        h_fg = h_fg or self.hot_fluid.h_fg
        if h_fg is None or h_fg <= 0:
            raise InvalidInputError("Kondenser çözümü için gizli ısı (h_fg) gereklidir.")
        C_cold = _require_positive("Soğuk akışkan cp", self.cold_fluid.cp) * m_cold
        Q_max = m_hot * h_fg
        NTU = (self.U * self.A) / C_cold
        epsilon = 1.0 - np.exp(-NTU)
        Q = epsilon * C_cold * (T_sat - T_cold_in)
        Q = min(Q, Q_max)
        T_cold_out = T_cold_in + Q / C_cold
        return {
            "Method": "Kondenser (Cr=0)",
            "Source": "custom",
            "Q [W]": Q,
            "epsilon": epsilon,
            "T_hot_in [C]": T_sat,
            "T_cold_in [C]": T_cold_in,
            "T_hot_out [C]": T_sat,
            "T_cold_out [C]": T_cold_out,
            "NTU": NTU,
            "C_r": 0.0,
            "Q_max [W]": Q_max,
            "status": "warning" if Q_max <= Q else "ok",
            "warnings": (["Gizli ısı kapasitesi sınırına ulaşıldı; tam yoğuşma olmayabilir."] if Q_max <= Q else []),
        }

    def solve_evaporator(self, m_hot: float, m_cold: float, T_hot_in: float, T_sat: float, h_fg: float | None = None):
        """Buharlaştırıcı (evaporatör): soğuk akışkan T_sat'de buharlaşır (C_c → ∞, Cr=0)."""
        h_fg = h_fg or self.cold_fluid.h_fg
        if h_fg is None or h_fg <= 0:
            raise InvalidInputError("Evaporatör çözümü için gizli ısı (h_fg) gereklidir.")
        C_hot = _require_positive("Sıcak akışkan cp", self.hot_fluid.cp) * m_hot
        Q_max = m_cold * h_fg
        NTU = (self.U * self.A) / C_hot
        epsilon = 1.0 - np.exp(-NTU)
        Q = epsilon * C_hot * (T_hot_in - T_sat)
        Q = min(Q, Q_max)
        T_hot_out = T_hot_in - Q / C_hot
        return {
            "Method": "Evaporatör (Cr=0)",
            "Source": "custom",
            "Q [W]": Q,
            "epsilon": epsilon,
            "T_hot_in [C]": T_hot_in,
            "T_cold_in [C]": T_sat,
            "T_hot_out [C]": T_hot_out,
            "T_cold_out [C]": T_sat,
            "NTU": NTU,
            "C_r": 0.0,
            "Q_max [W]": Q_max,
            "status": "warning" if Q_max <= Q else "ok",
            "warnings": (["Gizli ısı kapasitesi sınırına ulaşıldı; tam buharlaşma olmayabilir."] if Q_max <= Q else []),
        }

    def solve_segmented(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, n_segments: int = 10):
        """1D Sayısal Dilimli (Discretized Finite-Volume) ε-NTU Çözücüsü.

        Eşanjör yüzeyini n_segments eşit dilime (ΔA = A / n) böler.
        Her dilimde yerel ΔNTU ve yerel Cr üzerinden segment etkinliği ε_i
        ve aktarılan ısı ΔQ_i hesaplanarak adım adım entegre edilir.
        Ters akışta (counterflow) iteratif shoot/bisection integrasyonu uygulanır.
        """
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        Cr = C_min / C_max if C_max > 0 else 1.0

        n_segments = max(2, int(n_segments))
        dA = self.A / n_segments
        dNTU = (self.U * dA) / C_min
        eps_seg = self._segment_effectiveness(dNTU, Cr)

        warnings = []
        phase_warns = self._check_phase_change(T_hot_in, T_cold_in)
        for pw in phase_warns:
            _append_unique(warnings, pw)

        if self.flow_type == "parallel":
            # Paralel akış: İki akışkan da segment 0'dan başlar
            T_h = T_hot_in
            T_c = T_cold_in
            T_h_list = [T_h]
            T_c_list = [T_c]
            Q_total = 0.0
            for _ in range(n_segments):
                dQ = eps_seg * C_min * (T_h - T_c)
                dQ = max(0.0, dQ)
                Q_total += dQ
                T_h -= dQ / C_h
                T_c += dQ / C_c
                T_h_list.append(T_h)
                T_c_list.append(T_c)
            t_ho = T_h
            t_co = T_c
        else:
            # Ters akış veya çapraz akış:
            # Soğuk çıkış sıcaklığını tahmin eden kök bulucu
            def residual(t_cold_out_guess):
                T_h = T_hot_in
                T_c = t_cold_out_guess
                for _ in range(n_segments):
                    dQ = eps_seg * C_min * max(0.0, T_h - T_c)
                    T_h -= dQ / C_h
                    T_c -= dQ / C_c
                return T_c - T_cold_in

            try:
                t_co_found = opt.brentq(residual, T_cold_in + 1e-4, T_hot_in - 1e-4)
                T_h = T_hot_in
                T_c = t_co_found
                T_h_list = [T_h]
                T_c_list = [T_c]
                Q_total = 0.0
                for _ in range(n_segments):
                    dQ = eps_seg * C_min * max(0.0, T_h - T_c)
                    Q_total += dQ
                    T_h -= dQ / C_h
                    T_c -= dQ / C_c
                    T_h_list.append(T_h)
                    T_c_list.append(T_c)
                t_ho = T_h
                t_co = t_co_found
            except Exception:
                res = self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="custom")
                t_ho = res["T_hot_out [C]"]
                t_co = res["T_cold_out [C]"]
                Q_total = res["Q [W]"]
                T_h_list = [T_hot_in + (t_ho - T_hot_in) * (i / n_segments) for i in range(n_segments + 1)]
                T_c_list = [T_cold_in + (t_co - T_cold_in) * (i / n_segments) for i in range(n_segments + 1)]
                warnings.append("Segmentli sayısal çözücü kök bulamadı; standart NTU profiline düşüldü.")

        q_max = C_min * (T_hot_in - T_cold_in)
        epsilon_total = Q_total / q_max if q_max > 0 else 0.0
        NTU_total = (self.U * self.A) / C_min

        T_h_mid = float(np.mean(T_h_list))
        T_c_mid = float(np.mean(T_c_list))

        return {
            "Method": "Epsilon-NTU (Segmented)",
            "Source": f"custom-{n_segments}seg",
            "Q [W]": float(Q_total),
            "epsilon": float(epsilon_total),
            "T_hot_in [C]": T_hot_in,
            "T_cold_in [C]": T_cold_in,
            "T_hot_out [C]": float(t_ho),
            "T_cold_out [C]": float(t_co),
            "NTU": float(NTU_total),
            "C_r": Cr,
            "n_segments": n_segments,
            "T_h_mid [C]": round(T_h_mid, 1),
            "T_c_mid [C]": round(T_c_mid, 1),
            "T_h_profile": [round(t, 2) for t in T_h_list],
            "T_c_profile": [round(t, 2) for t in T_c_list],
            "status": "warning" if warnings else "ok",
            "warnings": warnings,
        }

    def _segment_effectiveness(self, NTU: float, Cr: float) -> float:
        """ε for a single segment based on flow type."""
        if self.flow_type == "parallel":
            e = (1 - np.exp(-NTU * (1 + Cr))) / (1 + Cr) if Cr >= 0 else 1.0
        elif self.flow_type == "counter":
            e = (1 - np.exp(-NTU * (1 - Cr))) / (1 - Cr * np.exp(-NTU * (1 - Cr))) if Cr < 1.0 else NTU / (1 + NTU)
        elif self.flow_type == "cross_unmixed":
            e = 1 - np.exp(1 / Cr * NTU**0.22 * (np.exp(-Cr * NTU**0.78) - 1)) if Cr > 0 else 1 - np.exp(-NTU)
        elif self.flow_type == "cross_mixed_unmixed":
            e = 1 / Cr * (1 - np.exp(-Cr * (1 - np.exp(-NTU)))) if Cr > 0 else 1 - np.exp(-NTU)
        else:
            e = 0.0
        return max(0.0, min(1.0, float(e)))

    def calculate_actual_performance(
        self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, T_hot_out: float, T_cold_out: float
    ):
        """Kullanıcı çıkış sıcaklıklarını verdiğinde gerçek Q'yu hesaplar."""
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        warnings = []

        Q_hot_side = C_h * (T_hot_in - T_hot_out)
        Q_cold_side = C_c * (T_cold_out - T_cold_in)
        balance_ref = max(abs(Q_hot_side), abs(Q_cold_side), 1e-12)
        balance_error_fraction = abs(Q_hot_side - Q_cold_side) / balance_ref

        # Gerçek Q (ortalama alarak veya enerji kaybı hesabı yaparak)
        Q_avg = (Q_hot_side + Q_cold_side) / 2.0

        Q_max = C_min * (T_hot_in - T_cold_in)

        epsilon_actual = Q_avg / Q_max if Q_max > 0 else 0
        if Q_hot_side < 0 or Q_cold_side < 0:
            warnings.append(
                "Ölçülen çıkış sıcaklıkları negatif ısı transferi üretiyor; performans sonucu fiziksel değildir."
            )
        if balance_error_fraction > ENERGY_BALANCE_WARNING_FRACTION:
            warnings.append(
                f"Enerji dengesi sapmasi %{balance_error_fraction * 100:.2f}; "
                f"sicak ve soguk taraf Q farki %{ENERGY_BALANCE_WARNING_FRACTION * 100:.1f} esigini asiyor."
            )
        if epsilon_actual < 0 or epsilon_actual > 1:
            warnings.append(
                "Gerçekleşen effectiveness 0-1 aralığı dışında; çıkış sıcaklıkları veya debiler tutarsız olabilir."
            )

        # LMTD ile Gerçek U Gereksinimi
        dt1, dt2 = self._terminal_temperature_differences(T_hot_in, T_cold_in, T_hot_out, T_cold_out)

        try:
            if dt1 <= 0 or dt2 <= 0:
                raise InvalidInputError("Invalid terminal temperature difference")
            LMTD = dt1 if abs(dt1 - dt2) < 1e-06 else (dt1 - dt2) / np.log(dt1 / dt2)

            F = self._calc_lmtd_F(T_hot_in, T_cold_in, T_hot_out, T_cold_out, C_h, C_c, warnings=warnings)

            U_required = Q_avg / (self.A * LMTD * F) if (self.A * LMTD * F) > 0 else 0
        except Exception as exc:
            LMTD = 0
            U_required = 0
            F = 1.0
            warnings.append(f"LMTD/U_required hesaplanamadı: {exc}")

        return {
            "Q_hot [W]": Q_hot_side,
            "Q_cold [W]": Q_cold_side,
            "Q_avg [W]": Q_avg,
            "energy_balance_error_fraction": balance_error_fraction,
            "epsilon_actual": epsilon_actual,
            "U_required": U_required,
            "LMTD": LMTD,
            "F": F,
            "status": "warning" if warnings else "ok",
            "warnings": warnings,
        }

    def _nusselt_internal(
        self,
        Re: float,
        Pr: float,
        n_factor: float,
        laminar_nu: float,
        side_name: str,
        warnings: list[str],
        gz: float | None = None,
    ) -> float:
        Re = _require_positive(f"{side_name} Reynolds", Re)
        Pr = _require_positive(f"{side_name} Prandtl", Pr)
        if Re <= 2300:
            if LAMINAR_ENTRANCE_MODEL and gz is not None and gz > 0:
                nu_lam = laminar_nu + 0.0668 * gz / (1.0 + 0.04 * gz ** (2.0 / 3.0))
                warnings.append(
                    f"{side_name}: laminer akista termal giriş bölgesi (Hausen/Graetz) uygulandı: "
                    f"Gz={gz:.1f}, Nu={nu_lam:.2f}."
                )
                return nu_lam
            warnings.append(
                f"{side_name}: laminer akista Nu={laminar_nu:.2f} sabit sinir kosulu varsayimiyla kullanildi."
            )
            return laminar_nu
        if Re < 10000:
            warnings.append(
                f"{side_name}: Re={Re:.0f} geçiş bölgesinde; Gnielinski korelasyonu yaklaşık olarak kullanıldı."
            )
            try:
                fd = (0.79 * np.log(Re) - 1.64) ** -2
                return ht.conv_internal.turbulent_Gnielinski(Re=Re, Pr=Pr, fd=fd)
            except Exception as exc:
                warnings.append(f"{side_name}: Gnielinski uygulanamadi; Dittus-Boelter yedegi kullanildi: {exc}")
                return 0.023 * (Re**0.8) * (Pr**n_factor)
        if Pr < GNIELINSKI_PR_RANGE[0] or Pr > GNIELINSKI_PR_RANGE[1]:
            warnings.append(f"{side_name}: Pr={Pr:.3g} Gnielinski tipik geçerlilik aralığı dışında.")
        try:
            fd = (0.79 * np.log(Re) - 1.64) ** -2
            return ht.conv_internal.turbulent_Gnielinski(Re=Re, Pr=Pr, fd=fd)
        except Exception as exc:
            warnings.append(f"{side_name}: Gnielinski uygulanamadi; Dittus-Boelter yedegi kullanildi: {exc}")
            return 0.023 * (Re**0.8) * (Pr**n_factor)

    def calculate_geometric_U(self, geom, m_hot: float, m_cold: float, hot_is_tube: bool = False):
        """
        Geometrik ölçülere göre Toplam Isı Transfer Katsayısını (U) hesaplar.
        Tüm akış tiplerini destekler.

        *geom* may be a dict or a :class:`GeometryInput` instance.
        """
        from model_types import GeometryInput

        if isinstance(geom, GeometryInput):
            geom = geom.to_dict()
        D_o = geom["D_o"]
        D_i = geom["D_i"]
        L = geom["L"]
        # Matris boru yerleşimi desteği (N_T x N_L)
        N_T_in = geom.get("N_transverse") or geom.get("N_T")
        N_L_in = geom.get("N_rows") or geom.get("N_L") or geom.get("N_longitudinal")
        if N_T_in and N_L_in and float(N_T_in) > 0 and float(N_L_in) > 0:
            N = int(float(N_T_in) * float(N_L_in))
        else:
            N = geom.get("N_tubes", 1)
        k_wall = geom["k_wall"]
        R_f_i = float(geom.get("R_f_i", 0.0) or 0.0)
        R_f_o = float(geom.get("R_f_o", 0.0) or 0.0)
        self.shell_passes = int(geom.get("shell_passes", self.shell_passes) or 1)
        self.tube_passes = int(geom.get("tube_passes", self.tube_passes) or 2)
        self.baffle_cut = float(geom.get("baffle_cut", self.baffle_cut) or 0.25)
        warnings: list[str] = []
        if R_f_i < 0 or R_f_o < 0:
            raise InvalidInputError("Fouling dirençleri negatif olamaz.")

        D_o = _require_positive("Dış çap", D_o)
        D_i = _require_positive("İç çap", D_i)
        L = _require_positive("Boru uzunluğu", L)
        N = _require_positive("Boru sayısı", N)
        k_wall = _require_positive("Duvar ısıl iletkenliği", k_wall)
        if D_i >= D_o:
            raise InvalidGeometryError("Dış çap iç çaptan büyük olmalıdır.")
        _require_positive("Sıcak akışkan debisi", m_hot)
        _require_positive("Soğuk akışkan debisi", m_cold)

        # İç Akışkan ve Dış Akışkan Seçimi
        fluid_in = self.hot_fluid if hot_is_tube else self.cold_fluid
        fluid_out = self.cold_fluid if hot_is_tube else self.hot_fluid
        m_in = m_hot if hot_is_tube else m_cold
        m_out = m_cold if hot_is_tube else m_hot

        if fluid_in.mu is None or fluid_in.k_cond is None:
            raise FluidPropertyError(
                f"İç akışkan ({fluid_in.name}) için Viskozite ve Isıl İletkenlik değeri gereklidir!"
            )
        if fluid_out.mu is None or fluid_out.k_cond is None:
            raise FluidPropertyError(
                f"Dış akışkan ({fluid_out.name}) için Viskozite ve Isıl İletkenlik değeri gereklidir!"
            )

        if not fluid_in.density:
            raise FluidPropertyError(
                f"İç akışkan ({fluid_in.name}) için Yoğunluk değeri hesaplanamıyor. Manuel akışkansa yoğunluğu girmelisiniz."
            )
        if not fluid_out.density:
            raise FluidPropertyError(
                f"Dış akışkan ({fluid_out.name}) için Yoğunluk değeri hesaplanamıyor. Manuel akışkansa yoğunluğu girmelisiniz."
            )

        # --- İÇ TAŞINIM (h_i) ---
        # Çok geçişli eşanjörde geçiş başına boru sayısı (N / tube_passes)
        n_passes = max(1, self.tube_passes)
        n_tubes_per_pass = max(1.0, float(N) / float(n_passes))
        A_c_i = n_tubes_per_pass * (np.pi * D_i**2) / 4.0
        v_in = m_in / (fluid_in.density * A_c_i)
        if FLUIDS_AVAILABLE:
            Re_i = fluids_core.Reynolds(V=v_in, D=D_i, rho=fluid_in.density, mu=fluid_in.mu)
            Pr_i = fluids_core.Prandtl(Cp=fluid_in.cp, mu=fluid_in.mu, k=fluid_in.k_cond)
        else:
            Re_i = (fluid_in.density * v_in * D_i) / fluid_in.mu
            Pr_i = (fluid_in.cp * fluid_in.mu) / fluid_in.k_cond

        n_factor = 0.3 if hot_is_tube else 0.4
        gz_i = Re_i * Pr_i * (D_i / L)
        Nu_i = self._nusselt_internal(Re_i, Pr_i, n_factor, 3.66, "İç taraf", warnings, gz=gz_i)
        h_i = (Nu_i * fluid_in.k_cond) / D_i

        # İki-fazlı mod (kondenser/evaporatör): iç tarafta faz değişimi kontrolü
        is_two_phase_in = bool(geom.get("is_two_phase_tube", False)) or (
            hot_is_tube and getattr(self.hot_fluid, "h_fg", None) and not self.hot_fluid.single_phase
        )
        h_tp_in = float(geom.get("h_two_phase_tube", 0.0) or geom.get("h_tp_tube", 0.0) or 0.0)
        if is_two_phase_in:
            h_i = h_tp_in if h_tp_in > 0 else 4500.0
            warnings.append(f"İç taraf iki-fazlı mod: h_i = {h_i:.0f} W/m²K (faz değişimi taşınım katsayısı) uygulandı.")

        # --- DUVAR İLETİM DİRENCİ (R_wall) ---
        R_wall = np.log(D_o / D_i) / (2 * np.pi * k_wall * L * N)

        # --- DIŞ TAŞINIM (h_o) ---
        if self.exchanger_type == EXCHANGER_TYPE_FINNED:
            pitch = geom.get("pitch", D_o * 2.0)
            pitch = _require_positive("Transverse pitch", pitch)
            if pitch <= D_o:
                raise InvalidGeometryError("Transverse pitch dış çaptan büyük olmalıdır.")
            n_transverse = float(N_T_in) if N_T_in and float(N_T_in) > 0 else max(1.0, np.sqrt(N))
            W_estimate = n_transverse * pitch
            # Kanat tıkanma etkisi (fin blockage) hesaba katılır
            if geom.get("is_finned", False):
                h_b_val = float(geom.get("fin_height", 0.0) or 0.0)
                t_f_val = float(geom.get("fin_thickness", 0.0) or 0.0)
                n_f_val = float(geom.get("fin_density", 0.0) or 0.0)
                fin_blockage = n_transverse * (2.0 * h_b_val * t_f_val * n_f_val)
                A_min = L * max(1e-6, W_estimate - n_transverse * D_o - fin_blockage)
            else:
                A_min = (W_estimate - n_transverse * D_o) * L
            A_min = max(A_min, 1e-6)
            v_out = m_out / (fluid_out.density * A_min)
            if FLUIDS_AVAILABLE:
                Re_o = fluids_core.Reynolds(V=v_out, D=D_o, rho=fluid_out.density, mu=fluid_out.mu)
                Pr_o = fluids_core.Prandtl(Cp=fluid_out.cp, mu=fluid_out.mu, k=fluid_out.k_cond)
            else:
                Re_o = (fluid_out.density * v_out * D_o) / fluid_out.mu
                Pr_o = (fluid_out.cp * fluid_out.mu) / fluid_out.k_cond

            if geom.get("is_finned", False):
                fin_density = _require_positive("Kanatçık yoğunluğu", geom["fin_density"])
                fin_thickness = _require_positive("Kanatçık kalınlığı", geom["fin_thickness"])
                h_b = _require_positive("Kanatçık yüksekliği", geom["fin_height"])
                k_fin = _require_positive("Kanatçık ısıl iletkenliği", geom["k_fin"])
                fin_type = geom.get("fin_type", "annular")
                s = (1.0 / fin_density) - fin_thickness
                if s <= 0:
                    raise InvalidGeometryError(
                        "Kanatçık aralığı pozitif olmalıdır; fin_density ve fin_thickness değerlerini kontrol edin."
                    )
                if not (BRIGGS_YOUNG_RE_RANGE[0] <= Re_o <= BRIGGS_YOUNG_RE_RANGE[1]):
                    warnings.append(
                        f"Kanatçık dış taşınım: Briggs-Young korelasyonu Re = {Re_o:.0f} için geçerlilik aralığı dışında (1100 ≤ Re ≤ 18000)."
                    )
                try:
                    Nu_o = (
                        0.134
                        * (Re_o**0.681)
                        * (Pr_o**0.33)
                        * ((s / h_b) ** 0.2)
                        * ((s / geom["fin_thickness"]) ** 0.1134)
                    )
                    h_o = (Nu_o * fluid_out.k_cond) / D_o
                    eta_fin = _fin_efficiency(
                        fin_type,
                        h_o,
                        k_fin,
                        fin_thickness,
                        h_b,
                        D_o,
                        pitch=pitch,
                        pitch_parallel=geom.get("pitch_parallel", pitch),
                    )
                except Exception as exc:
                    warnings.append(f"Kanatçık korelasyonu uygulanamadı; Grimison tube-bank fallback: {exc}")
                    eta_fin = 1.0
                    try:
                        Nu_o = ht.conv_tube_bank.Nu_Grimison_tube_bank(
                            Re=Re_o,
                            Pr=Pr_o,
                            Do=D_o,
                            tube_rows=max(1, int(np.sqrt(N))),
                            pitch_parallel=geom.get("pitch_parallel", pitch),
                            pitch_normal=pitch,
                        )
                    except Exception:
                        Nu_o = 0.33 * (Re_o**0.6) * (Pr_o**0.33)
                    h_o = (Nu_o * fluid_out.k_cond) / D_o
            else:
                eta_fin = 1.0
                tube_rows = max(1, int(np.sqrt(N)))
                pitch_parallel = geom.get("pitch_parallel", pitch)
                try:
                    Nu_o = ht.conv_tube_bank.Nu_Grimison_tube_bank(
                        Re=Re_o,
                        Pr=Pr_o,
                        Do=D_o,
                        tube_rows=tube_rows,
                        pitch_parallel=pitch_parallel,
                        pitch_normal=pitch,
                    )
                    if Nu_o <= 0:
                        raise ConvergenceError("Grimison sıfır/negatif Nu döndürdü")
                except Exception:
                    warnings.append(
                        f"Dış taşınım: Grimison tube-bank uygulanamadı; "
                        f"Zukauskas-style fallback kullanıldı (Re={Re_o:.0f})."
                    )
                    arrangement = geom.get("tube_arrangement", "staggered")
                    row_corr = ht.conv_tube_bank.Zukauskas_tube_row_correction(
                        tube_rows=tube_rows, staggered=(arrangement == "staggered"), Re=Re_o
                    )
                    if Re_o < 1000:
                        C, m = (0.52, 0.5) if arrangement == "staggered" else (0.27, 0.63)
                    else:
                        C, m = (0.35, 0.6) if arrangement == "staggered" else (0.021, 0.84)
                    Nu_o = C * (Re_o**m) * (Pr_o**0.36) * row_corr
                h_o = (Nu_o * fluid_out.k_cond) / D_o
        elif self.exchanger_type == EXCHANGER_TYPE_SHELL:
            # Gövde-Boru TEMA — annulus yaklaşımı (P5'te Kern metodu ile değiştirilecek)
            # Kern Metodu (gövde-boru TEMA)
            D_shell = geom.get("D_shell", D_o * 1.5)
            D_shell = _require_positive("Gövde iç çapı", D_shell)
            if D_shell <= D_o:
                raise InvalidGeometryError("Gövde iç çapı boru dış çapından büyük olmalıdır.")
            pitch = geom.get("pitch", D_o * 1.25)
            if pitch <= D_o:
                pitch = D_o * 1.25
            baffle_spacing = geom.get("baffle_spacing", L * 0.2)
            baffle_spacing = _require_positive("Deflektör aralığı", baffle_spacing)
            layout_angle = geom.get("tube_layout_angle", "30")
            C_prime = pitch - D_o  # clearance
            A_shell = D_shell * baffle_spacing * C_prime / pitch
            A_shell = max(A_shell, 1e-6)
            G_s = m_out / A_shell  # shell-side mass velocity
            if layout_angle in ("30", "60"):
                D_e = (2.0 * np.sqrt(3.0) * pitch**2 - np.pi * D_o**2) / (np.pi * D_o)
            else:
                D_e = (4.0 * pitch**2 - np.pi * D_o**2) / (np.pi * D_o)
            D_e = max(D_e, 1e-6)
            if FLUIDS_AVAILABLE:
                Re_o = fluids_core.Reynolds(V=G_s / fluid_out.density, D=D_e, rho=fluid_out.density, mu=fluid_out.mu)
                Pr_o = fluids_core.Prandtl(Cp=fluid_out.cp, mu=fluid_out.mu, k=fluid_out.k_cond)
            else:
                Re_o = (G_s * D_e) / fluid_out.mu
                Pr_o = (fluid_out.cp * fluid_out.mu) / fluid_out.k_cond
            # Kern heat transfer correlation
            Nu_o = 0.36 * Re_o**0.55 * Pr_o ** (1.0 / 3.0) if Re_o > 2000 else 0.5 * Re_o**0.5 * Pr_o ** (1.0 / 3.0)
            # Faz F3: opsiyonel Bell-Delaware (rigorous rating)
            if USE_BELL_DELAWARE and geom.get("h_o_method", "bell_delaware") != "kern":
                try:
                    h_id_nu = 0.36 * Re_o**0.55 * Pr_o ** (1.0 / 3.0)
                    h_o_bd, j_factors = _bell_delaware_shell_h(
                        h_id_nu,
                        fluid_out.k_cond,
                        D_o,
                        D_shell,
                        self.baffle_cut,
                        int(N),
                        L,
                        baffle_spacing,
                        Re_shell=Re_o,
                    )
                    h_o = h_o_bd
                    warnings.append(
                        "Gövde-boru Bell-Delaware (rigorous): h_id="
                        f"{h_id_nu * fluid_out.k_cond / max(D_e, 1e-6):.2f} W/m²K, "
                        f"J_c={j_factors['J_c']:.3f}, J_l={j_factors['J_l']:.3f}, "
                        f"J_b={j_factors['J_b']:.3f}, J_s={j_factors['J_s']:.2f}, J_r={j_factors['J_r']:.2f}"
                    )
                except Exception as exc:
                    warnings.append(f"Bell-Delaware uygulanamadı; Kern sonucu kullanıldı: {exc}")
                    h_o = (Nu_o * fluid_out.k_cond) / D_e
            else:
                h_o = (Nu_o * fluid_out.k_cond) / D_e
            eta_fin = 1.0
            warnings.append(f"Gövde-boru Kern metodu: Re_s={Re_o:.0f}, Nu_s={Nu_o:.2f}, D_e={D_e:.4f}m")
            if self.baffle_cut < 0.15 or self.baffle_cut > 0.45:
                _append_unique(
                    warnings,
                    f"Deflektör kesim oranı (baffle cut) = {self.baffle_cut:.2f} TEMA önerilen aralığı (%15–%45) dışında. "
                    "Kern metodu bu etkiyi doğrudan modellemez; Bell-Delaware yöntemi ile doğrulama önerilir.",
                )
            if self.shell_passes > 1:
                _append_unique(
                    warnings,
                    f"Gövde geçiş sayısı = {self.shell_passes} (E/F-shell). Bowman F-faktörü yalnızca tek gövde geçişli "
                    "(1-N) konfigürasyon için geçerlidir; çok gövde geçişli tasarımlarda seri eşanjör/ayrı modelleme kullanın.",
                )
        else:
            # Çift Borulu — annulus tarafı
            D_shell = geom.get("D_shell", D_o * 1.5)
            D_shell = _require_positive("Gövde iç çapı", D_shell)
            if D_shell <= D_o:
                raise InvalidGeometryError("Gövde iç çapı boru dış çapından büyük olmalıdır.")
            D_h_annulus = D_shell - D_o
            A_c_o = (np.pi * (D_shell**2 - D_o**2)) / 4.0
            A_c_o = max(A_c_o, 1e-6)
            v_out = m_out / (fluid_out.density * A_c_o)
            if FLUIDS_AVAILABLE:
                Re_o = fluids_core.Reynolds(V=v_out, D=D_h_annulus, rho=fluid_out.density, mu=fluid_out.mu)
                Pr_o = fluids_core.Prandtl(Cp=fluid_out.cp, mu=fluid_out.mu, k=fluid_out.k_cond)
            else:
                Re_o = (fluid_out.density * v_out * D_h_annulus) / fluid_out.mu
                Pr_o = (fluid_out.cp * fluid_out.mu) / fluid_out.k_cond

            n_factor_out = 0.4 if hot_is_tube else 0.3
            r_star = D_o / D_shell

            if Re_o <= 2300:
                if r_star <= 0 or r_star >= 1:
                    Nu_o = 4.86
                    warnings.append(f"Dış taraf annulus laminer: r*={r_star:.3f} sınır dışı, Nu=4.86 alındı.")
                else:
                    Nu_o = 3.66 + 1.2 * (r_star**-0.8)
                warnings.append(f"Dış taraf annulus laminer: Nu_i={Nu_o:.2f} (r*={r_star:.3f}, iç çeper ısıtmalı)")
            elif Re_o < 10000:
                warnings.append(f"Dış taraf annulus: Re={Re_o:.0f} geçiş bölgesinde; Gnielinski yaklaşık kullanıldı.")
                try:
                    fd = (0.79 * np.log(Re_o) - 1.64) ** -2
                    Nu_o = ht.conv_internal.turbulent_Gnielinski(Re=Re_o, Pr=Pr_o, fd=fd)
                except Exception:
                    Nu_o = 0.023 * (Re_o**0.8) * (Pr_o**n_factor_out)
            else:
                if Pr_o < 0.7 or Pr_o > 160:
                    warnings.append(f"Dış taraf annulus: Pr={Pr_o:.3g} Gnielinski tipik aralık dışında.")
                try:
                    fd = (0.79 * np.log(Re_o) - 1.64) ** -2
                    Nu_o = ht.conv_internal.turbulent_Gnielinski(Re=Re_o, Pr=Pr_o, fd=fd)
                except Exception as exc:
                    warnings.append(f"Dış taraf annulus: Gnielinski uygulanamadı; Dittus-Boelter yedeği: {exc}")
                    Nu_o = 0.023 * (Re_o**0.8) * (Pr_o**n_factor_out)
            h_o = (Nu_o * fluid_out.k_cond) / D_h_annulus
            eta_fin = 1.0

        # İki-fazlı mod: dış tarafta faz değişimi kontrolü
        is_two_phase_out = bool(geom.get("is_two_phase_shell", False)) or (
            not hot_is_tube and getattr(self.hot_fluid, "h_fg", None) and not self.hot_fluid.single_phase
        )
        h_tp_out = float(geom.get("h_two_phase_shell", 0.0) or geom.get("h_tp_shell", 0.0) or 0.0)
        if is_two_phase_out:
            h_o = h_tp_out if h_tp_out > 0 else 3500.0
            warnings.append(f"Dış taraf iki-fazlı mod: h_o = {h_o:.0f} W/m²K (faz değişimi taşınım katsayısı) uygulandı.")

        # --- Sieder-Tate çeper viskozite düzeltmesi (Faz B1) ---
        # h *= (mu_b / mu_w)^0.14. Çeper sıcaklığı, film dirençlerine göre ağırlıklı
        # ortalama sıcaklıkla sabit nokta iterasyonuyla tahmin edilir.
        # Sadece mu(T) bağımlı akışkanlarda (CoolProp / IAPWS) uygulanır.
        if SIEDER_TATE_CORRECTION:
            T_in_ref = fluid_in.calc_temp_c
            T_out_ref = fluid_out.calc_temp_c
            if T_in_ref is not None and T_out_ref is not None:
                corr_in = 1.0
                corr_out = 1.0
                T_w = (T_in_ref + T_out_ref) / 2.0
                for _ in range(max(1, int(SIEDER_TATE_ITERATIONS))):
                    T_w = (h_i * T_in_ref + h_o * T_out_ref) / max(h_i + h_o, 1e-12)
                    mu_w_in = fluid_in.viscosity_at(T_w)
                    mu_w_out = fluid_out.viscosity_at(T_w)
                    corr_in = (fluid_in.mu / mu_w_in) ** 0.14 if (mu_w_in and fluid_in.mu) else 1.0
                    corr_out = (fluid_out.mu / mu_w_out) ** 0.14 if (mu_w_out and fluid_out.mu) else 1.0
                    corr_in = min(2.0, max(0.5, corr_in))
                    corr_out = min(2.0, max(0.5, corr_out))
                    h_i *= corr_in
                    h_o *= corr_out
                if abs(corr_in - 1.0) > 0.01 or abs(corr_out - 1.0) > 0.01:
                    _append_unique(
                        warnings,
                        f"Sieder-Tate çeper viskozite düzeltmesi uygulandı: "
                        f"h_i ×{corr_in:.3f}, h_o ×{corr_out:.3f} (T_w={T_w:.1f} °C).",
                    )

        A_i = np.pi * D_i * L * N
        A_o = np.pi * D_o * L * N

        if self.exchanger_type == EXCHANGER_TYPE_FINNED and geom.get("is_finned", False):
            fin_h = geom["fin_height"]
            fin_t = geom["fin_thickness"]
            fin_dens = geom["fin_density"]
            fin_type = geom.get("fin_type", "annular")
            N_fins_per_tube = fin_dens * L

            if fin_type == "plate" and geom.get("pitch") and geom.get("pitch_parallel"):
                p_t = geom["pitch"]
                p_l = geom["pitch_parallel"]
                A_fin_cell = max(0.0, 2.0 * (p_t * p_l - (np.pi * D_o**2) / 4.0))
                A_fin_total = N * N_fins_per_tube * A_fin_cell
            else:
                # Dairesel kanat (annular fin): 2 yüzey + uç alanı
                D_fin = D_o + 2.0 * fin_h
                A_fin_single = 2.0 * np.pi * fin_h * (D_o + fin_h) + np.pi * D_fin * fin_t
                A_fin_total = N * N_fins_per_tube * A_fin_single

            fraction_bare = max(0.0, 1.0 - fin_dens * fin_t)
            A_bare_total = A_o * fraction_bare
            A_total_out = A_bare_total + A_fin_total

            # Genel yüzey verimi (Overall surface efficiency): eta_o * A_total = A_bare + eta_fin * A_fin
            eta_o = (A_bare_total + eta_fin * A_fin_total) / max(A_total_out, 1e-12)
            eta_o = max(0.01, min(1.0, float(eta_o)))
        else:
            A_total_out = A_o
            eta_o = 1.0
            A_bare_total = A_o
            A_fin_total = 0.0

        R_contact_total = 0.0
        if self.exchanger_type == EXCHANGER_TYPE_FINNED and geom.get("is_finned", False):
            fin_style = (
                geom.get("ache_fin_type")
                or geom.get("fin_style")
                or geom.get("fin_attachment")
                or geom.get("api661_fin_type")
            )
            matched_key = None
            if fin_style:
                fin_style_str = str(fin_style).strip()
                if fin_style_str in API661_FIN_TYPES:
                    matched_key = fin_style_str
                else:
                    for k in API661_FIN_TYPES:
                        if (
                            fin_style_str.lower() in k.lower()
                            or k.lower().startswith(fin_style_str.lower())
                            or fin_style_str.lower().split()[0] == k.lower().split()[0]
                        ):
                            matched_key = k
                            break
            if matched_key:
                fin_info = API661_FIN_TYPES[matched_key]
                limit_t = fin_info["max_temp_c"]
                r_c = fin_info["contact_resistance"]
                R_contact_total = r_c / max(A_total_out, 1e-12)

                T_eval = fluid_in.calc_temp_c if hot_is_tube else fluid_out.calc_temp_c
                if T_eval is not None and T_eval > limit_t:
                    _append_unique(
                        warnings,
                        f"API 661 Uyarısı: '{matched_key}' kanat için izin verilen sürekli çalışma sıcaklığı "
                        f"{limit_t:.0f} °C'dir. Proses sıcaklığı ({T_eval:.1f} °C) sınırı aşıyor; "
                        "mekanik gevşeme ve ısıl temas kaybı riski!",
                    )

        R_i = 1.0 / (h_i * A_i)
        R_o = 1.0 / (h_o * A_total_out * eta_o) + R_contact_total
        R_f_i_total = R_f_i / A_i if R_f_i > 0 else 0.0
        R_f_o_total = R_f_o / A_total_out if R_f_o > 0 else 0.0

        U_A_total = 1.0 / (R_i + R_f_i_total + R_wall + R_f_o_total + R_o)

        self.U = U_A_total / A_total_out
        self.A = A_total_out

        # --- BASINÇ DÜŞÜŞÜ (ΔP) ---
        delta_p_tube = 0.0
        delta_p_shell = 0.0

        try:
            # Tube-side pressure drop (akış boyu L * tube_passes)
            if FLUIDS_AVAILABLE:
                f_i = fluids.friction_factor(Re=Re_i, eD=TUBE_WALL_ROUGHNESS / D_i)
            else:
                f_i = (0.79 * np.log(max(Re_i, 2300)) - 1.64) ** -2 if Re_i >= 2300 else 64.0 / max(Re_i, 1)
            L_flow_tube = L * max(1, self.tube_passes)
            delta_p_tube = f_i * (L_flow_tube / D_i) * (fluid_in.density * v_in**2 / 2.0)
            if Re_i < 2300:
                delta_p_tube *= 1.1  # approximate laminar correction for developing flow
            # Çok geçişli dönüş kafaları + nozul lokal kayıpları (Faz 2.2)
            if self.tube_passes > 1:
                delta_p_local = (
                    LOCAL_LOSS_VELOCITY_HEADS_PER_PASS * self.tube_passes * (fluid_in.density * v_in**2 / 2.0)
                )
                delta_p_tube += delta_p_local
        except Exception as exc:
            warnings.append(f"Boru içi basınç düşüşü hesaplanamadı: {exc}")

        try:
            if self.exchanger_type == EXCHANGER_TYPE_FINNED:
                N_tube_rows = max(1, int(np.sqrt(N)))
                if FLUIDS_AVAILABLE:
                    f_o = fluids.friction_factor(Re=max(Re_o, 1), eD=TUBE_WALL_ROUGHNESS / D_o)
                else:
                    f_o = (0.79 * np.log(max(Re_o, 2300)) - 1.64) ** -2 if Re_o >= 2300 else 64.0 / max(Re_o, 1)
                v_max = v_out  # already based on minimum free area
                if geom.get("is_finned", False):
                    s = (1.0 / geom["fin_density"]) - geom["fin_thickness"]
                    f_briggs = 37.86 * (max(Re_o, 1100) ** -0.316) * (geom.get("pitch", D_o * 2.0) / D_o) ** -0.927
                    delta_p_shell = f_briggs * N_tube_rows * fluid_out.density * v_max**2 / 2.0
                else:
                    delta_p_shell = 2.0 * f_o * N_tube_rows * fluid_out.density * v_max**2 / 2.0
            elif self.exchanger_type == EXCHANGER_TYPE_SHELL:
                N_b = max(1, int(L / baffle_spacing - 1))
                f_kern = np.exp(0.576 - 0.19 * np.log(max(Re_o, 1.0)))
                delta_p_shell = f_kern * G_s**2 * D_shell * (N_b + 1) / (2.0 * fluid_out.density * max(D_e, 1e-6))
                # Faz B2: gövde giriş/çıkış nozul basınç düşüşü
                # ΔP_nozzle = N_noz · K · ρ·v_noz²/2 (K = SHELL_NOZZLE_VELOCITY_HEADS)
                D_noz = float(geom.get("nozzle_diameter", 0.0) or 0.0)
                if D_noz <= 0:
                    D_noz = 0.4 * D_shell  # nozul çapı girilmediyse tahmini
                A_noz = np.pi * D_noz**2 / 4.0
                A_noz = max(A_noz, 1e-6)
                v_noz = m_out / (fluid_out.density * A_noz)
                delta_p_nozzle = (
                    SHELL_NOZZLE_COUNT * SHELL_NOZZLE_VELOCITY_HEADS * (fluid_out.density * v_noz**2 / 2.0)
                )
                delta_p_shell += delta_p_nozzle
                warnings.append(f"Gövde nozul ΔP: v_noz={v_noz:.2f} m/s, ΔP_nozzle={delta_p_nozzle:.0f} Pa eklendi.")
                # Faz 2.3: TEMA akış kaynaklı titreşim ön değerlendirmesi
                v_shell = G_s / fluid_out.density
                rho_v2 = fluid_out.density * v_shell**2
                if rho_v2 > TEMA_RHO_V2_LIMIT:
                    _append_unique(
                        warnings,
                        f"TEMA titreşim kontrolü: ρv² = {rho_v2:.0f} kg/(m·s²) > {TEMA_RHO_V2_LIMIT:.0f} limiti. "
                        "Giriş nozuluna impingement plate (çarptırma plakası) ekleyin veya nozul çapını büyütün.",
                    )
                max_span = MAX_UNSUPPORTED_SPAN_FACTOR * D_o
                if baffle_spacing > max_span:
                    _append_unique(
                        warnings,
                        f"TEMA desteklenmeyen boru boyu: baffle aralığı = {baffle_spacing*1000:.0f} mm > "
                        f"{max_span*1000:.0f} mm (limit). Titreşim riski — baffle aralığını düşürün.",
                    )
            elif self.exchanger_type == EXCHANGER_TYPE_DOUBLE:
                D_h_ann = geom.get("D_shell", D_o * 1.5) - D_o
                D_h_ann = max(D_h_ann, 1e-6)
                v_out = (m_out / fluid_out.density) / (np.pi * (D_shell**2 - D_o**2) / 4.0)
                if FLUIDS_AVAILABLE:
                    f_ann = fluids.friction_factor(Re=max(Re_o, 1), eD=TUBE_WALL_ROUGHNESS / D_h_ann)
                else:
                    f_ann = (0.79 * np.log(max(Re_o, 2300)) - 1.64) ** -2 if Re_o >= 2300 else 64.0 / max(Re_o, 1)
                delta_p_shell = f_ann * (L / D_h_ann) * (fluid_out.density * v_out**2 / 2.0)
        except Exception as exc:
            warnings.append(f"Dış taraf basınç düşüşü hesaplanamadı: {exc}")

        # --- POMPA / FAN GÜCÜ (Faz 2.1) ---
        pump_power_tube = 0.0
        pump_power_shell = 0.0
        try:
            vol_flow_tube = m_in / fluid_in.density
            eta_tube = self.fan_efficiency if fluid_in.density < 100.0 else self.pump_efficiency
            pump_power_tube = vol_flow_tube * delta_p_tube / eta_tube
        except Exception as exc:
            warnings.append(f"Boru tarafı pompa gücü hesaplanamadı: {exc}")
        try:
            vol_flow_shell = m_out / fluid_out.density
            eta_shell = self.fan_efficiency if fluid_out.density < 100.0 else self.pump_efficiency
            pump_power_shell = vol_flow_shell * delta_p_shell / eta_shell
        except Exception as exc:
            warnings.append(f"Gövde/kanat tarafı fan gücü hesaplanamadı: {exc}")

        return {
            "U": self.U,
            "A_total": self.A,
            "A_bare_total": A_bare_total,
            "A_fin_total": A_fin_total,
            "h_i": h_i,
            "h_o": h_o,
            "Re_i": Re_i,
            "Re_o": Re_o,
            "R_wall": R_wall,
            "R_f_i": R_f_i,
            "R_f_o": R_f_o,
            "R_f_i_total": R_f_i_total,
            "R_f_o_total": R_f_o_total,
            "eta_fin": eta_fin,
            "eta_o": eta_o,
            "delta_p_tube": delta_p_tube,
            "delta_p_shell": delta_p_shell,
            "pump_power_tube": pump_power_tube,
            "pump_power_shell": pump_power_shell,
            "shell_passes": self.shell_passes,
            "tube_passes": self.tube_passes,
            "baffle_cut": self.baffle_cut,
            "status": "warning" if warnings else "ok",
            "warnings": warnings,
        }

    def run_solvers(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float) -> list[dict]:
        """Dört çözücüyü de çalıştırıp bağımsız doğrulama (cross-check) listesi döndürür.

        [custom ε-NTU, custom LMTD, ht ε-NTU, ht LMTD]. UI'lardaki tekrarı ortadan kaldırır.
        """
        return [
            self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="custom"),
            self.solve_custom_lmtd(m_hot, m_cold, T_hot_in, T_cold_in),
            self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source="ht"),
            self.solve_lmtd(m_hot, m_cold, T_hot_in, T_cold_in, source="ht"),
        ]

    def solve_with_refinement(
        self,
        m_hot: float,
        m_cold: float,
        T_hot_in: float,
        T_cold_in: float,
        rebuild,
        max_iterations: int = 2,
        tol: float = 1.0,
    ):
        """Dört çözücüyü koşturup ortalama (midpoint) sıcaklıkta özellik iyileştirmesi yapar (Faz E1).

        *rebuild(T_hot_mid, T_cold_mid, m_hot, m_cold)*, belirtilen ortalama
        sıcaklıklarda eşanjörü ve U/A'yı yeniden kuran bir geri çağrı olmalı ve
        (m_hot, m_cold, hx) üçlüsünü döndürmelidir. Bu, masaüstü ve web
        arayüzlerindeki tekrarlanan 2-geçişli ortalama sıcaklık döngüsünü
        ortadan kaldırır.

        Döndürür: (m_hot, m_cold, self, crosscheck_results)
        """
        results = list(self.run_solvers(m_hot, m_cold, T_hot_in, T_cold_in))
        for _ in range(max_iterations):
            t_ho = results[0]["T_hot_out [C]"]
            t_co = results[0]["T_cold_out [C]"]
            if abs((T_hot_in + t_ho) / 2.0 - T_hot_in) < tol and abs((T_cold_in + t_co) / 2.0 - T_cold_in) < tol:
                break
            m_hot, m_cold, hx = rebuild((T_hot_in + t_ho) / 2.0, (T_cold_in + t_co) / 2.0, m_hot, m_cold)
            self.hot_fluid = hx.hot_fluid
            self.cold_fluid = hx.cold_fluid
            self.U = hx.U
            self.A = hx.A
            self.pump_efficiency = getattr(hx, "pump_efficiency", self.pump_efficiency)
            self.fan_efficiency = getattr(hx, "fan_efficiency", self.fan_efficiency)
            self.tube_passes = getattr(hx, "tube_passes", self.tube_passes)
            self.shell_passes = getattr(hx, "shell_passes", self.shell_passes)
            self.baffle_cut = getattr(hx, "baffle_cut", self.baffle_cut)
            results = list(hx.run_solvers(m_hot, m_cold, T_hot_in, T_cold_in))
        return m_hot, m_cold, self, results

    def cross_check(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float):
        """Dört farklı kombinasyonu hesaplar ve birbirleriyle kıyaslar."""
        res_ntu_custom, res_custom_lmtd, res_ntu_ht, res_lmtd_ht = self.run_solvers(m_hot, m_cold, T_hot_in, T_cold_in)

        print(f"| {'Method':<20} | {'Source':<10} | {'Q [W]':<15} | {'T_h_out [C]':<15} | {'T_c_out [C]':<15} |")
        print("-" * 86)

        results = [res_ntu_custom, res_ntu_ht, res_lmtd_ht]
        for r in results:
            print(
                f"| {r['Method']:<20} | {r['Source']:<10} | {r['Q [W]']:<15.2f} | {r['T_hot_out [C]']:<15.2f} | {r['T_cold_out [C]']:<15.2f} |"
            )

        print("-" * 86)
        q_ntu = res_ntu_custom["Q [W]"]
        q_lmtd = res_lmtd_ht["Q [W]"]
        diff_pct = abs(q_ntu - q_lmtd) / q_ntu * 100 if q_ntu > 0 else 0
        print(f"--> Epsilon-NTU ve LMTD Metotları Arası Fark: %{diff_pct:.4f}")

        q_ht = res_ntu_ht["Q [W]"]
        diff_ht_pct = abs(q_ntu - q_ht) / q_ntu * 100 if q_ntu > 0 else 0
        print(f"--> Custom Kod ve 'ht' Kütüphanesi Arası Fark: %{diff_ht_pct:.4f}")

    def plot_temperature_profile(self, result: dict, fig: Any = None) -> Any:
        if fig is None:
            fig = plt.figure(figsize=TEMP_PROFILE_SIZE)
        else:
            fig.clear()
        ax = fig.add_subplot(111)
        Th_in = result.get("T_hot_in [C]")
        Tc_in = result.get("T_cold_in [C]")
        if Th_in is None or Tc_in is None:
            raise InvalidInputError("Temperature profile requires inlet temperatures in the result.")
        Th_out = result["T_hot_out [C]"]
        Tc_out = result["T_cold_out [C]"]
        x = np.linspace(0.0, 1.0, 50)
        Th = Th_in + (Th_out - Th_in) * x
        if self.flow_type == "counter":
            Tc = Tc_out + (Tc_in - Tc_out) * x
            cold_label = "Cold fluid, opposite direction"
        elif self.flow_type == "parallel":
            Tc = Tc_in + (Tc_out - Tc_in) * x
            cold_label = "Cold fluid"
        else:
            Tc = Tc_in + (Tc_out - Tc_in) * (1.0 - np.exp(-3.0 * x)) / (1.0 - np.exp(-3.0))
            cold_label = "Cold fluid, representative crossflow"
        ax.plot(x, Th, color=PALETTE["hot_in"], lw=3, label="Hot fluid", zorder=3)
        ax.plot(x, Tc, color=PALETTE["cold_in"], lw=3, label=cold_label, zorder=3)
        ax.fill_between(x, Tc, Th, color=PALETTE["fill_between"], alpha=0.1, zorder=1)
        ax.set_xlabel("Normalized heat transfer length")
        ax.set_ylabel("Temperature [°C]")
        ax.set_title("Temperature Profile")
        for _val, label, color, pos in [
            (Th_in, f"Hot in {Th_in:.1f} °C", PALETTE["hot_in"], (0.02, Th_in)),
            (Th_out, f"Hot out {Th_out:.1f} °C", PALETTE["hot_out"], (0.98, Th_out)),
            (Tc_in, f"Cold in {Tc_in:.1f} °C", PALETTE["cold_in"], (0.02, Tc_in)),
            (Tc_out, f"Cold out {Tc_out:.1f} °C", PALETTE["cold_out"], (0.98, Tc_out)),
        ]:
            ax.annotate(
                label,
                xy=pos,
                xytext=(pos[0], pos[1] + (Th_in - Tc_in) * 0.06),
                fontsize=9,
                color=color,
                fontweight="semibold",
                ha="left" if pos[0] < 0.5 else "right",
                va="bottom",
                arrowprops=dict(arrowstyle="->", color=color, lw=1.2),
            )
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=True)
        fig.tight_layout()
        return fig

    def plot_enhanced_schematic(self, result: dict | None = None, fig: Any = None) -> Any:
        if fig is None:
            fig = plt.figure(figsize=SCHEMATIC_SIZE)
        else:
            fig.clear()
        ax = fig.add_subplot(111)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 5)
        ax.axis("off")

        ax.add_patch(
            patches.Shadow(
                patches.FancyBboxPatch(
                    (2.05, 1.05),
                    6,
                    3,
                    boxstyle="round,pad=0.1",
                    linewidth=1.8,
                    edgecolor=PALETTE["body_edge"],
                    facecolor=PALETTE["body_fill"],
                ),
                0.08,
                -0.08,
            )
        )
        body = patches.FancyBboxPatch(
            (2, 1),
            6,
            3,
            boxstyle="round,pad=0.1",
            linewidth=2,
            edgecolor=PALETTE["body_edge"],
            facecolor=PALETTE["body_fill"],
        )
        ax.add_patch(body)

        tube_rows = 5
        tubes_per_row = 9
        for row in range(tube_rows):
            y = 1.4 + row * 3.2 / (tube_rows - 1)
            offset = 0.22 if row % 2 else 0.0
            for col in range(tubes_per_row):
                x = 2.45 + offset + col * 5.5 / (tubes_per_row - 1)
                ax.add_patch(
                    patches.Circle(
                        (x, y),
                        0.075,
                        facecolor=PALETTE["tube_fill"],
                        edgecolor=PALETTE["tube_edge"],
                        lw=0.6,
                        zorder=2,
                    )
                )

        def temp_label(key, prefix):
            if not result or result.get(key) is None:
                return prefix
            return f"{prefix}\n{result[key]:.1f} °C"

        flow_type_display = self.flow_type.replace("_", " ").title()
        ax.text(
            5,
            4.55,
            flow_type_display,
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color=PALETTE["text_dark"],
        )
        ax.text(
            5,
            4.55 - 0.25,
            self._exchanger_name(),
            ha="center",
            va="center",
            fontsize=10,
            fontweight="normal",
            color=PALETTE["text_muted"],
        )

        def arrow(x, y, dx, dy, color, label, ox=0.0, oy=0.3):
            ax.annotate(
                "",
                xy=(x + dx, y + dy),
                xytext=(x, y),
                arrowprops=dict(arrowstyle="-|>", lw=3.5, color=color),
            )
            ax.text(
                x + dx / 2 + ox,
                y + dy / 2 + oy,
                label,
                color=color,
                fontweight="bold",
                ha="center",
                va="center",
                fontsize=10,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor=color, lw=0.8),
            )

        if self.flow_type == "parallel":
            arrow(1, 4, 1.5, 0, PALETTE["hot_in"], temp_label("T_hot_in [C]", f"Hot In\n{self.hot_fluid.name}"))
            arrow(7.5, 4, 1.5, 0, PALETTE["hot_out"], temp_label("T_hot_out [C]", "Hot Out"))
            arrow(1, 2, 1.5, 0, PALETTE["cold_in"], temp_label("T_cold_in [C]", f"Cold In\n{self.cold_fluid.name}"))
            arrow(7.5, 2, 1.5, 0, PALETTE["cold_out"], temp_label("T_cold_out [C]", "Cold Out"))
        elif self.flow_type == "counter":
            arrow(1, 4, 1.5, 0, PALETTE["hot_in"], temp_label("T_hot_in [C]", f"Hot In\n{self.hot_fluid.name}"))
            arrow(7.5, 4, 1.5, 0, PALETTE["hot_out"], temp_label("T_hot_out [C]", "Hot Out"))
            arrow(9, 2, -1.5, 0, PALETTE["cold_in"], temp_label("T_cold_in [C]", f"Cold In\n{self.cold_fluid.name}"))
            arrow(2.5, 2, -1.5, 0, PALETTE["cold_out"], temp_label("T_cold_out [C]", "Cold Out"))
        else:
            arrow(1, 3, 1.5, 0, PALETTE["cold_in"], temp_label("T_cold_in [C]", f"Cold In\n{self.cold_fluid.name}"))
            arrow(7.5, 3, 1.5, 0, PALETTE["cold_out"], temp_label("T_cold_out [C]", "Cold Out"))
            arrow(
                5,
                4.85,
                0,
                -1.0,
                PALETTE["hot_in"],
                temp_label("T_hot_in [C]", f"Hot In\n{self.hot_fluid.name}"),
                ox=1.1,
                oy=-0.05,
            )
            arrow(5, 1.15, 0, -1.0, PALETTE["hot_out"], temp_label("T_hot_out [C]", "Hot Out"), ox=1.0, oy=-0.05)

        fig.tight_layout()
        return fig

    def _exchanger_name(self) -> str:
        from config import EXCHANGER_TYPES

        return EXCHANGER_TYPES.get(self.exchanger_type, self.exchanger_type)
