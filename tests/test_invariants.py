"""单参数变化的物理不变量。"""
import copy

import pytest

from app.core.relperm import CoreyParams
from app.core.tangent import find_welge_tangent

BASE = dict(mu_w=0.5, mu_o=1.0, swc=0.2, sor=0.2,
            krw0=0.3, kro0=0.9, nw=2.0, no=2.0)


def _params(**overrides) -> CoreyParams:
    kw = copy.deepcopy(BASE)
    kw.update(overrides)
    return CoreyParams(**kw)


def test_more_favorable_mobility_raises_swf():
    """流度比变有利（注入水流度相对受抑，M 降低）→ Swf 升高、前缘变钝。

    这里“有利”按油藏工程标准定义 M = (krw0/μw)/(kro0/μo) 减小：
    升高水相粘度 μw（增粘水/聚合物驱）使 M 下降、驱替趋活塞式。
    """
    base = _params()
    favorable = _params(mu_w=2.0)          # μw↑ → M↓
    very_favorable = _params(mu_w=4.0)

    m_base = (base.krw0 / base.mu_w) / (base.kro0 / base.mu_o)
    m_fav = (favorable.krw0 / favorable.mu_w) / (favorable.kro0 / favorable.mu_o)
    assert m_fav < m_base                   # 确实更有利

    swf_base = find_welge_tangent(base).swf
    swf_fav = find_welge_tangent(favorable).swf
    swf_vf = find_welge_tangent(very_favorable).swf
    assert swf_base < swf_fav < swf_vf      # Swf 单调升高
    # 前缘“变钝”：激波速度变小（推进慢、波及均匀）
    assert find_welge_tangent(favorable).shock_speed < \
           find_welge_tangent(base).shock_speed


def test_more_unfavorable_mobility_lowers_swf():
    """反向校验：μw 降低（M 增大、水更稀更易窜）→ Swf 降低、前缘贴向 Swc。"""
    base = _params()
    unfavorable = _params(mu_w=0.1)
    assert find_welge_tangent(unfavorable).swf < find_welge_tangent(base).swf


def test_increasing_sor_shifts_endpoint_left():
    """只加大 Sor：末端 1-Sor 左移、可动油变少（Swc 不动）。"""
    p1 = _params(sor=0.2)
    p2 = _params(sor=0.35)
    assert p2.s_orw < p1.s_orw
    assert p2.mobile_span < p1.mobile_span   # 可动区间收窄
    t2 = find_welge_tangent(p2)
    assert p1.swc < t2.swf < p2.s_orw        # 切点仍在新的可动开区间内


def test_equal_viscosity_equal_exponent_symmetric():
    """两相粘度相等且 Corey 幂次相同：f 在可动区间中点附近大致对称。

    注意对称的是 f 曲线本身（f(mid)=0.5 且 f(mid-δ)=1-f(mid+δ)）；
    切点并不在中点——nw=no=2 时切点解析位置为 t_f=1/√2。
    """
    from app.core.fractional import fractional_flow

    p = CoreyParams(1.0, 1.0, 0.15, 0.3, 0.7, 0.7, 2.5, 2.5)
    mid = 0.5 * (p.swc + p.s_orw)
    assert fractional_flow(mid, p) == pytest.approx(0.5, abs=1e-12)
    for delta in (0.05, 0.1, 0.2):
        assert fractional_flow(mid - delta, p) == pytest.approx(
            1.0 - fractional_flow(mid + delta, p), abs=1e-12)
    t = find_welge_tangent(p)
    assert p.swc < t.swf < p.s_orw

    # 幂次为 2 的对称情形有解析切点，可做精确交叉验证
    p2 = CoreyParams(1.0, 1.0, 0.2, 0.2, 1.0, 1.0, 2.0, 2.0)
    t2 = find_welge_tangent(p2)
    assert t2.t_f == pytest.approx(1.0 / 2 ** 0.5, abs=1e-8)
