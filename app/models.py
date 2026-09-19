"""物性参数校验。所有拒绝条件在这里给出明确中文原因。"""
from __future__ import annotations

from .core.relperm import CoreyParams


class ValidationError(ValueError):
    """物性参数不合法。"""


def validate_params(
    mu_w: float,
    mu_o: float,
    swc: float,
    sor: float,
    krw0: float,
    kro0: float,
    nw: float,
    no: float,
) -> CoreyParams:
    """逐项校验并构造 CoreyParams；任一硬边界不满足即拒绝。"""

    def num(name: str, v: object) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValidationError(f"参数 {name} 必须是数值")
        fv = float(v)
        if fv != fv or fv in (float("inf"), float("-inf")):
            raise ValidationError(f"参数 {name} 必须是有限数值")
        return fv

    mu_w = num("mu_w", mu_w)
    mu_o = num("mu_o", mu_o)
    swc = num("swc", swc)
    sor = num("sor", sor)
    krw0 = num("krw0", krw0)
    kro0 = num("kro0", kro0)
    nw = num("nw", nw)
    no = num("no", no)

    if mu_w <= 0:
        raise ValidationError("水相粘度 mu_w 必须严格为正")
    if mu_o <= 0:
        raise ValidationError("油相粘度 mu_o 必须严格为正")
    if swc < 0:
        raise ValidationError("束缚水饱和度 swc 不能为负")
    if sor < 0:
        raise ValidationError("残余油饱和度 sor 不能为负")
    if swc + sor >= 1.0:
        raise ValidationError(
            f"swc + sor 必须严格小于 1（当前 {swc}+{sor}={swc + sor:g}）"
        )
    if not (0.0 < krw0 <= 1.0):
        raise ValidationError("水相端点相对渗透率 krw0 必须落在 (0, 1]")
    if not (0.0 < kro0 <= 1.0):
        raise ValidationError("油相端点相对渗透率 kro0 必须落在 (0, 1]")
    if nw <= 0:
        raise ValidationError("水相 Corey 幂次 nw 必须为正")
    if no <= 0:
        raise ValidationError("油相 Corey 幂次 no 必须为正")

    return CoreyParams(
        mu_w=mu_w, mu_o=mu_o, swc=swc, sor=sor,
        krw0=krw0, kro0=kro0, nw=nw, no=no,
    )
