"""Buckley-Leverett 饱和度剖面：激波 + 后方稀疏波。

自相似变量 ξ = x/t（无量纲推进速度，按需求约定）。Welge 解：

    0 ≤ ξ ≤ f'(1-Sor)        : Sw = 1-Sor          （末端/注入端，仅当 f'→0 退化为点）
    f'(1-Sor) < ξ < V_shock  : ξ = f'(Sw) 反解 Sw  （稀疏波/连续波，后方）
    ξ = V_shock              : Sw 由 Swf 跳变到 Swc （激波，竖直前缘）
    ξ > V_shock              : Sw = Swc            （未见水，原始含水带）

关键纪律：
    * 前缘速度只能取切线斜率 V_shock = f(Swf)/(Swf-Swc)，
      绝不能用切点当地导数 f'(Swf) 冒充——f'(Swf) 恰好等于 V_shock 是 Welge
      条件保证的，但“先有切线、后有速度”的顺序不能反；在别处（如中点）拿
      当地导数当激波速度会给出偏慢且不守恒的错误前缘。
    * 稀疏波段严格按 df/dSw 铺，连续无跳跃；
    * 禁止用中心差分把激波抹成斜坡。
"""
from __future__ import annotations

from dataclasses import dataclass

from .fractional import df_dt
from .relperm import CoreyParams
from .tangent import WelgeTangent, find_welge_tangent


class ProfileError(ValueError):
    """激波后方稀疏波构造失败（如 df/dSw 不单调，自相似解不存在）。"""


@dataclass(frozen=True)
class RarefactionPoint:
    sw: float
    xi: float


@dataclass(frozen=True)
class Profile:
    """一组物性对应的完整 BL 解。"""

    tangent: WelgeTangent
    swf: float
    shock_speed: float          # = tangent.slope，冗余给出方便调用方
    xi_rarefaction_end: float   # 稀疏波靠注入端一端的 ξ（=f'(1-Sor)，可能为 0）
    rarefaction: list[RarefactionPoint]  # 从注入端 (高 Sw) 到激波 (Swf)
    profile_polyline: list[tuple[float, float]]  # 作图折线（ξ, Sw），激波为竖直线
    samples: list[tuple[float, float]]           # 调用方 ξ 取样点上的 (ξ, Sw)

    @property
    def xi_shock(self) -> float:
        return self.shock_speed


def _speed_of_t(t: float, p: CoreyParams) -> float:
    """归一化坐标 t 处的 ξ = df/dSw。"""
    return df_dt(t, p) / p.mobile_span


def _check_rarefaction_monotonic(t_f: float, p: CoreyParams) -> None:
    """稀疏波段 t ∈ (t_f,1) 上 ξ=f'(t) 必须随 t 单调递减（ξ 随 Sw 单调递增）。"""
    grid = 2001
    prev = None
    for i in range(grid):
        t = t_f + (1.0 - t_f) * i / (grid - 1)
        if not (0.0 < t < 1.0):
            continue
        xi = _speed_of_t(t, p)
        if prev is not None and xi > prev + 1e-10:
            raise ProfileError(
                "切点后方 df/dSw 不随饱和度单调，稀疏波自相似解不存在，拒绝构造剖面。"
            )
        prev = xi


def _invert_rarefaction(xi: float, t_lo: float, t_hi: float,
                        p: CoreyParams, tol: float = 1e-12,
                        max_iter: int = 200) -> float:
    """在 t ∈ [t_lo, t_hi]（ξ 单调递减）上反解 ξ = f'(t)，返回 t。

    t_lo 对应 ξ 高端（激波侧 t_f, V_shock），t_hi 对应 ξ 低端（注入端, xi_min）。
    """
    for _ in range(max_iter):
        mid = 0.5 * (t_lo + t_hi)
        xi_mid = _speed_of_t(mid, p)
        if abs(t_hi - t_lo) < tol:
            return mid
        if xi_mid > xi:
            t_lo = mid
        else:
            t_hi = mid
    return 0.5 * (t_lo + t_hi)


