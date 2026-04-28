import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)
import matplotlib.patches as patches
import ht

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
    import fluids.core as fluids_core
    FLUIDS_AVAILABLE = True
except ImportError:
    FLUIDS_AVAILABLE = False

SUPPORTED_FLOW_TYPES = {'parallel', 'counter', 'cross_unmixed', 'cross_mixed_unmixed'}
CHEDL_NAME_MAP = {
    'Air': 'air',
    'CO2': 'CO2',
    'INCOMP::T66': None,
    'INCOMP::T55': None,
    'INCOMP::TVP1': None,
    'INCOMP::DowA': None,
    'INCOMP::DowJ': None,
    'INCOMP::DowQ': None,
    'INCOMP::PNF': None,
    'INCOMP::S800': None,
}


def _is_finite(value):
    return np.isfinite(float(value))


def _require_positive(name, value):
    if value is None or not _is_finite(value) or float(value) <= 0:
        raise ValueError(f"{name} sıfırdan büyük ve sonlu olmalıdır.")
    return float(value)


def _append_warning(result, message):
    result.setdefault('warnings', []).append(message)
    if result.get('status') == 'ok':
        result['status'] = 'warning'
    return result


def _append_unique(warnings, message):
    if message not in warnings:
        warnings.append(message)


def _properties_from_chedl(name, calc_temp_c, pressure):
    if not THERMO_AVAILABLE:
        raise ImportError("thermo kütüphanesi bulunamadı.")
    T_K = calc_temp_c + 273.15
    chedl_name = CHEDL_NAME_MAP.get(name, name)
    if chedl_name is None:
        raise ValueError(f"'{name}' ChEDL/thermo tarafında desteklenmiyor.")
    if chedl_name == 'air':
        from thermo import Mixture
        mix = Mixture(IDs=['nitrogen', 'oxygen', 'argon', 'carbon dioxide'], zs=[0.78084, 0.20946, 0.00934, 0.00036], T=T_K, P=pressure)
        return mix.Cp, mix.rho, mix.mu, mix.k
    chem = Chemical(chedl_name, T=T_K, P=pressure)
    return chem.Cp, chem.rho, chem.mu, chem.k


class Fluid:
    def __init__(self, name="Generic", cp=None, density=None, mu=None, k_cond=None, is_coolprop=False, calc_temp_c=None, pressure=101325):
        self.name = name
        self.is_coolprop = is_coolprop
        self.pressure = pressure
        self.mu = mu
        self.k_cond = k_cond
        
        if is_coolprop:
            if calc_temp_c is None:
                raise ValueError("CoolProp kullanıldığında referans sıcaklık (calc_temp_c) °C cinsinden girilmelidir.")
            if not COOLPROP_AVAILABLE:
                self.cp, self.density, self.mu, self.k_cond = _properties_from_chedl(name, calc_temp_c, pressure)
                self.is_coolprop = False
                self.property_source = "ChEDL/thermo"
            else:
                T_K = calc_temp_c + 273.15
                try:
                    self.cp = CP.PropsSI('C', 'T', T_K, 'P', pressure, name)
                    self.density = CP.PropsSI('D', 'T', T_K, 'P', pressure, name)
                    # Try fetching viscosity and conductivity
                    try:
                        self.mu = CP.PropsSI('V', 'T', T_K, 'P', pressure, name)
                        self.k_cond = CP.PropsSI('L', 'T', T_K, 'P', pressure, name)
                    except ValueError:
                        self.mu = None
                        self.k_cond = None
                except ValueError:
                    try:
                        incomp_name = name if name.startswith("INCOMP::") else f"INCOMP::{name}"
                        self.cp = CP.PropsSI('C', 'T', T_K, 'P', pressure, incomp_name)
                        self.density = CP.PropsSI('D', 'T', T_K, 'P', pressure, incomp_name)
                        try:
                            self.mu = CP.PropsSI('V', 'T', T_K, 'P', pressure, incomp_name)
                            self.k_cond = CP.PropsSI('L', 'T', T_K, 'P', pressure, incomp_name)
                        except ValueError:
                            self.mu = None
                            self.k_cond = None
                    except ValueError as e:
                        try:
                            self.cp, self.density, self.mu, self.k_cond = _properties_from_chedl(name, calc_temp_c, pressure)
                            self.is_coolprop = False
                            self.property_source = "ChEDL/thermo"
                        except Exception as chedl_exc:
                            raise ValueError(f"'{name}' CoolProp içerisinde bulunamadı. Hata: {e}. ChEDL/thermo fallback hatası: {chedl_exc}")
        else:
            if cp is None:
                raise ValueError("Manuel kullanımda cp değeri zorunludur.")
            self.cp = cp
            self.density = density

        self.cp = _require_positive(f"{self.name} cp", self.cp)
        if self.density is not None:
            self.density = _require_positive(f"{self.name} yoğunluk", self.density)
        if self.mu is not None:
            self.mu = _require_positive(f"{self.name} viskozite", self.mu)
        if self.k_cond is not None:
            self.k_cond = _require_positive(f"{self.name} ısıl iletkenlik", self.k_cond)
            
