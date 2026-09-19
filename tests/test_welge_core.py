"""Core invariants of the Welge construction and the rarefaction profile."""
from __future__ import annotations

import numpy as np
import pytest

from app.core.fractional_flow import FractionalFlow
from app.core.profile import build_rarefaction, sample_profile
from app.core.relperm import RockFluid
from app.core.welge import TangentError, solve_welge
from tests.conftest import make_params


def solve(**over):
    return solve_welge(make_params(**over).to_rockfluid())


# 1. 切线斜率 == f(Swf)/(Swf-Swc) == df/dSw|Swf（恒等式）
def test_tangent_slope_identity():
    p = make_params().to_rockfluid()
    sol = solve_welge(p)
    ff = FractionalFlow(p)
    chord = sol.f_swf / (sol.swf - p.swc)
    deriv = ff.df_dsw(np.array([sol.swf]))[0]
    assert sol.tangent_slope == pytest.approx(chord, abs=1e-12)
    assert sol.shock_speed == pytest.approx(chord, abs=1e-12)
    assert deriv == pytest.approx(chord, rel=1e-9)
    assert sol.slope_residual < 1e-9


# 2. 切点必须落在可动开区间内；末端 f(1-Sor)=1, f(Swc)=0
def test_tangent_point_is_interior_and_endpoints():
    p = make_params().to_rockfluid()
    sol = solve_welge(p)
    assert p.swc + 1e-6 < sol.swf < p.swi - 1e-6
    ff = FractionalFlow(p)
    assert ff(p.swi) == pytest.approx(1.0, abs=1e-14)
    assert ff(p.swc) == pytest.approx(0.0, abs=1e-14)


# 3. 切线在整条可动区间上支撑曲线（熵条件，数值验证）
def test_tangent_globally_supports_curve():
    p = make_params().to_rockfluid()
    sol = solve_welge(p)
    ff = FractionalFlow(p)
    s = np.linspace(0, 1, 50_001)
    F = ff.F(s)
    chord = sol.f_swf / sol.s_star * s
    assert np.max(F - chord) <= 1e-8


# 4. 对默认档核对解析解（nw=no=2, krw0=kro0=1）：
#    h=sF'-F=0 化简为 r(1-s^2)=s^2（r=mu_w/mu_o*kro0/krw0），
#    即 s* = sqrt(r/(1+r))。
def test_default_case_matches_analytic_solution():
    p = make_params().to_rockfluid()
    sol = solve_welge(p)
    r = p.mu_w / p.mu_o * p.kro0 / p.krw0  # 0.5
    s_an = np.sqrt(r / (1.0 + r))
    assert sol.s_star == pytest.approx(s_an, abs=1e-6)
    assert sol.swf == pytest.approx(p.swc + p.span * s_an, abs=1e-6)


# 5. 单参数不变量：驱替向有利方向（水更稠/油更稀，即经典流度比
#    M = (krw0*mu_o)/(kro0*mu_w) 下降；μw/μo 上升）变化时，
#    Swf 升高、激波后稀疏波区间变短——前缘变钝、更接近活塞驱。
def test_favorable_mobility_raises_swf():
    muos = [8.0, 4.0, 2.0, 1.0, 0.5]  # μw/μo = 0.125,...,2，逐步有利
    swfs, speeds, ratios, rarefaction_spans, mob_ratios = [], [], [], [], []
    for muo in muos:
        p = make_params(mu_w=1.0, mu_o=muo).to_rockfluid()
        sol = solve_welge(p)
        build_rarefaction(sol)
        swfs.append(sol.swf)
        speeds.append(sol.shock_speed)
        ratios.append(p.mu_w / p.mu_o)
        mob_ratios.append(p.krw0 * p.mu_o / (p.kro0 * p.mu_w))
        rarefaction_spans.append(p.swi - sol.swf)
    assert all(a < b for a, b in zip(ratios, ratios[1:]))      # μw/μo 在上升
    assert all(a > b for a, b in zip(mob_ratios, mob_ratios[1:]))  # M 在下降
    assert all(a < b for a, b in zip(swfs, swfs[1:]))          # Swf 单调升高
    assert all(a > b for a, b in zip(rarefaction_spans, rarefaction_spans[1:]))
    assert swfs[-1] - swfs[0] > 0.2


