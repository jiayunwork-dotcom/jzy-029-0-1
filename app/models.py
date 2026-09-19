"""Pydantic models and hard-boundary validation for rock/fluid parameters."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .core.relperm import RockFluid


class ParamsInput(BaseModel):
    """Raw parameters accepted from HTTP (or file storage)."""

    model_config = ConfigDict(extra="forbid")

    mu_w: float = Field(..., description="水相粘度 [cP]，必须 > 0")
    mu_o: float = Field(..., description="油相粘度 [cP]，必须 > 0")
    swc: float = Field(..., description="束缚水饱和度，必须 >= 0")
    sor: float = Field(..., description="残余油饱和度，必须 >= 0")
    krw0: float = Field(..., description="水相端点相对渗透率，取值 (0, 1]")
    kro0: float = Field(..., description="油相端点相对渗透率，取值 (0, 1]")
    nw: float = Field(..., description="水相 Corey 幂次，必须 > 0")
    no: float = Field(..., description="油相 Corey 幂次，必须 > 0")

    @model_validator(mode="after")
    def _check_bounds(self) -> "ParamsInput":
        problems: list[str] = []
        if not (self.mu_w > 0):
            problems.append(f"水相粘度必须为正，收到 mu_w={self.mu_w}")
        if not (self.mu_o > 0):
            problems.append(f"油相粘度必须为正，收到 mu_o={self.mu_o}")
        if self.swc < 0:
            problems.append(f"束缚水饱和度不能为负，收到 swc={self.swc}")
        if self.sor < 0:
            problems.append(f"残余油饱和度不能为负，收到 sor={self.sor}")
        if not (0.0 < self.krw0 <= 1.0):
            problems.append(f"水相端点相对渗透率必须在 (0, 1]，收到 krw0={self.krw0}")
        if not (0.0 < self.kro0 <= 1.0):
            problems.append(f"油相端点相对渗透率必须在 (0, 1]，收到 kro0={self.kro0}")
        if not (self.nw > 0):
            problems.append(f"水相 Corey 幂次必须为正，收到 nw={self.nw}")
        if not (self.no > 0):
            problems.append(f"油相 Corey 幂次必须为正，收到 no={self.no}")
        if self.swc >= 0 and self.sor >= 0 and not (self.swc + self.sor < 1.0):
            problems.append(
                f"swc + sor 必须严格小于 1，收到 "
                f"{self.swc} + {self.sor} = {self.swc + self.sor}"
            )
        if problems:
            raise ValueError("；".join(problems))
        return self

    def to_rockfluid(self) -> RockFluid:
        return RockFluid(**self.model_dump())


class SolveRequest(BaseModel):
    """Body for POST /solve: either a named deck or inline params, not both."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    params: Optional[ParamsInput] = None
    xi: Optional[list[float]] = Field(
        default=None, description="调用方指定的无因次速度取样点"
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "SolveRequest":
        if (self.name is None) == (self.params is None):
            raise ValueError("必须且只能提供 name（点名物性档）或 params（当次参数）之一")
        return self
