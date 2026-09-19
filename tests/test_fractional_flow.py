"""相对渗透率与分流函数的边界钉点。"""
import pytest

from app.core.fractional import df_dsw, fractional_flow, mobility_water
from app.core.relperm import CoreyParams, kro, krw


def test_krw_endpoints(symmetric_params):
    p = symmetric_params
    assert krw(p.swc, p) == pytest.approx(0.0)
    assert krw(p.s_orw, p) == pytest.approx(p.krw0)  # 末端水相端点
    assert kro(p.swc, p) == pytest.approx(p.kro0)    # 束缚水处油相端点
    assert kro(p.s_orw, p) == pytest.approx(0.0)


def test_krw_outside_mobile_interval_is_zero(symmetric_params):
    p = symmetric_params
    assert krw(p.swc - 0.1, p) == 0.0
    assert kro(p.s_orw + 0.1, p) == 0.0


def test_fractional_flow_endpoints(symmetric_params):
    p = symmetric_params
    # 硬边界：束缚水处 f=0，末端 f=1
    assert fractional_flow(p.swc, p) == 0.0
    assert fractional_flow(p.s_orw, p) == 1.0
    assert fractional_flow(p.swc - 0.5, p) == 0.0
    assert fractional_flow(p.s_orw + 0.5, p) == 1.0


def test_fractional_flow_monotone_and_bounded(standard_params):
    p = standard_params
    prev = -1e-12
    for i in range(101):
        sw = p.swc + (p.s_orw - p.swc) * i / 100
        f = fractional_flow(sw, p)
        assert 0.0 <= f <= 1.0
        assert f + 1e-12 >= prev
        prev = f


def test_symmetric_f_about_midpoint(symmetric_params):
    """等粘度且 Corey 幂次相同：f 在可动区间中点附近大致对称，f(mid)=0.5。"""
    p = symmetric_params
    mid = 0.5 * (p.swc + p.s_orw)
    assert fractional_flow(mid, p) == pytest.approx(0.5, abs=1e-12)
    for delta in (0.05, 0.1, 0.2):
        fa = fractional_flow(mid - delta, p)
        fb = fractional_flow(mid + delta, p)
        assert fa == pytest.approx(1.0 - fb, abs=1e-12)


def test_analytic_derivative_matches_finite_difference(standard_params):
    """解析 df/dSw 与高精度有限差分一致（仅作实现自检，绝不用它抹激波）。"""
    p = standard_params
    h = 1e-7
    for t in (0.2, 0.5, 0.8):
        sw = p.swc + t * p.mobile_span
        fd = (fractional_flow(sw + h, p) - fractional_flow(sw - h, p)) / (2 * h)
        assert df_dsw(sw, p) == pytest.approx(fd, rel=1e-6)


def test_mobility_definition(symmetric_params):
    p = symmetric_params
    sw = 0.5
    assert mobility_water(sw, p) == pytest.approx(krw(sw, p) / p.mu_w)
