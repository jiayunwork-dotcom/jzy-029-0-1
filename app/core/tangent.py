"""Welge 作图：从束缚水点 (Swc, 0) 向分流曲线作切线。

在归一化坐标 t = (Sw - Swc)/L（L = 1-Sor-Swc）下，束缚水点对应 (0, 0)，
切线条件（切点 tf）为

    f(tf) / tf = f'(tf)        即   h(t) = t·f'(t) - f(t) = 0

激波（前缘）无因次速度：

    V_shock = f(Swf) / (Swf - Swc) = f'(Swf) 的切线斜率 = g(tf)/... 实为 g(tf)/L 的 L 倍，
    即 V_shock = g(tf)，其中 g(t) = f(t)/t（注意 t = (Sw-Swc)/L，
    故 f(Swf)/(Swf-Swc) = f(tf)/(L·tf) = g(tf)/L？——见下，按真实坐标算）。

严格按需求钉死的校验：
    V_shock == f(Swf) / (Swf - Swc)
    Swf 必须落在 (Swc, 1-Sor) 开区间内，落到端点即判失败；
    找不到内部切线（如 nw=no=1 的线性分流、幂次<1 的非 S 形曲线）一律拒绝，
    绝不拿中点饱和度凑斜坡。
"""
from __future__ import annotations

from dataclasses import dataclass

from .fractional import _f_of_t, df_dt
from .relperm import CoreyParams


class NoTangentError(ValueError):
    """在可动区间内作不出符合 Welge 条件的内部切线。"""


@dataclass(frozen=True)
class WelgeTangent:
    """Welge 切线求解结果。"""

    swf: float           # 切点（激波前缘）饱和度
    t_f: float           # 切点归一化坐标
    f_swf: float         # f(Swf)
    shock_speed: float   # 激波无因次速度 = 切线斜率
    slope: float         # 切线斜率 df/dSw 在切点处（二者相等）
    swc: float           # 切线起点 (Swc, 0)
    s_orw: float         # 可动区间右端点 1-Sor

    @property
    def tangent_line(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """作图用切线段：从 (Swc, 0) 到 (1-Sor, V·(1-Sor-Swc))。"""
        end_sw = self.s_orw
        end_f = self.shock_speed * (end_sw - self.swc)
        return (self.swc, 0.0), (end_sw, end_f)


def _g(t: float, p: CoreyParams) -> float:
    """g(t) = f(t)/t：割线斜率（归一化坐标）。"""
    return _f_of_t(t, p) / t


def _h(t: float, p: CoreyParams) -> float:
    """h(t) = t·f'(t) - f(t)：g 的驻点条件。"""
    return t * df_dt(t, p) - _f_of_t(t, p)


def _bisect_h(lo: float, hi: float, p: CoreyParams, tol: float = 1e-13,
              max_iter: int = 200) -> float:
    """在已知 h(lo) > 0、h(hi) < 0 的区间上二分求 h=0。"""
    flo = _h(lo, p)
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fm = _h(mid, p)
        if abs(hi - lo) < tol:
            return mid
        if fm > 0.0:
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def find_welge_tangent(p: CoreyParams, grid: int = 4001) -> WelgeTangent:
    """搜索内部 Welge 切点。

    步骤：
      1. 在 (0,1) 上密排网格，找 h(t) 由正变负的跨号区间（g 的极大点）；
      2. 在所有跨号区间里取 g 值最大的那个（多解时取物理的前缘分叉）；
      3. 二分精炼后，校验它是严格内部极大值，且严格高于两个端点的割线极限。
    """
    ts = [i / grid for i in range(1, grid)]  # 开区间，不含 0 和 1
    h_prev = _h(ts[0], p)

    candidates: list[tuple[float, float, float]] = []  # (g_mid, lo, hi)
    for i in range(1, len(ts)):
        t = ts[i]
        h_now = _h(t, p)
        if h_prev > 0.0 >= h_now:
            lo, hi = ts[i - 1], t
            root = _bisect_h(lo, hi, p)
            candidates.append((_g(root, p), root, root))
        h_prev = h_now

    if not candidates:
        raise NoTangentError(
            "分流曲线在可动开区间内不存在由 (Swc,0) 出发的内部切线 "
            "（h(t)=t·f'(t)-f(t) 无正变负跨号）；可能 Corey 幂次导致非 S 形分流，"
            "无法定义唯一激波前缘。"
        )

    # 取 g 最大的驻点
    candidates.sort(reverse=True)
    g_star, t_f, _ = candidates[0]

    # ---- 端点割线极限，用于确认切点是严格内部极大值 ----
    k = p.mu_w * p.kro0 / (p.mu_o * p.krw0)
    if p.nw > 1.0:
        g0 = 0.0
    elif abs(p.nw - 1.0) < 1e-12:
        g0 = 1.0 / (1.0 + k)
    else:
        # nw < 1：g(t) 在 t→0+ 发散，不可能存在有限的内部切线
        raise NoTangentError(
            "nw < 1 时割线斜率 f(t)/t 在束缚水端发散，无有限内部切线，拒绝求解。"
        )
    g1 = 1.0  # f(t)/t -> 1 (t->1-)，对 no>0 均成立（f→1, t→1）

    tol = 1e-7
    if g_star <= g0 + tol:
        raise NoTangentError("切线切点退化为束缚水端点（内部割线不高于端点极限），拒绝求解。")
    if g_star <= g1 + tol:
        raise NoTangentError("切线切点退化为末端 1-Sor（内部割线不高于端点极限），拒绝求解。")

    # 切点严格落在开区间内
    eps = 1e-9
    if not (eps < t_f < 1.0 - eps):
        raise NoTangentError("切点落在可动区间端点上，拒绝求解。")

    swf = p.swc + t_f * p.mobile_span
    f_swf = _f_of_t(t_f, p)
    # 真实饱和度坐标：V = f(Swf)/(Swf-Swc)
    shock_speed = f_swf / (swf - p.swc)
    slope = df_dt(t_f, p) / p.mobile_span  # df/dSw 在切点处，切线条件要求二者相等

    return WelgeTangent(
        swf=swf,
        t_f=t_f,
        f_swf=f_swf,
        shock_speed=shock_speed,
        slope=slope,
        swc=p.swc,
        s_orw=p.s_orw,
    )
