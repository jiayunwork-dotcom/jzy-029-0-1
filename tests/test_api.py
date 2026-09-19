"""End-to-end HTTP tests against the FastAPI app."""
from __future__ import annotations

import pytest


# ------------------------------------------------------------------ decks ---
def test_list_decks_shows_all_fields(client):
    r = client.get("/api/decks")
    assert r.status_code == 200
    decks = r.json()["decks"]
    assert "default" in decks
    required = {"mu_w", "mu_o", "swc", "sor", "krw0", "kro0", "nw", "no"}
    for name, d in decks.items():
        assert required <= set(d), name


def test_get_named_deck(client):
    r = client.get("/api/decks/default")
    assert r.status_code == 200
    assert r.json()["params"]["mu_o"] == 2.0


def test_unknown_deck_rejected_with_404(client):
    r = client.get("/api/decks/does_not_exist")
    assert r.status_code == 404
    assert r.json()["code"] == "unknown_deck"


def test_create_and_replace_deck(client):
    body = {"mu_w": 1.0, "mu_o": 3.0, "swc": 0.15, "sor": 0.2,
            "krw0": 0.9, "kro0": 1.0, "nw": 2.5, "no": 2.0}
    r = client.post("/api/decks/pytest_tmp", json=body)
    assert r.status_code == 201
    r2 = client.post("/api/decks/pytest_tmp", json=body)
    assert r2.status_code == 409
    r3 = client.put("/api/decks/pytest_tmp", json={**body, "mu_o": 5.0})
    assert r3.status_code == 200 and r3.json()["updated"] is True
    assert client.get("/api/decks/pytest_tmp").json()["params"]["mu_o"] == 5.0


def test_illegal_deck_name_rejected(client):
    r = client.get("/api/decks/..%2fevil")
    assert r.status_code in (400, 404, 422)


# ------------------------------------------------------------------ solve ---
def test_solve_named_returns_interior_swf_and_identity(client, default_params):
    r = client.get("/api/solve/default")
    assert r.status_code == 200
    d = r.json()
    lo, hi = d["mobile_interval"]["swc"], d["mobile_interval"]["sw_max"]
    assert lo < d["swf"] < hi
    assert d["f_swf"] / (d["swf"] - lo) == pytest.approx(d["tangent_slope"], abs=1e-9)
    assert d["shock_speed"] == pytest.approx(d["tangent_slope"], abs=1e-12)
    assert d["residuals"]["slope_identity"] < 1e-8
    assert d["residuals"]["global_support"] <= 1e-7


def test_solve_inline_params_and_xi_samples(client, default_params):
    body = {"params": default_params,
            "xi": [0.0, 1.0, 2.0, 5.0]}
    r = client.post("/api/solve", json=body)
    assert r.status_code == 200
    d = r.json()
    samples = d["samples"]
    assert len(samples["sw"]) == 4
    # ahead of the shock -> swc; near inlet -> 1-sor
    assert samples["sw"][3] == pytest.approx(0.2, abs=1e-12)
    assert samples["sw"][0] == pytest.approx(0.8, abs=1e-12)
    # interior rarefaction sample strictly between swf and 1-sor
    assert d["swf"] < samples["sw"][2] < 0.8


def test_solve_unknown_name_rejected(client):
    r = client.post("/api/solve", json={"name": "nope"})
    assert r.status_code == 404
    assert r.json()["code"] == "unknown_deck"


def test_solve_rejects_swc_sor_overflow(client, default_params):
    bad = {**default_params, "swc": 0.5, "sor": 0.6}
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 422
    assert "swc + sor" in r.text


def test_solve_rejects_nonpositive_viscosity(client, default_params):
    bad = {**default_params, "mu_o": 0.0}
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 422
    assert "粘度" in r.text


def test_solve_rejects_missing_fields(client):
    r = client.post("/api/solve", json={"params": {"mu_w": 1.0}})
    assert r.status_code == 422


def test_solve_rejects_when_no_interior_tangent(client, default_params):
    """nw=no=1 时 f 线性，切线退化成端点割线：必须判失败而不是凑斜坡。"""
    bad = {**default_params, "nw": 1.0, "no": 1.0}
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 422
    assert r.json()["code"] == "tangent_failed"
    assert "切" in r.json()["detail"]


def test_solve_rejects_both_name_and_params(client, default_params):
    r = client.post("/api/solve",
                    json={"name": "default", "params": default_params})
    assert r.status_code == 422


def test_endpoint_f_is_one_in_curve(client):
    d = client.get("/api/solve/default").json()
    assert d["fractional_curve"]["f"][-1] == pytest.approx(1.0, abs=1e-9)
    assert d["fractional_curve"]["f"][0] == pytest.approx(0.0, abs=1e-9)
    # curve lives inside the mobile interval only
    sw = d["fractional_curve"]["sw"]
    assert sw[0] == pytest.approx(d["mobile_interval"]["swc"], abs=1e-12)
    assert sw[-1] == pytest.approx(d["mobile_interval"]["sw_max"], abs=1e-12)


def test_profile_has_vertical_shock_pair(client):
    d = client.get("/api/solve/default").json()
    v = d["shock_speed"]
    xi, sw = d["profile"]["xi"], d["profile"]["sw"]
    # two consecutive points share xi == V but carry Swf and Swc
    hits = [i for i, x in enumerate(xi) if abs(x - v) < 1e-7]
    assert len(hits) >= 2
    vals = {round(sw[i], 6) for i in hits}
    assert round(d["swf"], 6) in vals
    assert round(d["mobile_interval"]["swc"], 6) in vals


def test_viscosity_trend_via_api(client, default_params):
    """向有利方向（mu_o 减小 => 经典流度比 M 下降、μw/μo 上升）变化时
    Swf 升高、激波后稀疏区变短（前缘变钝）。"""
    out = {}
    for mu_o in [8.0, 2.0, 0.5]:  # μw/μo = 0.125, 0.5, 2
        r = client.post("/api/solve",
                        json={"params": {**default_params, "mu_o": mu_o}})
        d = r.json()
        out[mu_o] = (d["swf"], d["shock_speed"])
    assert out[8.0][0] < out[2.0][0] < out[0.5][0]   # Swf 升高
    assert out[8.0][1] > out[2.0][1] > out[0.5][1]   # ξ_f 降低


def test_sor_shift_via_api(client, default_params):
    ends = []
    for sor in [0.1, 0.4]:
        r = client.post("/api/solve",
                        json={"params": {**default_params, "sor": sor}})
        d = r.json()
        assert r.status_code == 200
        ends.append(d["mobile_interval"]["sw_max"])
    assert ends[0] > ends[1]  # 末端左移


def test_static_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Buckley" in r.text


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
