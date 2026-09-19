"""参数拒绝条件：缺项、越界、非正粘度、未知档名。"""
import pytest

from app.models import ValidationError, validate_params

VALID = dict(mu_w=1.0, mu_o=1.0, swc=0.2, sor=0.2,
             krw0=1.0, kro0=1.0, nw=2.0, no=2.0)


@pytest.mark.parametrize("field,bad", [
    ("swc", -0.01),
    ("sor", -0.01),
    ("mu_w", 0.0),
    ("mu_o", -2.0),
    ("nw", 0.0),
    ("no", -1.0),
    ("krw0", 0.0),
    ("krw0", 1.5),
    ("kro0", -0.2),
])
def test_invalid_fields_rejected(field, bad):
    kw = dict(VALID)
    kw[field] = bad
    with pytest.raises(ValidationError):
        validate_params(**kw)


def test_swc_plus_sor_equals_one_rejected():
    kw = dict(VALID)
    kw.update(swc=0.6, sor=0.4)
    with pytest.raises(ValidationError, match="严格小于 1"):
        validate_params(**kw)


def test_swc_plus_sor_exceeds_one_rejected():
    kw = dict(VALID)
    kw.update(swc=0.7, sor=0.5)
    with pytest.raises(ValidationError):
        validate_params(**kw)


def test_non_numeric_rejected():
    with pytest.raises(ValidationError):
        validate_params(**{**VALID, "mu_w": "abc"})


def test_valid_params_pass():
    p = validate_params(**VALID)
    assert p.s_orw == 0.8
