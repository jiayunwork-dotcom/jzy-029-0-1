"""Fractional flow function f(Sw) and its analytical derivative.

With
    krw = krw0 * s**nw,  kro = kro0 * (1-s)**no,
    s = (Sw - Swc) / span,               span = 1 - Sor - Swc,
the water fractional flow is

    f(Sw) = (krw / mu_w) / (krw / mu_w + kro / mu_o)
          = krw / (krw + R * kro),     R = mu_w / mu_o.

Mapping to the unit interval ``s in [0, 1]`` gives

    F(s) = a / (a + R b),   a = s**nw, b = (1-s)**no
    f(Sw) = F(s),   df/dSw = F'(s) / span.

F is exactly 0 at s=0 and 1 at s=1.  Derivatives at the endpoints can be
zero, finite or infinite depending on the Corey exponents, so callers must
not request :func:`df_dsw` exactly at an endpoint.
"""
from __future__ import annotations

import numpy as np

from .relperm import RockFluid


class FractionalFlow:
    """Callable fractional flow with its analytic saturation derivative."""

    def __init__(self, params: RockFluid) -> None:
        self.p = params
        self.R = params.mu_w / params.mu_o  # mu_w / mu_o
        self.krw0 = params.krw0
        self.kro0 = params.kro0
        self.nw = params.nw
        self.no = params.no
        self.span = params.span

    # -- unit-interval form -------------------------------------------------
    def _ab(self, s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        s = np.asarray(s, dtype=float)
        return np.power(s, self.nw), np.power(1.0 - s, self.no)

    def F(self, s: np.ndarray | float) -> np.ndarray:
        """Fractional flow on the mobile coordinate s in [0, 1]."""
        s = np.asarray(s, dtype=float)
        a, b = self._ab(s)
        return a / (a + self.R * (self.kro0 / self.krw0) * b)

    def dF_ds(self, s: np.ndarray | float) -> np.ndarray:
        """Analytical derivative dF/ds (valid for 0 < s < 1)."""
        s = np.asarray(s, dtype=float)
        a = np.power(s, self.nw)
        b = np.power(1.0 - s, self.no)
        k = self.R * self.kro0 / self.krw0
        denom = a + k * b
        da = self.nw * np.power(s, self.nw - 1.0)
        db = -self.no * np.power(1.0 - s, self.no - 1.0)
        # d/ds [a/(a+k b)] = (a' (a+k b) - a (a' + k b')) / denom^2
        #                  = k (a' b - a b') / denom^2
        return self.R * (self.kro0 / self.krw0) * (da * b - a * db) / (denom * denom)

    # -- physical saturation form ------------------------------------------
    def __call__(self, sw: np.ndarray | float) -> np.ndarray:
        """f(Sw); exactly 0 at Swc and exactly 1 at 1-Sor by construction."""
        sw = np.asarray(sw, dtype=float)
        s = self.p.mobile_s(sw)
        out = self.F(s)
        # Enforce endpoint values even if 0**n or 0*inf appears numerically.
        out = np.where(s <= 0.0, 0.0, out)
        out = np.where(s >= 1.0, 1.0, out)
        return out

    def df_dsw(self, sw: np.ndarray | float) -> np.ndarray:
        """df/dSw = (1/span) dF/ds, valid strictly inside the mobile interval."""
        sw = np.asarray(sw, dtype=float)
        s = self.p.mobile_s(sw)
        return self.dF_ds(s) / self.span

    def dF_ds_at_s(self, s: float) -> float:
        """Scalar derivative helper used by the tangent solver."""
        return float(self.dF_ds(np.array([s]))[0])

    def f_at_s(self, s: float) -> float:
        """Scalar f on the unit mobile coordinate."""
        return float(self.F(np.array([s]))[0])

    def sw_from_s(self, s: np.ndarray | float) -> np.ndarray:
        """Map unit mobile coordinate back to physical water saturation."""
        return self.p.swc + self.span * np.asarray(s, dtype=float)


def fractional_flow(params: RockFluid) -> FractionalFlow:
    """Convenience factory (also mirrors relperm's module-level style)."""
    return FractionalFlow(params)


def mobility_check(params: RockFluid, sw: np.ndarray | float) -> dict:
    """Return phase mobilities; useful in tests / diagnostics."""
    return {
        "krw": kr_water(params, sw),
        "kro": kr_oil(params, sw),
        "lambda_w": kr_water(params, sw) / params.mu_w,
        "lambda_o": kr_oil(params, sw) / params.mu_o,
    }