class FinTubeHeatExchanger:
    def __init__(self, hot_fluid: Fluid, cold_fluid: Fluid, U: float, A: float, flow_type: str = 'cross_unmixed'):
        self.hot_fluid = hot_fluid
        self.cold_fluid = cold_fluid
        self.U = _require_positive("U", U)
        self.A = _require_positive("A", A)
        if flow_type not in SUPPORTED_FLOW_TYPES:
            raise ValueError(f"Desteklenmeyen akış tipi: {flow_type}")
        self.flow_type = flow_type

    def _capacity_rates(self, m_hot, m_cold, T_hot_in, T_cold_in):
        m_hot = _require_positive("Sıcak akışkan debisi", m_hot)
        m_cold = _require_positive("Soğuk akışkan debisi", m_cold)
        _require_positive("Sıcak akışkan cp", self.hot_fluid.cp)
        _require_positive("Soğuk akışkan cp", self.cold_fluid.cp)
        _require_positive("U", self.U)
        _require_positive("A", self.A)
        if not _is_finite(T_hot_in) or not _is_finite(T_cold_in):
            raise ValueError("Giriş sıcaklıkları sonlu olmalıdır.")
        if T_hot_in <= T_cold_in:
            raise ValueError("Sıcak akışkan giriş sıcaklığı soğuk akışkan giriş sıcaklığından büyük olmalıdır.")
        C_h = m_hot * self.hot_fluid.cp
        C_c = m_cold * self.cold_fluid.cp
        return C_h, C_c

    def _map_ht_flow_type(self, C_h, C_c):
        """Kendi flow_type değişkenimizi ht kütüphanesinin subtype formatına çevirir."""
        if self.flow_type == 'parallel': return 'parallel'
        if self.flow_type == 'counter': return 'counterflow'
        if self.flow_type == 'cross_unmixed': return 'crossflow'
        if self.flow_type == 'cross_mixed_unmixed':
            return 'crossflow, mixed Cmax' if C_h >= C_c else 'crossflow, mixed Cmin'
        return 'counterflow'

    def _terminal_temperature_differences(self, T_hot_in, T_cold_in, T_hot_out, T_cold_out):
        """Akis tipine gore LMTD terminal sicaklik farklarini dondur."""
        if self.flow_type == 'parallel':
            return T_hot_in - T_cold_in, T_hot_out - T_cold_out
        return T_hot_in - T_cold_out, T_hot_out - T_cold_in

    def solve_ntu(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, source: str = 'custom'):
        """Epsilon-NTU metodunu kullanarak çıkış sıcaklıklarını hesaplar."""
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        C_r = C_min / C_max
        NTU = (self.U * self.A) / C_min
        
        epsilon = 0.0
        
        if source == 'custom':
            if self.flow_type == 'parallel':
                epsilon = (1 - np.exp(-NTU * (1 + C_r))) / (1 + C_r)
            elif self.flow_type == 'counter':
                if C_r < 1.0:
                    epsilon = (1 - np.exp(-NTU * (1 - C_r))) / (1 - C_r * np.exp(-NTU * (1 - C_r)))
                else:
                    epsilon = NTU / (1 + NTU)
            elif self.flow_type == 'cross_unmixed':
                epsilon = 1 - np.exp((1/C_r) * (NTU**0.22) * (np.exp(-C_r * (NTU**0.78)) - 1))
            elif self.flow_type == 'cross_mixed_unmixed':
                epsilon = (1/C_r) * (1 - np.exp(-C_r * (1 - np.exp(-NTU))))
                
        elif source == 'ht':
            ht_subtype = self._map_ht_flow_type(C_h, C_c)
            epsilon = ht.hx.effectiveness_from_NTU(NTU=NTU, Cr=C_r, subtype=ht_subtype)
        else:
            raise ValueError(f"Desteklenmeyen NTU kaynağı: {source}")

        if not _is_finite(epsilon) or epsilon < 0 or epsilon > 1.0 + 1e-9:
            raise ValueError(f"Hesaplanan effectiveness fiziksel aralık dışında: {epsilon}")
        epsilon = min(max(float(epsilon), 0.0), 1.0)

        q_max = C_min * (T_hot_in - T_cold_in)
        q = epsilon * q_max
        T_hot_out = T_hot_in - (q / C_h)
        T_cold_out = T_cold_in + (q / C_c)
        
        result = {
            'Method': 'Epsilon-NTU',
            'Source': source,
            'Q [W]': q,
            'epsilon': epsilon,
            'T_hot_out [C]': T_hot_out,
            'T_cold_out [C]': T_cold_out,
            'NTU': NTU,
            'C_r': C_r,
            'status': 'ok',
            'warnings': []
        }
        if self.flow_type == 'cross_unmixed' and source == 'custom':
            _append_warning(result, "Çapraz akış/unmixed NTU bağıntısı yaklaşık korelasyondur; kritik tasarımda ht/tam çözüm ile karşılaştırın.")
        return result

    def solve_pychemengg_ntu(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float):
        """PyChemEngg kuruluysa bağımsız Effectiveness-NTU doğrulaması yapar."""
        try:
            from pychemengg.heattransfer import heatexchangers as pce_hx
        except ImportError as exc:
            raise ImportError("PyChemEngg kurulu değil. Opsiyonel doğrulama için `pip install pychemengg` çalıştırılabilir.") from exc

        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        C_max = max(C_h, C_c)
        C_r = C_min / C_max
        NTU = (self.U * self.A) / C_min
        solver = pce_hx.EffNTU(Cmin=C_min, Cmax=C_max, NTU=NTU, effectiveness="?")
        warnings = []

        if self.flow_type == 'parallel':
            epsilon = solver.doublepipe_parallelflow()
        elif self.flow_type == 'counter':
            epsilon = solver.doublepipe_counterflow()
        elif self.flow_type == 'cross_unmixed':
            epsilon = solver.crossflow_bothfluids_unmixed()
            warnings.append("PyChemEngg çapraz akış both-unmixed bağıntısı da yaklaşık NTU korelasyonudur.")
        elif self.flow_type == 'cross_mixed_unmixed':
            epsilon = solver.crossflow_Cmin_unmixed()
            warnings.append("PyChemEngg doğrulamasında cross_mixed_unmixed için Cmin-unmixed varsayımı kullanıldı.")
        else:
            raise ValueError(f"PyChemEngg doğrulaması bu akış tipi için desteklenmiyor: {self.flow_type}")

        if epsilon is None or not _is_finite(epsilon) or epsilon < 0 or epsilon > 1.0 + 1e-9:
            raise ValueError(f"PyChemEngg effectiveness sonucu fiziksel aralık dışında: {epsilon}")
        epsilon = min(max(float(epsilon), 0.0), 1.0)

        q_max = C_min * (T_hot_in - T_cold_in)
        q = epsilon * q_max
        return {
            'Method': 'Epsilon-NTU',
            'Source': 'PyChemEngg',
            'Q [W]': q,
            'epsilon': epsilon,
            'T_hot_out [C]': T_hot_in - (q / C_h),
            'T_cold_out [C]': T_cold_in + (q / C_c),
            'NTU': NTU,
            'C_r': C_r,
            'status': 'warning' if warnings else 'ok',
            'warnings': warnings,
        }

    def solve_lmtd(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, source: str = 'ht'):
        """LMTD metodunu iterasyon (root finding) ile kullanarak çıkış sıcaklıklarını hesaplar."""
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        
        def lmtd_residual(Q):
            if Q <= 0: return 1e6
            T_h_o = T_hot_in - Q/C_h
            T_c_o = T_cold_in + Q/C_c
            
            # Fiziksel olmayan sıcaklıkları engelle
            if T_h_o < T_cold_in or T_c_o > T_hot_in:
                return 1e6
                
            dt1, dt2 = self._terminal_temperature_differences(T_hot_in, T_cold_in, T_h_o, T_c_o)
            if dt1 <= 0 or dt2 <= 0:
                return 1e6
                
            try:
                if abs(dt1 - dt2) < 1e-6:
                    LMTD = dt1
                else:
                    LMTD = (dt1 - dt2) / np.log(dt1 / dt2)
            except ValueError:
                return 1e6
                
            F = 1.0
            if 'cross' in self.flow_type:
                _append_unique(warnings, "Çapraz akış LMTD F faktörü için F=0.9 yaklaşık kabul edildi; kritik tasarımda ε-NTU/ht sonucu esas alınmalıdır.")
                F = 0.9

            Q_lmtd = self.U * self.A * LMTD * F
            return Q - Q_lmtd

        Q_max = min(C_h, C_c) * (T_hot_in - T_cold_in)
        warnings = []
        status = 'ok'
        try:
            q_found = opt.brentq(lmtd_residual, 1.0, Q_max * 0.9999)
        except ValueError as exc:
            q_found = 0.0
            status = 'failed'
            warnings.append(f"LMTD kök bulma başarısız oldu: {exc}. Sonuç geçersiz kabul edilmelidir.")

        T_hot_out = T_hot_in - (q_found / C_h)
        T_cold_out = T_cold_in + (q_found / C_c)
        
        return {
            'Method': 'LMTD Iteration',
            'Source': source,
            'Q [W]': q_found,
            'T_hot_out [C]': T_hot_out,
            'T_cold_out [C]': T_cold_out,
            'status': 'warning' if status == 'ok' and warnings else status,
            'warnings': warnings
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
        
        if self.flow_type == 'parallel':
            # Paralel akışta maksimum verim C_min / (C_h + C_c) civarındadır
            max_eps = C_min / (C_h + C_c)
        else:
            max_eps = 0.999
        warnings = []
            
        def objective(eps):
            Q = eps * Q_max
            T_h_out = T_hot_in - Q / C_h
            T_c_out = T_cold_in + Q / C_c
            
            dt1, dt2 = self._terminal_temperature_differences(T_hot_in, T_cold_in, T_h_out, T_c_out)
                
            if dt1 <= 0 or dt2 <= 0:
                return 1e9 # Fizik dışı sıcaklık çakışması
                
            if abs(dt1 - dt2) < 1e-6:
                LMTD = dt1
            else:
                LMTD = (dt1 - dt2) / np.log(dt1 / dt2)
                
            F = 1.0
            if 'cross' in self.flow_type:
                P = (T_c_out - T_cold_in) / (T_hot_in - T_cold_in)
                R = C_c / C_h
                _append_unique(warnings, "Custom çapraz akış LMTD çözümünde yaklaşık F sınırlaması kullanıldı.")
                F = 1.0 - (0.25 * P * R)
                if F < 0.1: F = 0.1
                    
            Q_lmtd = self.U * self.A * LMTD * F
            return Q - Q_lmtd

        try:
            # Kök bulma
            eps_found = opt.brentq(objective, 1e-5, max_eps - 1e-5)
            Q_found = eps_found * Q_max
            T_h_out = T_hot_in - Q_found / C_h
            T_c_out = T_cold_in + Q_found / C_c
            
            return {
                'Method': 'LMTD Iteration',
                'Source': 'custom',
                'Q [W]': Q_found,
                'T_hot_out [C]': T_h_out,
                'T_cold_out [C]': T_c_out,
                'epsilon': eps_found,
                'status': 'warning' if warnings else 'ok',
                'warnings': warnings
            }
        except Exception as exc:
            # İterasyon çakarsa NTU'ya düş (yedek güvenlik)
            result = self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source='custom')
            result['Method'] = 'LMTD Iteration'
            result['Source'] = 'custom-fallback-NTU'
            result['status'] = 'fallback'
            result.setdefault('warnings', []).append(f"Custom LMTD çözücü yakınsamadı; NTU sonucuna düşüldü: {exc}")
            return result

    def calculate_actual_performance(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float, T_hot_out: float, T_cold_out: float):
        """
        Kullanıcı çıkış sıcaklıklarını verdiğinde gerçek Q'yu ve Kazan/Eşanjör Verimini (Effectiveness) hesaplar.
        Ayrıca sıcak ve soğuk taraftan transfer edilen ısının enerji dengesini kontrol eder.
        """
        C_h, C_c = self._capacity_rates(m_hot, m_cold, T_hot_in, T_cold_in)
        C_min = min(C_h, C_c)
        warnings = []
        
        Q_hot_side = C_h * (T_hot_in - T_hot_out)
        Q_cold_side = C_c * (T_cold_out - T_cold_in)
        
        # Gerçek Q (ortalama alarak veya enerji kaybı hesabı yaparak)
        Q_avg = (Q_hot_side + Q_cold_side) / 2.0
        
        Q_max = C_min * (T_hot_in - T_cold_in)
        
        epsilon_actual = Q_avg / Q_max if Q_max > 0 else 0
        if Q_hot_side < 0 or Q_cold_side < 0:
            warnings.append("Ölçülen çıkış sıcaklıkları negatif ısı transferi üretiyor; performans sonucu fiziksel değildir.")
        if epsilon_actual < 0 or epsilon_actual > 1:
            warnings.append("Gerçekleşen effectiveness 0-1 aralığı dışında; çıkış sıcaklıkları veya debiler tutarsız olabilir.")
        
        # LMTD ile Gerçek U Gereksinimi
        dt1, dt2 = self._terminal_temperature_differences(T_hot_in, T_cold_in, T_hot_out, T_cold_out)
            
        try:
            if dt1 <= 0 or dt2 <= 0:
                raise ValueError("Invalid terminal temperature difference")
            if abs(dt1 - dt2) < 1e-6:
                LMTD = dt1
            else:
                LMTD = (dt1 - dt2) / np.log(dt1 / dt2)
                
            F = 1.0
            if 'cross' in self.flow_type:
                P = (T_cold_out - T_cold_in) / (T_hot_in - T_cold_in)
                R = C_c / C_h
                _append_unique(warnings, "Çapraz akış gerçek performans LMTD hesabında yaklaşık F sınırlaması kullanıldı.")
                F = 1.0 - (0.25 * P * R)
                if F < 0.1:
                    F = 0.1
                    
            U_required = Q_avg / (self.A * LMTD * F) if (self.A * LMTD * F) > 0 else 0
        except Exception as exc:
            LMTD = 0
            U_required = 0
            F = 1.0
            warnings.append(f"LMTD/U_required hesaplanamadı: {exc}")
            
        return {
            'Q_hot [W]': Q_hot_side,
            'Q_cold [W]': Q_cold_side,
            'Q_avg [W]': Q_avg,
            'epsilon_actual': epsilon_actual,
            'U_required': U_required,
            'LMTD': LMTD,
            'F': F,
            'status': 'warning' if warnings else 'ok',
            'warnings': warnings
        }

    def _nusselt_internal(self, Re, Pr, n_factor, laminar_nu, side_name, warnings):
        Re = _require_positive(f"{side_name} Reynolds", Re)
        Pr = _require_positive(f"{side_name} Prandtl", Pr)
        if Re <= 2300:
            return laminar_nu
        if Re < 10000:
            warnings.append(f"{side_name}: Re={Re:.0f} geçiş bölgesinde; laminer ve Dittus-Boelter arasında interpolasyon kullanıldı.")
            nu_turb_10000 = 0.023 * (10000.0**0.8) * (Pr**n_factor)
            frac = (Re - 2300.0) / (10000.0 - 2300.0)
            return laminar_nu + frac * (nu_turb_10000 - laminar_nu)
        if Pr < 0.7 or Pr > 160:
            warnings.append(f"{side_name}: Pr={Pr:.3g} Dittus-Boelter tipik geçerlilik aralığı dışında.")
        return 0.023 * (Re**0.8) * (Pr**n_factor)

    def calculate_geometric_U(self, geom: dict, m_hot: float, m_cold: float, hot_is_tube: bool = False):
        """
        Geometrik ölçülere göre Toplam Isı Transfer Katsayısını (U) hesaplar.
        Tüm akış tiplerini destekler.
        """
        D_o = geom['D_o']
        D_i = geom['D_i']
        L = geom['L']
        N = geom.get('N_tubes', 1)
        k_wall = geom['k_wall']
        warnings = []

        D_o = _require_positive("Dış çap", D_o)
        D_i = _require_positive("İç çap", D_i)
        L = _require_positive("Boru uzunluğu", L)
        N = _require_positive("Boru sayısı", N)
        k_wall = _require_positive("Duvar ısıl iletkenliği", k_wall)
        if D_i >= D_o:
            raise ValueError("Dış çap iç çaptan büyük olmalıdır.")
        _require_positive("Sıcak akışkan debisi", m_hot)
        _require_positive("Soğuk akışkan debisi", m_cold)
        
        # İç Akışkan ve Dış Akışkan Seçimi
        fluid_in = self.hot_fluid if hot_is_tube else self.cold_fluid
        fluid_out = self.cold_fluid if hot_is_tube else self.hot_fluid
        m_in = m_hot if hot_is_tube else m_cold
        m_out = m_cold if hot_is_tube else m_hot
        
        if fluid_in.mu is None or fluid_in.k_cond is None:
            raise ValueError(f"İç akışkan ({fluid_in.name}) için Viskozite ve Isıl İletkenlik değeri gereklidir!")
        if fluid_out.mu is None or fluid_out.k_cond is None:
            raise ValueError(f"Dış akışkan ({fluid_out.name}) için Viskozite ve Isıl İletkenlik değeri gereklidir!")
            
        if not fluid_in.density:
            raise ValueError(f"İç akışkan ({fluid_in.name}) için Yoğunluk değeri hesaplanamıyor. Manuel akışkansa yoğunluğu girmelisiniz.")
        if not fluid_out.density:
            raise ValueError(f"Dış akışkan ({fluid_out.name}) için Yoğunluk değeri hesaplanamıyor. Manuel akışkansa yoğunluğu girmelisiniz.")
            
        # --- İÇ TAŞINIM (h_i) ---
        A_c_i = N * (np.pi * D_i**2) / 4.0
        v_in = m_in / (fluid_in.density * A_c_i)
        if FLUIDS_AVAILABLE:
            Re_i = fluids_core.Reynolds(V=v_in, D=D_i, rho=fluid_in.density, mu=fluid_in.mu)
            Pr_i = fluids_core.Prandtl(Cp=fluid_in.cp, mu=fluid_in.mu, k=fluid_in.k_cond)
        else:
            Re_i = (fluid_in.density * v_in * D_i) / fluid_in.mu
            Pr_i = (fluid_in.cp * fluid_in.mu) / fluid_in.k_cond
        
        n_factor = 0.3 if hot_is_tube else 0.4 
        Nu_i = self._nusselt_internal(Re_i, Pr_i, n_factor, 3.66, "İç taraf", warnings)
        h_i = (Nu_i * fluid_in.k_cond) / D_i
        
        # --- DUVAR İLETİM DİRENCİ (R_wall) ---
        R_wall = np.log(D_o / D_i) / (2 * np.pi * k_wall * L * N)
        
        # --- DIŞ TAŞINIM (h_o) ---
        if 'cross' in self.flow_type:
            pitch = geom.get('pitch', D_o * 2.0)
            pitch = _require_positive("Transverse pitch", pitch)
            if pitch <= D_o:
                raise ValueError("Transverse pitch dış çaptan büyük olmalıdır.")
            W_estimate = np.sqrt(N) * pitch
            A_min = (W_estimate - np.sqrt(N)*D_o) * L
            A_min = max(A_min, 1e-6)
            v_out = m_out / (fluid_out.density * A_min)
            if FLUIDS_AVAILABLE:
                Re_o = fluids_core.Reynolds(V=v_out, D=D_o, rho=fluid_out.density, mu=fluid_out.mu)
                Pr_o = fluids_core.Prandtl(Cp=fluid_out.cp, mu=fluid_out.mu, k=fluid_out.k_cond)
            else:
                Re_o = (fluid_out.density * v_out * D_o) / fluid_out.mu
                Pr_o = (fluid_out.cp * fluid_out.mu) / fluid_out.k_cond
            
            if geom.get('is_finned', False):
                fin_density = _require_positive("Kanatçık yoğunluğu", geom['fin_density'])
                fin_thickness = _require_positive("Kanatçık kalınlığı", geom['fin_thickness'])
                h_b = _require_positive("Kanatçık yüksekliği", geom['fin_height'])
                k_fin = _require_positive("Kanatçık ısıl iletkenliği", geom['k_fin'])
                s = (1.0 / fin_density) - fin_thickness
                if s <= 0:
                    raise ValueError("Kanatçık aralığı pozitif olmalıdır; fin_density ve fin_thickness değerlerini kontrol edin.")
                try:
                    Nu_o = 0.134 * (Re_o**0.681) * (Pr_o**0.33) * ((s/h_b)**0.2) * ((s/geom['fin_thickness'])**0.1134)
                    h_o = (Nu_o * fluid_out.k_cond) / D_o
                    m_fin = np.sqrt(2 * h_o / (k_fin * fin_thickness))
                    eta_fin = np.tanh(m_fin * h_b) / (m_fin * h_b)
                except Exception as exc:
                    warnings.append(f"Kanatçık korelasyonu uygulanamadı; çıplak boru dış korelasyonuna düşüldü: {exc}")
                    eta_fin = 1.0
                    Nu_o = 0.33 * (Re_o**0.6) * (Pr_o**0.33)
                    h_o = (Nu_o * fluid_out.k_cond) / D_o
            else:
                eta_fin = 1.0
                Nu_o = 0.33 * (Re_o**0.6) * (Pr_o**0.33)
                h_o = (Nu_o * fluid_out.k_cond) / D_o
        else:
            # Çift Borulu (Counter/Parallel)
            D_shell = geom.get('D_shell', D_o * 1.5)
            D_shell = _require_positive("Gövde iç çapı", D_shell)
            if D_shell <= D_o:
                raise ValueError("Gövde iç çapı boru dış çapından büyük olmalıdır.")
            D_e = D_shell - D_o
            A_c_o = (np.pi * (D_shell**2 - D_o**2)) / 4.0
            A_c_o = max(A_c_o, 1e-6)
            v_out = m_out / (fluid_out.density * A_c_o)
            if FLUIDS_AVAILABLE:
                Re_o = fluids_core.Reynolds(V=v_out, D=D_e, rho=fluid_out.density, mu=fluid_out.mu)
                Pr_o = fluids_core.Prandtl(Cp=fluid_out.cp, mu=fluid_out.mu, k=fluid_out.k_cond)
            else:
                Re_o = (fluid_out.density * v_out * D_e) / fluid_out.mu
                Pr_o = (fluid_out.cp * fluid_out.mu) / fluid_out.k_cond
            
            n_factor_out = 0.4 if hot_is_tube else 0.3
            Nu_o = self._nusselt_internal(Re_o, Pr_o, n_factor_out, 4.36, "Dış taraf", warnings)
            h_o = (Nu_o * fluid_out.k_cond) / D_e
            eta_fin = 1.0
            
        A_i = np.pi * D_i * L * N
        A_o = np.pi * D_o * L * N
        
        if geom.get('is_finned', False) and 'cross' in self.flow_type:
            A_fin_ratio = 1.0 + (2*geom['fin_height'] * geom['fin_density'])
            A_total_out = A_o * A_fin_ratio
        else:
            A_total_out = A_o
            
        R_i = 1.0 / (h_i * A_i)
        R_o = 1.0 / (h_o * A_total_out * eta_fin)
        
        U_A_total = 1.0 / (R_i + R_wall + R_o)
        
        self.U = U_A_total / A_total_out
        self.A = A_total_out
        
        return {
            'U': self.U,
            'A_total': self.A,
            'h_i': h_i,
            'h_o': h_o,
            'Re_i': Re_i,
            'Re_o': Re_o,
            'R_wall': R_wall,
            'eta_fin': eta_fin,
            'status': 'warning' if warnings else 'ok',
            'warnings': warnings
        }

    def cross_check(self, m_hot: float, m_cold: float, T_hot_in: float, T_cold_in: float):
        """Dört farklı kombinasyonu hesaplar ve birbirleriyle kıyaslar."""
        res_ntu_custom = self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source='custom')
        res_ntu_ht = self.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in, source='ht')
        res_lmtd_ht = self.solve_lmtd(m_hot, m_cold, T_hot_in, T_cold_in, source='ht')
        
        print(f"| {'Method':<20} | {'Source':<10} | {'Q [W]':<15} | {'T_h_out [C]':<15} | {'T_c_out [C]':<15} |")
        print("-" * 86)
        
        results = [res_ntu_custom, res_ntu_ht, res_lmtd_ht]
        for r in results:
            print(f"| {r['Method']:<20} | {r['Source']:<10} | {r['Q [W]']:<15.2f} | {r['T_hot_out [C]']:<15.2f} | {r['T_cold_out [C]']:<15.2f} |")
            
        print("-" * 86)
        q_ntu = res_ntu_custom['Q [W]']
        q_lmtd = res_lmtd_ht['Q [W]']
        diff_pct = abs(q_ntu - q_lmtd) / q_ntu * 100 if q_ntu > 0 else 0
        print(f"--> Epsilon-NTU ve LMTD Metotları Arası Fark: %{diff_pct:.4f}")
        
        q_ht = res_ntu_ht['Q [W]']
        diff_ht_pct = abs(q_ntu - q_ht) / q_ntu * 100 if q_ntu > 0 else 0
        print(f"--> Custom Kod ve 'ht' Kütüphanesi Arası Fark: %{diff_ht_pct:.4f}")

    def plot_schematic(self, fig=None):
        """
        Akış konfigürasyonuna göre sıcaklık renk geçişli (kırmızıdan maviye) gerçekçi oklar 
        ve ısı değiştirici boru demetlerini matplotlib ile çizer.
        """
        if fig is None:
            fig = plt.figure(figsize=(8, 4))
        else:
            fig.clear()
            
        ax = fig.add_subplot(111)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 5)
        ax.axis('off')
        
        import matplotlib.patches as patches
        
        # Gövde / Dış Ortam Kutusu
        rect = patches.Rectangle((2, 1), 6, 3, linewidth=2, edgecolor='black', facecolor='#f0f0f0', zorder=1)
        ax.add_patch(rect)
        ax.text(5, 4.3, f"Heat Exchanger - {self.flow_type.capitalize()}", ha='center', va='center', fontsize=12, fontweight='bold')
        
        # Ok Çizim Fonksiyonu
        def draw_arrow(x, y, dx, dy, color, label):
            ax.arrow(x, y, dx, dy, head_width=0.2, head_length=0.3, fc=color, ec=color, lw=3, zorder=3)
            ax.text(x + dx/2, y + dy/2 + 0.3, label, color=color, fontweight='bold', ha='center')

        if self.flow_type == 'parallel':
            draw_arrow(1, 4, 1.5, 0, 'red', f"Hot In\n{self.hot_fluid.name}")
            draw_arrow(7.5, 4, 1.5, 0, 'red', "Hot Out")
            draw_arrow(1, 2, 1.5, 0, 'blue', f"Cold In\n{self.cold_fluid.name}")
            draw_arrow(7.5, 2, 1.5, 0, 'blue', "Cold Out")
            
        elif self.flow_type == 'counter':
            draw_arrow(1, 4, 1.5, 0, 'red', f"Hot In\n{self.hot_fluid.name}")
            draw_arrow(7.5, 4, 1.5, 0, 'red', "Hot Out")
            draw_arrow(9, 2, -1.5, 0, 'blue', f"Cold In\n{self.cold_fluid.name}")
            draw_arrow(2.5, 2, -1.5, 0, 'blue', "Cold Out")
            
        elif 'cross' in self.flow_type:
            draw_arrow(1, 3, 1.5, 0, 'blue', f"Cold In\n{self.cold_fluid.name}")
            draw_arrow(7.5, 3, 1.5, 0, 'blue', "Cold Out")
            draw_arrow(5, 5.5, 0, -1.5, 'red', f"Hot In\n{self.hot_fluid.name}")
            draw_arrow(5, 1.5, 0, -1.5, 'red', "Hot Out")

        plt.title(f"Heat Exchanger Schematic - {self.flow_type.replace('_', ' ').title()}", fontsize=14)
        plt.tight_layout()
        
        return fig
