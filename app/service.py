"""Assemble full solution payloads (fractional-flow curve, tangent, profile)."""
from __future__ import annotations

import numpy as np

from .core.fractional_flow import FractionalFlow
from .core.profile import build_rarefaction, profile_polyline, sample_profile
from .core.relperm import RockFluid
from .core.welge import WelgeSolution, solve_welge

_N_CURVE = 401
_N_PROFILE = 1_001


def _round_list(arr: np.ndarray, ndigits: int = 6) -> list[float]:
    return [round(float(v), ndigits) for v in arr]


def solve_payload(
    params: RockFluid,
    xi_values: list[float] | None = None,
    *,
    n_curve: int = _N_CURVE,
    n_profile: int = _N_PROFILE,
) -> dict:
    """Run Welge + rarefaction and shape everything the HTTP layer needs."""
    sol: WelgeSolution = solve_welge(params)
    ff = FractionalFlow(params)
    tab = build_rarefaction(sol)

    # f(Sw) over the mobile interval only — never extend the tangent search
    # beyond [Swc, 1-Sor].
    s_curve = np.linspace(0.0, 1.0, n_curve)
    sw_curve = ff.sw_from_s(s_curve)
    f_curve = ff.F(s_curve)

    # Welge tangent in physical coordinates: from (Swc, 0) through
    # (Swf, f(Swf)) and drawn a little past the tangent point for visibility.
    tangent_x = [params.swc, sol.swf, params.swi]
    tangent_y = [
        0.0,
        sol.f_swf,
        sol.tangent_slope * (params.swi - params.swc),
    ]

    # Full Sw(xi) profile with a duplicated point at the shock (vertical jump).
    xi_poly, sw_poly = profile_polyline(
        params, sol, table=tab, n=n_profile,
    )

    payload: dict = {
        "params": params.model_dump(),
        "mobile_interval": {"swc": params.swc, "sw_max": params.swi,
                            "span": params.span},
        "swf": sol.swf,
        "f_swf": sol.f_swf,
        "shock_speed": sol.shock_speed,
        "tangent_slope": sol.tangent_slope,
        "s_star": sol.s_star,
        "residuals": {
            "slope_identity": sol.slope_residual,
            "global_support": sol.support_residual,
        },
        "fractional_curve": {
            "sw": _round_list(sw_curve),
            "f": _round_list(f_curve),
        },
        "tangent": {
            "sw": _round_list(tangent_x),
            "f": _round_list(tangent_y),
        },
        "profile": {
            "xi": _round_list(xi_poly),
            "sw": _round_list(sw_poly),
        },
        "xi_inlet": tab.xi_inlet,
    }

    if xi_values is not None:
        xi_arr = np.asarray(xi_values, dtype=float)
        sw_samples = sample_profile(params, sol, xi_arr, table=tab)
        payload["samples"] = {
            "xi": [float(v) for v in xi_arr],
            "sw": [float(v) for v in sw_samples],
        }

    return payload
