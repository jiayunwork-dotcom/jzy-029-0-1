"""Corey 相对渗透率。

饱和度记法：
    Sw              含水饱和度（真实值，范围 [0, 1]）
    Swc             束缚水饱和度（irreducible / connate water）
    Sor             残余油饱和度
    S_orw = 1 - Sor 可动区间的右端点（水驱末端最大含水饱和度）

可动水 / 可动油归一化饱和度（仅在 [Swc, 1-Sor] 内有物理意义）：
    Snw = (Sw - Swc) / (1 - Sor - Swc)     # 可动水
    Sno = (1 - Sor - Sw) / (1 - Sor - Swc) # 可动油 = 1 - Snw

Corey 模型（端点 k_rw0 / k_ro0 ∈ (0, 1]，幂次 nw / no > 0）：
    krw(Sw) = krw0 * Snw ** nw
    kro(Sw) = kro0 * Sno ** no
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoreyParams:
    """一组水驱物性参数。"""

    mu_w: float        # 水相粘度
    mu_o: float        # 油相粘度
    swc: float         # 束缚水饱和度
    sor: float         # 残余油饱和度
    krw0: float        # 水相端点相对渗透率（Sw = 1-Sor 处）
    kro0: float        # 油相端点相对渗透率（Sw = Swc 处）
    nw: float          # 水相 Corey 幂次
    no: float          # 油相 Corey 幂次

    @property
    def s_orw(self) -> float:
        """可动区间右端点 1 - Sor。"""
        return 1.0 - self.sor

    @property
    def mobile_span(self) -> float:
        """可动区间长度 1 - Sor - Swc。"""
        return 1.0 - self.sor - self.swc

    def normalized_water(self, sw: float) -> float:
        """可动水归一化饱和度 Snw ∈ [0, 1]。"""
        return (sw - self.swc) / self.mobile_span

    def normalized_oil(self, sw: float) -> float:
        """可动油归一化饱和度 Sno = 1 - Snw。"""
        return (self.s_orw - sw) / self.mobile_span


def krw(sw: float, p: CoreyParams) -> float:
    """水相相对渗透率 krw(Sw)。可动区间之外视为 0（端点处按 Corey 取值）。"""
    if sw < p.swc or sw > p.s_orw:
        return 0.0
    return p.krw0 * p.normalized_water(sw) ** p.nw


def kro(sw: float, p: CoreyParams) -> float:
    """油相相对渗透率 kro(Sw)。可动区间之外视为 0（端点处按 Corey 取值）。"""
    if sw < p.swc or sw > p.s_orw:
        return 0.0
    return p.kro0 * p.normalized_oil(sw) ** p.no
