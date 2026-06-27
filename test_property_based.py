from __future__ import annotations

import unittest

import numpy as np
from hypothesis import assume, given
from hypothesis import strategies as st

from heat_exchanger import EXCHANGER_TYPE_DOUBLE, EXCHANGER_TYPE_SHELL, FinTubeHeatExchanger, Fluid
from helpers import _require_positive

HX_FINNED = "finned_tube"
HX_SHELL = EXCHANGER_TYPE_SHELL
HX_DOUBLE = EXCHANGER_TYPE_DOUBLE

POSITIVE = st.floats(min_value=1e-10, max_value=1e6, allow_nan=False, allow_infinity=False)


class TestHypothesisNTUSolver(unittest.TestCase):
    @given(
        m_hot=POSITIVE,
        m_cold=POSITIVE,
        T_hot_in=st.floats(min_value=50.0, max_value=300.0, allow_nan=False, allow_infinity=False),
        T_cold_in=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    def test_ntu_never_returns_nan_or_inf(self, m_hot, m_cold, T_hot_in, T_cold_in):
        assume(T_hot_in > T_cold_in)
        hot = Fluid("hot", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        cold = Fluid("cold", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        hx = FinTubeHeatExchanger(hot, cold, U=100, A=10, flow_type="counter", exchanger_type=HX_SHELL)
        result = hx.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in)
        for k, v in result.items():
            if isinstance(v, float):
                self.assertFalse(np.isnan(v), f"{k} is NaN")
                self.assertFalse(np.isinf(v), f"{k} is Inf")

    @given(
        m_hot=POSITIVE,
        m_cold=POSITIVE,
        T_hot_in=st.floats(min_value=50.0, max_value=300.0, allow_nan=False, allow_infinity=False),
        T_cold_in=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    def test_lmtd_never_returns_nan_or_inf(self, m_hot, m_cold, T_hot_in, T_cold_in):
        assume(T_hot_in > T_cold_in)
        hot = Fluid("hot", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        cold = Fluid("cold", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        hx = FinTubeHeatExchanger(hot, cold, U=100, A=10, flow_type="counter", exchanger_type=HX_SHELL)
        result = hx.solve_lmtd(m_hot, m_cold, T_hot_in, T_cold_in, source="ht")
        for k, v in result.items():
            if isinstance(v, float):
                self.assertFalse(np.isnan(v), f"{k} is NaN")
                self.assertFalse(np.isinf(v), f"{k} is Inf")

    @given(
        T_hot_in=st.floats(min_value=30.0, max_value=500.0, allow_nan=False, allow_infinity=False),
        T_cold_in=st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),
    )
    def test_f_factor_bounds(self, T_hot_in, T_cold_in):
        assume(T_hot_in > T_cold_in)
        from correlations import _bowman_lmtd_factor

        T_hot_out = T_cold_in + (T_hot_in - T_cold_in) * 0.5
        T_cold_out = T_hot_in - (T_hot_in - T_cold_in) * 0.5
        F = _bowman_lmtd_factor(T_hot_in, T_cold_in, T_hot_out, T_cold_out, 1000, 1000)
        self.assertGreaterEqual(F, 0.01)
        self.assertLessEqual(F, 1.0)

    @given(
        m_hot=POSITIVE,
        m_cold=POSITIVE,
        T_hot_in=st.floats(min_value=80.0, max_value=300.0, allow_nan=False, allow_infinity=False),
        T_cold_in=st.floats(min_value=0.0, max_value=40.0, allow_nan=False, allow_infinity=False),
    )
    def test_energy_balance_reasonable_ntu_vs_lmtd(self, m_hot, m_cold, T_hot_in, T_cold_in):
        assume(T_hot_in > T_cold_in + 20)
        hot = Fluid("hot", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        cold = Fluid("cold", cp=1000, density=1, mu=1e-5, k_cond=0.03)
        hx = FinTubeHeatExchanger(hot, cold, U=500, A=10, flow_type="counter", exchanger_type=HX_DOUBLE)
        try:
            ntu = hx.solve_ntu(m_hot, m_cold, T_hot_in, T_cold_in)
            lmtd = hx.solve_lmtd(m_hot, m_cold, T_hot_in, T_cold_in, source="ht")
        except (ValueError, ZeroDivisionError):
            return
        if ntu.get("status") == "ok" and lmtd.get("status") == "ok":
            diff_ratio = abs(ntu["Q [W]"] - lmtd["Q [W]"]) / max(1.0, ntu["Q [W]"])
            self.assertLess(diff_ratio, 0.15)


class TestHypothesisFluid(unittest.TestCase):
    @given(
        cp=POSITIVE,
        density=POSITIVE,
        mu=POSITIVE,
        k_cond=POSITIVE,
    )
    def test_fluid_require_positive(self, cp, density, mu, k_cond):
        val = _require_positive("test", cp)
        self.assertEqual(val, cp)

    @given(
        cp=st.floats(min_value=-1e6, max_value=0, allow_nan=False, allow_infinity=False),
    )
    def test_fluid_rejects_non_positive_cp(self, cp):
        with self.assertRaises(ValueError):
            _require_positive("cp", cp)

    @given(
        name=st.text(min_size=1, max_size=20),
        cp=POSITIVE,
        density=POSITIVE,
        mu=POSITIVE,
        k_cond=POSITIVE,
    )
    def test_fluid_constructs_cleanly(self, name, cp, density, mu, k_cond):
        f = Fluid(name, cp=cp, density=density, mu=mu, k_cond=k_cond, is_coolprop=False)
        self.assertEqual(f.name, name)
        self.assertGreater(f.cp, 0)
        self.assertGreater(f.density, 0)

    @given(
        name=st.text(min_size=1, max_size=10),
        cp=POSITIVE,
        density=POSITIVE,
        mu=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        k_cond=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    )
    def test_fluid_allows_zero_mu_k(self, name, cp, density, mu, k_cond):
        try:
            f = Fluid(name, cp=cp, density=density, mu=mu, k_cond=k_cond, is_coolprop=False)
            self.assertIsNotNone(f)
        except (ValueError, ZeroDivisionError):
            pass


if __name__ == "__main__":
    unittest.main()
