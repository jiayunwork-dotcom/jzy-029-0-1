"""含水率分流函数 f(Sw) 及其解析导数。

流度：
    λw = krw / μw,   λo = kro / μo
分流：
    f(Sw) = λw / (λw + λo)

在归一化可动水饱和度 t = Snw ∈ (0, 1) 上（记 K = μw·kro0 / (μo·krw0)，
因为 dSw/dt = L = 1-Sor-Swc）：

    f(t)  = t**nw / (t**nw + K (1-t)**no)
    df/dt = K t**(nw-1) (1-t)**(no-1) (nw(1-t) + no t) / (t**nw + K(1-t)**no)**2
    df/dSw = (1/L) df/dt

解析导数只在可动区间内部使用；Swc 处 f 恒取 0，末端 1-Sor 处 f 恒取 1。
"""
from __future__ import annotations

from .relperm import CoreyParams, kro, krw


def mobility_water(sw: float, p: CoreyParams) -> float:
    """水流度 λw = krw/μw。"""
    return krw(sw, p) / p.mu_w


def mobility_oil(sw: float, p: CoreyParams) -> float:
    """油流度 λo = kro/μo。"""
    return kro(sw, p) / p.mu_o


def fractional_flow(sw: float, p: CoreyParams) -> float:
    """含水率分流函数 f(Sw)。

    可动区间之外：Sw <= Swc 取 0，Sw >= 1-Sor 取 1。
    端点处不依赖 0/0 的极限，直接钉死边界值（这是物理硬边界）。
    """
    if sw <= p.swc:
        return 0.0
    if sw >= p.s_orw:
        return 1.0
    lw = krw(sw, p) / p.mu_w
    lo = kro(sw, p) / p.mu_o
    return lw / (lw + lo)


def _f_of_t(t: float, p: CoreyParams) -> float:
    """归一化坐标 t ∈ (0,1) 上的 f。"""
    a = t ** p.nw
    b = (1.0 - t) ** p.no
    k = p.mu_w * p.kro0 / (p.mu_o * p.krw0)
    return a / (a + k * b)


def df_dt(t: float, p: CoreyParams) -> float:
    """归一化坐标上的解析导数 df/dt，t ∈ (0,1) 开区间。"""
    a = t ** p.nw
    b = (1.0 - t) ** p.no
    k = p.mu_w * p.kro0 / (p.mu_o * p.krw0)
    denom = a + k * b
    return (
        k
        * t ** (p.nw - 1.0)
        * (1.0 - t) ** (p.no - 1.0)
        * (p.nw * (1.0 - t) + p.no * t)
        / denom**2
    )


def df_dsw(sw: float, p: CoreyParams) -> float:
    """真实饱和度坐标上的解析导数 df/dSw = (1/L) df/dt。"""
    t = p.normalized_water(sw)
    if not 0.0 < t < 1.0:
        raise ValueError("df/dSw 仅在可动开区间 (Swc, 1-Sor) 内有定义")
    return df_dt(t, p) / p.mobile_span


def sweep_curve(p: CoreyParams, n: int = 201) -> tuple[list[float], list[float]]:
    """整条可动区间上的 (Sw, f) 取样点，用于作图。"""
    sws = [p.swc + (p.s_orw - p.swc) * i / (n - 1) for i in range(n)]
    fs = [fractional_flow(s, p) for s in sws]
    return sws, fs
