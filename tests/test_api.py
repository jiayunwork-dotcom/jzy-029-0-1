"""HTTP 层端到端测试（FastAPI TestClient）。"""
import os
import tempfile

import pytest

# 每个测试会话使用独立的物性档文件，避免污染仓库
_TMP = tempfile.mkdtemp(prefix="bl_profiles_")
os.environ["BL_PROFILES_FILE"] = os.path.join(_TMP, "profiles.json")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

VALID_PARAMS = dict(mu_w=1.0, mu_o=1.0, swc=0.2, sor=0.2,
                    krw0=1.0, kro0=1.0, nw=2.0, no=2.0)


# ---------------------------------------------------------------- 页面与健康
def test_index_page_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "Buckley" in r.text or "水驱" in r.text


def test_static_js_served():
    r = client.get("/static/app.js")
    assert r.status_code == 200


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


# ---------------------------------------------------------------- 物性档
def test_list_default_profiles():
    r = client.get("/api/profiles")
    names = r.json()["profiles"]
    assert "symmetric" in names
    for fields in names.values():
        assert {"mu_w", "mu_o", "swc", "sor", "krw0", "kro0", "nw", "no"} <= \
               set(fields)


def test_unknown_profile_rejected():
    r = client.get("/api/solve/no_such_thing")
    assert r.status_code == 404
    assert "未知物性档" in r.json()["detail"]


def test_unknown_profile_post_rejected():
    r = client.post("/api/solve", json={"profile": "ghost"})
    assert r.status_code == 404


def test_create_then_use_profile():
    r = client.put("/api/profiles/my_case",
                   json={"name": "my_case", **VALID_PARAMS})
    assert r.status_code == 201
    r2 = client.get("/api/solve/my_case")
    assert r2.status_code == 200
    assert r2.json()["profile_name"] == "my_case"


# ---------------------------------------------------------------- 求解契约
def test_solve_inline_symmetric_contract():
    r = client.post("/api/solve", json={"params": VALID_PARAMS})
    assert r.status_code == 200
    d = r.json()
    p, t = d["params"], d["tangent"]
    assert p["s_orw"] == pytest.approx(0.8)
    # 切点在可动开区间
    assert p["swc"] < t["swf"] < p["s_orw"]
    # 切线斜率 == f(Swf)/(Swf-Swc) == 激波速度
    secant = t["f_swf"] / (t["swf"] - p["swc"])
    assert t["slope"] == pytest.approx(secant, rel=1e-9)
    assert t["shock_speed"] == pytest.approx(secant, rel=1e-9)
    # 对称等幂次 nw=no=2：切点解析解 t_f = 1/√2
    assert t["swf"] == pytest.approx(0.2 + 0.6 / (2 ** 0.5), abs=1e-6)
    # 曲线末端 f=1
    ff = d["fractional_flow"]
    assert ff["sw"][-1] == pytest.approx(0.8)
    assert ff["f"][-1] == pytest.approx(1.0)
    assert ff["f"][0] == pytest.approx(0.0)
    # 切线从 (Swc,0) 出发
    assert t["line"][0] == pytest.approx({"sw": 0.2, "f": 0.0})
    # 剖面折线包含激波竖直段
    pl = d["profile"]["polyline"]
    shock_xs = [q["xi"] for q in pl if abs(q["xi"] - t["shock_speed"]) < 1e-12]
    assert len(shock_xs) >= 2  # 同一 ξ 上两个 Sw：Swf 与 Swc


def test_solve_returns_samples_at_requested_xi():
    r = client.post("/api/solve", json={"params": VALID_PARAMS,
                                        "xi": [0.0, 0.2, 9.0]})
    d = r.json()
    samples = d["samples"]
    assert [s["xi"] for s in samples] == [0.0, 0.2, 9.0]
    # ξ=0 为末端高饱和，ξ 很大为 Swc
    assert samples[0]["sw"] == pytest.approx(0.8)
    assert samples[2]["sw"] == pytest.approx(0.2)


# ---------------------------------------------------------------- 拒绝路径
def test_missing_both_profile_and_params():
    r = client.post("/api/solve", json={})
    assert r.status_code == 400


def test_inline_swc_sor_bound_rejected_over_http():
    bad = dict(VALID_PARAMS)
    bad.update(swc=0.7, sor=0.5)
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 400
    assert "严格小于 1" in r.json()["detail"]


def test_nonpositive_viscosity_rejected_over_http():
    bad = dict(VALID_PARAMS)
    bad["mu_o"] = 0.0
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 400
    assert "mu_o" in r.json()["detail"]


def test_missing_field_rejected_over_http():
    bad = dict(VALID_PARAMS)
    del bad["nw"]
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 400


def test_no_tangent_case_rejected_over_http():
    # nw=no=1：线性分流，无内部切线
    bad = dict(VALID_PARAMS)
    bad.update(nw=1.0, no=1.0)
    r = client.post("/api/solve", json={"params": bad})
    assert r.status_code == 400
    assert "切线" in r.json()["detail"]


def test_put_invalid_profile_rejected():
    bad = dict(VALID_PARAMS)
    bad["mu_w"] = -1
    r = client.put("/api/profiles/broken", json={"name": "broken", **bad})
    assert r.status_code == 400
    # 没落盘
    assert "broken" not in client.get("/api/profiles").json()["profiles"]
