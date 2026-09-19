"""Rarefaction behind the shock and sampling of the full Sw(xi) profile.

Buckley-Leverett solution (continuous water injection at Sw=1-Sor):

* for xi < V_shock : rarefaction, xi = df/dSw, with Sw found by inverting
  the monotone branch df/dSw on [Swf, 1-Sor]; Sw ranges from 1-Sor (near the
  inlet) down to Swf as xi approaches V_shock from below;
* at xi = V_shock : a genuine jump (shock) between Swf and Swc;
* for xi > V_shock : undisturbed reservoir, Sw = Swc.

The shock velocity is the Welge chord slope — never the local derivative
df/dSw at Swf (that would smear the shock into a non-conservative ramp).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .fractional_flow import FractionalFlow
from .relperm import RockFluid
from .welge import WelgeSolution

_N_TABLE = 200_001


@dataclass(frozen=True)
class RarefactionTable:
    """Monotone (xi, Sw) table covering the rarefaction branch."""

    xi: np.ndarray          # df/dSw, decreasing from xi_inlet down to V_shock
    sw: np.ndarray          # Sw, increasing from Swf to 1-Sor as xi decreases
    xi_inlet: float         # df/dSw at 1-Sor (0 for typical Corey exponents)
    v_shock: float


def build_rarefaction(sol: WelgeSolution, *, n: int = _N_TABLE) -> RarefactionTable:
    """Build the monotone inversion table df/dSw on [Swf, 1-Sor]."""
    p = sol.params
    ff = FractionalFlow(p)

    eps = 1.0e-9
    # s increases from the tangent point s* towards 1; df/ds decreases from
    # V_shock towards its inlet value (0 for no > 1).  Start exactly at s*
    # where the derivative equals the chord, so the table reaches V exactly.
    s_grid = np.linspace(sol.s_star, 1.0 - eps, n)
    sw_grid = ff.sw_from_s(s_grid)
    xi_grid = ff.dF_ds(s_grid) / p.span

    # Require xi strictly decreasing as s increases (monotone rarefaction).
    dxi = np.diff(xi_grid)
    if np.any(dxi >= 0.0):
        ok = np.nonzero(dxi >= 0.0)[0]
        cutoff = int(ok[0])
        if cutoff < 100:
            raise ValueError(
                "稀疏波分支 df/dSw 在 [Swf, 1-Sor] 上不单调，无法构造连续稀疏波"
            )
        s_grid = s_grid[: cutoff + 1]
        sw_grid = sw_grid[: cutoff + 1]
        xi_grid = xi_grid[: cutoff + 1]

    # Inlet velocity at 1-Sor (0 when no > 1; finite for no = 1; divergent
    # for no < 1, in which case the finite table start is used and flagged).
    if p.no >= 1.0:
        xi_inlet = 0.0 if p.no > 1.0 else float(xi_grid[-1])
    else:
        xi_inlet = float(xi_grid[-1])

    return RarefactionTable(
        xi=xi_grid,        # decreasing: V_shock ... xi_inlet
        sw=sw_grid,        # increasing: Swf ... 1-Sor
        xi_inlet=xi_inlet,
        v_shock=sol.shock_speed,
    )


def sample_profile(
    p: RockFluid,
    sol: WelgeSolution,
    xi_values: np.ndarray | list[float],
    *,
    table: RarefactionTable | None = None,
) -> np.ndarray:
    """Return Sw at requested dimensionless positions xi.

    Convention (continuous injection at Sw = 1-Sor):

    * xi < xi_inlet        -> 1-Sor (inlet plateau)
    * xi_inlet <= xi < V  -> rarefaction, Sw interpolated from df/dSw
    * xi >= V              -> Swc (ahead of the shock)

    The value exactly at V is reported as Swc here; the jump is represented
    separately in :func:`profile_polyline`.  Note that in the rarefaction xi
    is stored decreasing, so interpolation reverses the arrays.
    """
    xi = np.asarray(xi_values, dtype=float)
    tab = table if table is not None else build_rarefaction(sol)
    sw_max = p.swi

    # xi below the inlet characteristic is the injection plateau (1-Sor);
    # xi at/above the shock is undisturbed (Swc); between them the rarefaction.
    sw = np.empty_like(xi)
    rarefied = (xi > tab.xi_inlet) & (xi < tab.v_shock)
    sw[~rarefied] = np.where(
        xi[~rarefied] >= tab.v_shock, p.swc, sw_max
    )
    if np.any(rarefied):
        sw_rare = np.interp(
            xi[rarefied], tab.xi[::-1], tab.sw[::-1],
            left=sw_max, right=sol.swf,
        )
        sw[rarefied] = sw_rare
    return sw


def profile_polyline(
    p: RockFluid,
    sol: WelgeSolution,
    *,
    table: RarefactionTable | None = None,
    xi_max: float | None = None,
    n: int = 1_001,
) -> tuple[np.ndarray, np.ndarray]:
    """(xi, Sw) polyline including a duplicated point at the shock.

    Plotting this directly yields a vertical segment at xi = V_shock between
    Swf (behind) and Swc (ahead) — the shock is never drawn as a ramp.
    """
    tab = table if table is not None else build_rarefaction(sol)
    x_hi = xi_max if xi_max is not None else sol.shock_speed * 1.25
    x_hi = max(x_hi, sol.shock_speed * 1.1, 1.0e-6)
    x_lo = max(tab.xi_inlet, 0.0)

    xi = np.linspace(x_lo, sol.shock_speed, n)
    sw = sample_profile(p, sol, xi, table=tab)

    # Rarefaction side right up to V (Swf), jump down, then ahead of front.
    xi_out = np.concatenate([
        xi,
        [sol.shock_speed, x_hi],
    ])
    sw_out = np.concatenate([
        sw,
        [p.swc, p.swc],
    ])
    # Ensure the pre-shock point is exactly Swf (numerical end of branch).
    sw_out[len(xi) - 1] = sol.swf
    return xi_out, sw_out
