"""Corey relative permeabilities.

Only the mobile water interval ``[Swc, 1 - Sor]`` is ever used for the
fractional-flow / Welge construction.  Every function here assumes it has
already been validated; input validation lives in :mod:`app.models`.
"""
from __future__ import annotations

import numpy as np
from pydantic import BaseModel


class RockFluid(BaseModel):
    """Rock/fluid parameters for a Corey two-phase water/oil system."""

    mu_w: float  # water viscosity [cP]
    mu_o: float  # oil viscosity [cP]
    swc: float  # connate (irreducible) water saturation
    sor: float  # residual oil saturation
    krw0: float  # water endpoint relative permeability (at Sw = 1 - Sor)
    kro0: float  # oil endpoint relative permeability (at Sw = Swc)
    nw: float  # Corey exponent for water
    no: float  # Corey exponent for oil

    @property
    def swi(self) -> float:
        """End of the mobile interval (maximum water saturation)."""
        return 1.0 - self.sor

    @property
    def span(self) -> float:
        """Width of the mobile saturation interval."""
        return self.swi - self.swc

    def mobile_s(self, sw: np.ndarray | float) -> np.ndarray:
        """Dimensionless mobile-water saturation s = (Sw - Swc) / (1-Sor-Swc)."""
        return (np.asarray(sw, dtype=float) - self.swc) / self.span


def kr_water(p: RockFluid, sw: np.ndarray | float) -> np.ndarray:
    """Water relative permeability: krw0 * s**nw."""
    s = p.mobile_s(sw)
    return p.krw0 * np.power(s, p.nw)


def kr_oil(p: RockFluid, sw: np.ndarray | float) -> np.ndarray:
    """Oil relative permeability: kro0 * (1 - s)**no."""
    s = p.mobile_s(sw)
    return p.kro0 * np.power(1.0 - s, p.no)
