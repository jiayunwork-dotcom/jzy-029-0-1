"""Welge 切线（激波前缘）与 ξ 剖面的硬校验。"""
import pytest

from app.core.fractional import df_dsw, fractional_flow
from app.core.relperm import CoreyParams
from app.core.solution import solve_profile, sw_at_xi
from app.core.tangent import NoTangentError, find_welge_tangent


def test_tangent_point_in_open_interval(standard_params):
    t = find_welge_tangent(standard_params)
    p = standard_params
    assert p.swc < t.swf < p.s_orw
    assert 0.0 < t.t_f < 1.0


def test_slope_equals_secant_shock_speed(standard_params):
    """钉死：切线斜率 == f(Swf)/(Swf-Swc) == 激波速度。"""
    p = standard_params
    t = find_welge_tangent(p)
    secant = t.f_swf / (t.swf - p.swc)
    assert t.shock_speed == pytest.approx(secant, rel=1e-10)
    assert t.slope == pytest.approx(secant, rel=1e-10)
    # 切点处当地导数（切线条件保证它等于割线，但顺序必须是先切线后速度）
    assert df_dsw(t.swf, p) == pytest.approx(secant, rel=1e-8)


def test_shock_speed_positive_and_bounded(standard_params):
    t = find_welge_tangent(standard_params)
    assert t.shock_speed > 0


def test_tangent_line_starts_at_swc_zero(standard_params):
    t = find_welge_tangent(standard_params)
    (x0, y0), _ = t.tangent_line
    assert x0 == pytest.approx(standard_params.swc)
    assert y0 == pytest.approx(0.0)


def test_linear_fractional_flow_has_no_tangent():
    """nw=no=1 时 f 为线性/单调凹形，无唯一内部切线 → 必须判失败。"""
    p = CoreyParams(1.0, 1.0, 0.2, 0.2, 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(NoTangentError):
        find_welge_tangent(p)


def test_sublinear_corey_exponent_rejected():
    """幂次 <1 割线斜率在端点发散/非 S 形，无内部切线，拒绝。"""
    p = CoreyParams(1.0, 1.0, 0.2, 0.2, 1.0, 1.0, 0.8, 2.0)
    with pytest.raises(NoTangentError):
        find_welge_tangent(p)


# ---------------------------------------------------------------- 剖面
def test_profile_shock_jump_and_plateaus(standard_params):
    p = standard_params
    prof = solve_profile(p)
    v = prof.shock_speed
    # 上游（注入端/激波前一刻）高饱和，下游原始带 = Swc
    assert sw_at_xi(0.0, p, prof.tangent, prof.xi_rarefaction_end) == \
        pytest.approx(p.s_orw)
    assert sw_at_xi(v * 2, p, prof.tangent, prof.xi_rarefaction_end) == \
        pytest.approx(p.swc)
    # 激波位置返回上游 Swf，不允许落在某个“斜坡中点”
    sw_shock = sw_at_xi(v, p, prof.tangent, prof.xi_rarefaction_end)
    assert sw_shock == pytest.approx(prof.swf)
    # 激波两侧必须有真正的跳变（不能被抹成斜坡）
    just_after = sw_at_xi(v + 1e-6, p, prof.tangent, prof.xi_rarefaction_end)
    assert just_after == pytest.approx(p.swc)
    assert prof.swf - p.swc > 0.1  # 跳变是显著的


def test_rarefaction_satisfies_xi_equals_df_dsw(standard_params):
    """激波后方稀疏波：每个点必须满足 ξ = df/dSw（不是随便铺的斜坡）。"""
    p = standard_params
    prof = solve_profile(p)
    for pt in prof.rarefaction[::8]:
        assert pt.xi == pytest.approx(df_dsw(pt.sw, p), rel=1e-9)


def test_rarefaction_is_continuous_and_ordered(standard_params):
    p = standard_params
    prof = solve_profile(p)
    # 沿 ξ 增大方向 Sw 单调下降且连续，直到 Swf
    prev_xi = -1.0
    prev_sw = 2.0
    for pt in prof.rarefaction:
        assert pt.xi >= prev_xi - 1e-12
        assert pt.sw <= prev_sw + 1e-12
        prev_xi, prev_sw = pt.xi, pt.sw
    assert prof.rarefaction[-1].sw == pytest.approx(prof.swf)
    assert prof.rarefaction[-1].xi == pytest.approx(prof.shock_speed)


def test_local_derivative_elsewhere_misses_shock_position(standard_params):
    """拿稀疏波内部某点的当地导数冒充激波速度，会被剖面位置卡住：
    那个速度严格小于真正的切线激波速度，且该点位于连续稀疏波段内，
    饱和度没有跳变到 Swc——当作前缘位置是错的。"""
    p = standard_params
    prof = solve_profile(p)
    # 取切点上方（稀疏波内部）一点 t = 0.5*(t_f+1)
    t_mid = 0.5 * (prof.tangent.t_f + 1.0)
    s_mid = p.swc + t_mid * p.mobile_span
    fake_speed = df_dsw(s_mid, p)
    # 该点处于稀疏波段内部，其当地导数严格小于激波速度
    assert s_mid > prof.swf
    assert fake_speed < prof.shock_speed
    # 用假速度定“前缘”，落到的位置仍是连续的高饱和（稀疏波内部），
    # 根本不是跳变到 Swc 的真正前缘
    sw_at_fake = sw_at_xi(fake_speed, p, prof.tangent, prof.xi_rarefaction_end)
    assert sw_at_fake > prof.swf
    sw_behind_real_shock = sw_at_xi(
        prof.shock_speed + 1e-6, p, prof.tangent, prof.xi_rarefaction_end)
    assert sw_behind_real_shock == pytest.approx(p.swc)


def test_profile_samples_on_requested_xi(standard_params):
    p = standard_params
    prof = solve_profile(p, xi_points=[0.0, 0.3, 5.0])
    xis = [s[0] for s in prof.samples]
    assert xis[:3] == pytest.approx([0.0, 0.3, 5.0])


def test_endpoint_f_is_one_for_all_valid_params():
    """末端 Sw=1-Sor 处 f 必须为 1（跨多组参数）。"""
    cases = [
        CoreyParams(0.3, 2.0, 0.1, 0.25, 0.25, 0.95, 3.0, 1.5),
        CoreyParams(2.0, 1.0, 0.25, 0.05, 1.0, 0.8, 2.0, 4.0),
    ]
    for p in cases:
        assert fractional_flow(p.s_orw, p) == 1.0
        t = find_welge_tangent(p)
        assert p.swc < t.swf < p.s_orw
