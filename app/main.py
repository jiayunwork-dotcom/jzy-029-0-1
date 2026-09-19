"""FastAPI 入口：只做 Buckley-Leverett 分流 + Welge 作图这一件事。

路由：
    GET  /                      前端页面（静态资源同进程吐出）
    GET  /api/profiles          列出具名物性档
    PUT  /api/profiles/{name}   登记/更新一档
    DELETE /api/profiles/{name} 删除一档
    POST /api/solve             对具名档或当次参数求解
    GET  /api/solve/{name}      对具名档直接求解（可带 xi 查询参数）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError as PydanticValidationError

from .core.fractional import sweep_curve
from .core.solution import Profile, solve_profile
from .core.tangent import NoTangentError
from .models import ValidationError as BLValidationError
from .schemas import ProfileUpsertRequest, SolveRequest
from . import store

app = FastAPI(
    title="一维水驱 Buckley-Leverett / Welge 分流服务",
    version="1.0.0",
    description="Corey 相对渗透率 → 含水率分流 → Welge 切线激波前缘 → ξ 饱和度剖面",
)

STATIC_DIR = Path(__file__).parent / "static"


# --------------------------------------------------------------------------- #
# 统一错误处理：缺项/越界/非正粘度/切线无解一律 400 并说明原因；未知档名 404
# --------------------------------------------------------------------------- #
@app.exception_handler(BLValidationError)
async def _bl_validation_handler(request: Request, exc: BLValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(NoTangentError)
async def _no_tangent_handler(request: Request, exc: NoTangentError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PydanticValidationError)
async def _pydantic_handler(request: Request, exc: PydanticValidationError):
    return JSONResponse(status_code=400, content={"detail": "请求参数不合法",
                                                   "errors": exc.errors()})


@app.exception_handler(RequestValidationError)
async def _request_validation_handler(request: Request, exc: RequestValidationError):
    # 缺项 / 类型错误等一律 400 并指明缺哪个字段
    missing = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()) if x != "body")
        missing.append(f"{loc or '请求体'}: {err.get('msg', '不合法')}")
    return JSONResponse(
        status_code=400,
        content={"detail": "请求参数缺项或不合法：" + "；".join(missing)},
    )


# --------------------------------------------------------------------------- #
# 序列化
# --------------------------------------------------------------------------- #
def _params_dict(p) -> dict:
    return {
        "mu_w": p.mu_w, "mu_o": p.mu_o, "swc": p.swc, "sor": p.sor,
        "krw0": p.krw0, "kro0": p.kro0, "nw": p.nw, "no": p.no,
        "s_orw": p.s_orw,
    }


def _serialize(profile: Profile, params, profile_name: Optional[str]) -> dict:
    p = params
    sws, fs = sweep_curve(p, n=201)
    (t0, f0), (t1, f1) = profile.tangent.tangent_line

    return {
        "profile_name": profile_name,
        "params": _params_dict(p),
        "fractional_flow": {"sw": sws, "f": fs},
        "tangent": {
            "swc": p.swc,
            "s_orw": p.s_orw,
            "swf": profile.swf,
            "f_swf": profile.tangent.f_swf,
            "shock_speed": profile.shock_speed,   # 激波速度
            "slope": profile.tangent.slope,       # 切线斜率（二者相等）
            "line": [{"sw": t0, "f": f0}, {"sw": t1, "f": f1}],
        },
        "profile": {
            "xi_shock": profile.xi_shock,
            "xi_rarefaction_end": profile.xi_rarefaction_end,
            "rarefaction": [
                {"sw": pt.sw, "xi": pt.xi} for pt in profile.rarefaction
            ],
            "polyline": [{"xi": xi, "sw": sw} for xi, sw in
                         profile.profile_polyline],
        },
        "samples": [{"xi": xi, "sw": sw} for xi, sw in profile.samples],
    }


def _resolve_and_solve(profile_name: Optional[str], params_payload, xi):
    if params_payload is not None:
        p = params_payload  # Pydantic payload
        from .models import validate_params
        params = validate_params(**p.model_dump())
    elif profile_name is not None:
        try:
            params, _ = store.get_profile(profile_name)
        except KeyError:
            return JSONResponse(
                status_code=404,
                content={"detail": f"未知物性档：{profile_name!r}，"
                                   f"可用档：{sorted(store.list_profiles())}"},
            )
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": "必须提供 profile（具名档）或 params（当次物性）之一"},
        )

    xi_list = None
    if xi is not None:
        xi_list = [float(x) for x in xi]
    result = solve_profile(params, xi_points=xi_list)
    return _serialize(result, params, profile_name)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/profiles")
def api_list_profiles():
    """列出全部具名档，给出粘度、Swc、Sor、端点和幂次。"""
    return {"profiles": store.list_profiles()}


@app.put("/api/profiles/{name}", status_code=201)
def api_put_profile(name: str, payload: ProfileUpsertRequest):
    if payload.name != name:
        return JSONResponse(
            status_code=400,
            content={"detail": "路径档名与请求体 name 不一致"},
        )
    fields = payload.model_dump(exclude={"name"})
    saved = store.upsert_profile(name, fields)
    return {"name": name, "params": saved}


@app.delete("/api/profiles/{name}", status_code=200)
def api_delete_profile(name: str):
    try:
        store.delete_profile(name)
    except KeyError:
        return JSONResponse(status_code=404,
                            content={"detail": f"未知物性档：{name!r}"})
    return {"deleted": name}


@app.post("/api/solve")
def api_solve(req: SolveRequest):
    result = _resolve_and_solve(req.profile, req.params, req.xi)
    if isinstance(result, JSONResponse):
        return result
    return result


@app.get("/api/solve/{name}")
def api_solve_named(name: str, xi: Optional[str] = None):
    """对具名档直接求解；xi 可用逗号分隔给出多个取样点，如 ?xi=0.1,0.5,1.2。"""
    xi_list: Optional[list[float]] = None
    if xi is not None:
        try:
            xi_list = [float(tok) for tok in xi.split(",") if tok.strip()]
        except ValueError:
            return JSONResponse(status_code=400,
                                content={"detail": "xi 查询参数必须是逗号分隔的数值"})
    result = _resolve_and_solve(name, None, xi_list)
    if isinstance(result, JSONResponse):
        return result
    return result


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# 前端静态资源（同一进程吐出，不单独起前端服务）
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