# 6. 只加大 Sor：末端 1-Sor 左移、可动油变少
def test_increasing_sor_shifts_endpoint_left():
    ends, spans = [], []
    for sor in [0.1, 0.25, 0.4]:
        p = make_params(sor=sor).to_rockfluid()
        solve_welge(p)  # 仍然可构造切线
        ends.append(p.swi)
        spans.append(p.span)
    assert all(a > b for a, b in zip(ends, ends[1:]))      # 末端左移
    assert all(a > b for a, b in zip(spans, spans[1:]))    # 可动区间变窄


# 7. 两相粘度相等且 Corey 幂次相同：f 在可动区间中点附近大致对称
def test_symmetric_fractional_flow_when_matched():
    p = make_params(mu_w=1.0, mu_o=1.0, krw0=1.0, kro0=1.0,
                    nw=2.0, no=2.0).to_rockfluid()
    ff = FractionalFlow(p)
    s = np.linspace(0, 1, 1001)
    F = ff.F(s)
    assert np.max(np.abs(F - (1.0 - F[::-1]))) < 1e-12
    assert ff.F(0.5) == pytest.approx(0.5, abs=1e-12)


# 8. 用当地导数冒充切线会被剖面位置卡住：
#    流行的“简便做法”取可动区间中点饱和度、拿当地 df/dSw 当前缘速度，
#    该错误速度必须明显偏离真实激波（切线）速度；真实剖面在 ξ_f 是竖直跳变。
def test_local_derivative_impostor_caught_by_profile():
    p = make_params().to_rockfluid()
    sol = solve_welge(p)
    ff = FractionalFlow(p)

    s_mid = 0.5 * (p.swc + p.swi)
    naive_speed = float(ff.df_dsw(np.array([s_mid]))[0])
    # 错误中点法与真实切线速度显著不同（默认档差距 > 30%）：
    assert abs(naive_speed - sol.shock_speed) / sol.shock_speed > 0.3

    # 切点处“切线斜率 == 当地导数”是切点定义，不能拿它替代激波构造：
    local_at_front = float(ff.df_dsw(np.array([sol.swf]))[0])
    assert local_at_front == pytest.approx(sol.shock_speed, abs=1e-9)
    behind = sol.swf + 0.25 * p.span
    assert float(ff.df_dsw(np.array([behind]))[0]) < sol.shock_speed

    xi = np.linspace(0, sol.shock_speed * 1.5, 2001)
    tab = build_rarefaction(sol)
    sw = sample_profile(p, sol, xi, table=tab)
    behind = sw[xi < sol.shock_speed - 1e-9]
    ahead = sw[xi > sol.shock_speed + 1e-9]
    # 激波后方铺着稀疏波（Swf ... 1-Sor），前方一律 Swc：
    assert np.min(behind) == pytest.approx(sol.swf, abs=2e-3)
    assert np.max(behind) == pytest.approx(p.swi, abs=1e-9)
    assert np.all(ahead == pytest.approx(p.swc, abs=1e-12))
    # 在取样序列里激波表现为唯一一处有限跳变（≈Swf-Swc），而不是被
    # 中心差分抹开的斜坡：最大相邻差分应等于整段饱和度降，且只出现一次。
    jumps = np.abs(np.diff(sw))
    k = int(np.argmax(jumps))
    assert jumps[k] == pytest.approx(sol.swf - p.swc, abs=2e-3)
    assert jumps[k] > 0.3  # 默认档跳变 ~0.346
    assert np.count_nonzero(jumps > 0.05) == 1
    # 跳变位置就是 ξ_f
    assert xi[k] < sol.shock_speed <= xi[k + 1]
    # 而错误的“中点当地导数”给出的前缘分界线明显错位：
    s_mid_xi = naive_speed
    assert abs(xi[k + 1] - s_mid_xi) / sol.shock_speed > 0.3


# 9. 激波前方绝不能出现中间饱和度；激波后稀疏波满足 ξ = df/dSw
def test_rarefaction_matches_local_derivative():
    p = make_params().to_rockfluid()
    sol = solve_welge(p)
    ff = FractionalFlow(p)
    tab = build_rarefaction(sol)
    xi = np.linspace(tab.xi_inlet + 1e-6, sol.shock_speed - 1e-6, 20)
    sw = sample_profile(p, sol, xi, table=tab)
    assert np.all((sw > sol.swf - 1e-9) & (sw < p.swi + 1e-9))
    back = ff.df_dsw(sw)
    assert np.all(np.abs(back - xi) < 2e-5)
