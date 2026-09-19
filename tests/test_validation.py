"""Hard-boundary validation tests (parameter rejection paths)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import make_params


def expect_reject(**over):
    with pytest.raises(ValidationError) as exc:
        make_params(**over)
    return str(exc.value)


def test_negative_swc_rejected():
    msg = expect_reject(swc=-0.05)
    assert "束缚水" in msg


def test_negative_sor_rejected():
    msg = expect_reject(sor=-0.1)
    assert "残余油" in msg


def test_swc_plus_sor_ge_one_rejected():
    msg = expect_reject(swc=0.6, sor=0.4)
    assert "swc + sor" in msg
    msg2 = expect_reject(swc=0.7, sor=0.5)
    assert "swc + sor" in msg2


def test_nonpositive_viscosities_rejected():
    assert "粘度" in expect_reject(mu_w=0.0)
    assert "粘度" in expect_reject(mu_w=-1.0)
    assert "粘度" in expect_reject(mu_o=0.0)
    assert "粘度" in expect_reject(mu_o=-2.0)


def test_nonpositive_corey_exponents_rejected():
    assert "幂次" in expect_reject(nw=0.0)
    assert "幂次" in expect_reject(no=-1.5)


def test_endpoint_relperm_range_rejected():
    assert "端点" in expect_reject(krw0=0.0)
    assert "端点" in expect_reject(krw0=1.1)
    assert "端点" in expect_reject(kro0=-0.2)
    # 上界 1 允许，下界 0 不允许
    p = make_params(krw0=1.0, kro0=1.0)
    assert p.krw0 == 1.0 and p.kro0 == 1.0


def test_extra_fields_rejected():
    from app.models import ParamsInput
    base = make_params().model_dump()
    base["bogus"] = 1
    with pytest.raises(ValidationError):
        ParamsInput(**base)


def test_solve_request_requires_exactly_one_source():
    from app.models import SolveRequest
    params = make_params().model_dump()
    with pytest.raises(ValidationError):
        SolveRequest(params=params, name="default")
    with pytest.raises(ValidationError):
        SolveRequest()
    # 各自合法
    SolveRequest(name="default")
    SolveRequest(params=params)
