"""HTTP 请求/响应模型（Pydantic v2）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ParamsPayload(BaseModel):
    """一组水驱物性（随请求直接提交时用）。"""

    model_config = ConfigDict(extra="forbid")

    mu_w: float = Field(..., description="水相粘度（>0）")
    mu_o: float = Field(..., description="油相粘度（>0）")
    swc: float = Field(..., description="束缚水饱和度（>=0）")
    sor: float = Field(..., description="残余油饱和度（>=0）")
    krw0: float = Field(..., description="水相端点相对渗透率 (0,1]")
    kro0: float = Field(..., description="油相端点相对渗透率 (0,1]")
    nw: float = Field(..., description="水相 Corey 幂次（>0）")
    no: float = Field(..., description="油相 Corey 幂次（>0）")


class SolveRequest(BaseModel):
    """求解请求：profile 与 params 二选一；给 xi 则在这些点上取样。"""

    model_config = ConfigDict(extra="forbid")

    profile: Optional[str] = Field(None, description="具名物性档名称")
    params: Optional[ParamsPayload] = Field(None, description="直接提交的物性")
    xi: Optional[list[float]] = Field(None, description="需要取样的无因次速度 ξ 点")


class ProfileUpsertRequest(ParamsPayload):
    name: str = Field(..., min_length=1, max_length=64, description="物性档名称")
