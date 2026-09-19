"""Welge tangent construction: locate the Buckley-Leverett shock front.

From the point ``(Swc, f=0)`` a tangent is drawn to the fractional-flow
curve.  In the unit mobile coordinate ``s = (Sw - Swc)/span`` this is the
ray through the origin, and the tangent point maximises

    g(s) = F(s) / s,        g'(s*) = 0  <=>  F'(s*) = F(s*)/s*.

Back in physical variables the shock speed is

    V_shock = f(Swf) / (Swf - Swc),      Swf = Swc + span * s*.

Hard requirements enforced here:

* the tangent point must lie strictly inside ``(Swc, 1-Sor)`` — a root at an
  endpoint is a degenerate construction and is rejected;
* the chord from ``(Swc, 0)`` must globally support the curve from below
  (the entropy / Rankine-Hugoniot condition for the BL shock), i.e.
  ``F(s)/s <= F(s*)/s*`` for every ``s in [0, 1]``;
* the residual of the tangency equation and of the slope identity must be at
  numerical round-off level.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .fractional_flow import FractionalFlow
from .relperm import RockFluid


class TangentError(ValueError):
    """Raised when no valid interior Welge tangent can be constructed."""


@dataclass(frozen=True)
class WelgeSolution:
    params: RockFluid
    swf: float           # shock-front water saturation
    f_swf: float         # f at the tangent point
    shock_speed: float   # dimensionless shock velocity xi_f
    tangent_slope: float  # slope of the tangent in (Sw, f) coordinates
    s_star: float        # tangent point on the unit mobile coordinate
    slope_residual: float  # |F'(s*) - F(s*)/s*|
    support_residual: float  # max_s (F(s) - chord(s)), must be <= 0 numerically


#: Fraction of the mobile span that counts as "sitting on the endpoint".
_EDGE_TOL = 1.0e-6
#: Acceptance tolerance for the slope identity / support check.
_RESID_TOL = 1.0e-7
#: Grid used for bracketing and for the global support check.
_N_GRID = 200_001


def _g_prime_zero_form(ff: FractionalFlow, s: float) -> float:
    """h(s) = s F'(s) - F(s); h = 0 is the tangency condition."""
    return s * ff.dF_ds_at_s(s) - ff.f_at_s(s)


def solve_welge(
    params: RockFluid,
    *,
    n_grid: int = _N_GRID,
    edge_tol: float = _EDGE_TOL,
    resid_tol: float = _RESID_TOL,
) -> WelgeSolution:
    """Find the Welge tangent point for ``params`` or raise ``TangentError``."""
    ff = FractionalFlow(params)

    # Dense scan on (0, 1): bracket sign changes of h = s F' - F.
    s_grid = np.linspace(0.0, 1.0, n_grid)
    eps = 1.0e-9
    s_inner = np.linspace(eps, 1.0 - eps, n_grid)
    h = s_inner * ff.dF_ds(s_inner) - ff.F(s_inner)

    # The tangent point is the global maximum of g = F/s.  Scan g directly as
    # a fallback/selector so we never pick a minimum or a non-supporting root.
    with np.errstate(divide="ignore", invalid="ignore"):
        g = ff.F(s_inner) / s_inner

    # -- bracket sign changes and bisect each -------------------------------
    sign = np.sign(h)
    sign_change = sign[:-1] * sign[1:] < 0.0
    brackets = np.nonzero(sign_change)[0]

    candidates: list[tuple[float, float]] = []  # (s, g(s))
    for idx in brackets:
        lo, hi = float(s_inner[idx]), float(s_inner[idx + 1])
        root = _bisect(lambda z: _g_prime_zero_form(ff, z), lo, hi)
        if root is not None:
            candidates.append((root, float(ff.f_at_s(root) / root)))

    if not candidates:
        raise TangentError(
            "做不出 Welge 切线：在可动开区间 (Swc, 1-Sor) 内找不到 "
            "F'(s)=F(s)/s 的驻点（该组 Corey 参数下分流曲线无内点切点）"
        )

    # Tangent must support the curve: pick the stationary point with the
    # largest chord slope g; verify it globally afterwards.
    s_star, g_star = max(candidates, key=lambda t: t[1])

    # -- interior check ------------------------------------------------------
    if s_star <= edge_tol or s_star >= 1.0 - edge_tol:
        raise TangentError(
            f"切点落到可动区间端点上（s*={s_star:.6g}），不满足开区间要求，"
            "拒绝构造剖面"
        )

    # -- global support check: F(s) <= g_star * s for all s in [0, 1] --------
    F_grid = ff.F(s_grid)
    chord_grid = g_star * s_grid
    support_residual = float(np.max(F_grid - chord_grid))
    if support_residual > resid_tol:
        raise TangentError(
            "切线不满足全局支撑（熵）条件：存在 F(s) > 切线段 的区域；"
            f"最大超出 {support_residual:.3e}"
        )

    # -- residual of the tangency equation ----------------------------------
    slope_residual = abs(
        ff.dF_ds_at_s(s_star) - ff.f_at_s(s_star) / s_star
    )
    if slope_residual > resid_tol:
        raise TangentError(
            f"切线斜率方程残差过大：{slope_residual:.3e} > {resid_tol:.0e}"
        )

    swf = float(params.swc + params.span * s_star)
    f_swf = ff.f_at_s(s_star)
    # Shock speed in physical (Sw, f) coordinates:
    # df/ds tangent slope divided by span == f(Swf)/(Swf-Swc).
    tangent_slope = f_swf / (swf - params.swc)
    identity_residual = abs(
        tangent_slope - ff.dF_ds_at_s(s_star) / params.span
    )
    if identity_residual > resid_tol:  # pragma: no cover - guarded above
        raise TangentError(
            f"切线斜率与 f(Swf)/(Swf-Swc) 对不上：残差 {identity_residual:.3e}"
        )

    return WelgeSolution(
        params=params,
        swf=swf,
        f_swf=f_swf,
        shock_speed=tangent_slope,
        tangent_slope=tangent_slope,
        s_star=s_star,
        slope_residual=slope_residual,
        support_residual=support_residual,
    )


def _bisect(fun, lo: float, hi: float, *, max_iter: int = 120,
            tol: float = 1.0e-13) -> float | None:
    """Bisection with strict sign change; returns None on degeneracy."""
    flo, fhi = fun(lo), fun(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if flo * fhi > 0.0:
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fm = fun(mid)
        if abs(fm) < tol or 0.5 * (hi - lo) < tol:
            return mid
        if flo * fm <= 0.0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)