def sw_at_xi(xi: float, p: CoreyParams, tangent: WelgeTangent,
             xi_min: float) -> float:
    """给定 ξ 求饱和度 Sw。

    约定：ξ ≤ 0 取注入端饱和度 1-Sor；ξ 在稀疏波段内按 f' 反解；
    ξ 越过激波（含数值容差内落在激波上）返回前缘上游 Swf；
    ξ > V_shock 返回 Swc。
    """
    v = tangent.shock_speed
    eps = 1e-9 * max(1.0, abs(v))
    if xi <= xi_min + eps:
        return p.s_orw
    if xi >= v - eps:
        # 激波位置取上游值 Swf；严格下游为 Swc
        if xi <= v + eps:
            return tangent.swf
        return p.swc
    # 稀疏波段：xi_min < xi < V_shock
    t_f = tangent.t_f
    t = _invert_rarefaction(xi, t_lo=t_f, t_hi=1.0 - 1e-13, p=p)
    return p.swc + t * p.mobile_span


def solve_profile(p: CoreyParams, xi_points: list[float] | None = None,
                  rarefaction_n: int = 121) -> Profile:
    """对一组物性求完整 Welge/Buckley-Leverett 剖面。"""
    tangent = find_welge_tangent(p)

    # 注入端一侧的 ξ：f'(1-Sor)。no>1 时为 0；no=1 时为有限正值。
    if p.no >= 1.0:
        if abs(p.no - 1.0) < 1e-12:
            t_near = 1.0 - 1e-9
            xi_min = _speed_of_t(t_near, p)
        else:
            xi_min = 0.0
    else:
        t_near = 1.0 - 1e-9
        xi_min = _speed_of_t(t_near, p)

    _check_rarefaction_monotonic(tangent.t_f, p)

    # 稀疏波采样：从注入端（t→1, ξ 低）到激波侧（t_f, ξ=V_shock）
    t_hi = 1.0 - 1e-12
    rare: list[RarefactionPoint] = []
    for i in range(rarefaction_n):
        frac = i / (rarefaction_n - 1)
        t = t_hi + (tangent.t_f - t_hi) * frac  # frac: 0→注入端, 1→激波端
        xi = _speed_of_t(t, p)
        sw = p.swc + t * p.mobile_span
        rare.append(RarefactionPoint(sw=sw, xi=xi))
    # 保证激波侧端点精确落在 V_shock、切点上
    rare[-1] = RarefactionPoint(sw=tangent.swf, xi=tangent.shock_speed)

    # 作图折线（ξ, Sw）：注入平台 -> 稀疏波 -> 激波竖直下落 -> 原始带
    polyline: list[tuple[float, float]] = []
    if xi_min > 0.0:
        polyline.append((0.0, p.s_orw))
        polyline.append((xi_min, p.s_orw))
    else:
        polyline.append((rare[0].xi, p.s_orw))
    for pt in rare:
        polyline.append((pt.xi, pt.sw))
    # 激波：从 (V_shock, Swf) 竖直跳到 (V_shock, Swc)
    polyline.append((tangent.shock_speed, p.swc))
    # 下游原始带延伸一点（用于作图，取到 V_shock 的 1.25 倍）
    polyline.append((tangent.shock_speed * 1.25 if tangent.shock_speed > 0 else 1.0,
                     p.swc))

    samples: list[tuple[float, float]] = []
    if xi_points:
        for xi in xi_points:
            samples.append((float(xi), sw_at_xi(float(xi), p, tangent, xi_min)))

    return Profile(
        tangent=tangent,
        swf=tangent.swf,
        shock_speed=tangent.shock_speed,
        xi_rarefaction_end=xi_min,
        rarefaction=rare,
        profile_polyline=polyline,
        samples=samples,
    )
