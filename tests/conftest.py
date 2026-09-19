"""测试夹具：一组标准的对称水驱参数。"""
import pytest

from app.core.relperm import CoreyParams


@pytest.fixture
def symmetric_params() -> CoreyParams:
    # 等粘度、等端点、等幂次 → f 在可动区间中点附近对称
    return CoreyParams(
        mu_w=1.0, mu_o=1.0, swc=0.2, sor=0.2,
        krw0=1.0, kro0=1.0, nw=2.0, no=2.0,
    )


@pytest.fixture
def standard_params() -> CoreyParams:
    return CoreyParams(
        mu_w=0.5, mu_o=1.0, swc=0.2, sor=0.2,
        krw0=0.3, kro0=0.9, nw=2.0, no=2.0,
    )
