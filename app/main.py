"""FastAPI app: Buckley-Leverett fractional flow + Welge construction.

Only this process is exposed; the frontend is served as static files mounted
under / (the API lives under /api).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.welge import TangentError
from .models import ParamsInput, SolveRequest
from .service import solve_payload
from .storage import DeckExistsError, DeckStore, UnknownDeckError, validate_name

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("BL_DATA_DIR", BASE_DIR.parent / "data"))
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="一维水驱 Buckley-Leverett / Welge 服务",
    version="1.0.0",
    description="只做分流函数、Welge 切线切点和 ξ-饱和度剖面这一件事。",
)
store = DeckStore(DATA_DIR)


@app.exception_handler(TangentError)
async def _tangent_handler(_: Request, exc: TangentError) -> JSONResponse:
    return JSONResponse(status_code=422,
                        content={"detail": str(exc), "code": "tangent_failed"})


@app.exception_handler(UnknownDeckError)
async def _unknown_deck_handler(_: Request, exc: UnknownDeckError) -> JSONResponse:
    return JSONResponse(status_code=404,
                        content={"detail": str(exc), "code": "unknown_deck"})


@app.exception_handler(DeckExistsError)
async def _deck_exists_handler(_: Request, exc: DeckExistsError) -> JSONResponse:
    return JSONResponse(status_code=409,
                        content={"detail": str(exc), "code": "deck_exists"})


# ---------------------------------------------------------------- decks ----
@app.get("/api/decks", tags=["decks"], summary="列出全部物性档")
def list_decks() -> dict:
    return {"decks": {name: p.model_dump() for name, p in store.list().items()}}


@app.get("/api/decks/{name}", tags=["decks"], summary="读取一档物性")
def get_deck(name: str) -> dict:
    validate_name(name)
    return {"name": name, "params": store.get(name).model_dump()}


@app.post("/api/decks/{name}", tags=["decks"],
          summary="登记新的具名物性档（重名返回 409）", status_code=201)
def create_deck(name: str, params: ParamsInput) -> dict:
    validate_name(name)
    store.create(name, params)
    return {"name": name, "params": params.model_dump()}


@app.put("/api/decks/{name}", tags=["decks"], summary="更新或创建一具名物性档")
def put_deck(name: str, params: ParamsInput) -> dict:
    validate_name(name)
    existed = store.upsert(name, params)
    return {"name": name, "params": params.model_dump(), "updated": existed}


# ---------------------------------------------------------------- solve ----
def _resolve(name: str | None, params: ParamsInput | None) -> ParamsInput:
    if name is not None:
        return store.get(name)
    assert params is not None  # guaranteed by SolveRequest validator
    return params


@app.post("/api/solve", tags=["solve"], summary="按物性档或当次参数求完整解")
def solve(req: SolveRequest) -> dict:
    params_in = _resolve(req.name, req.params)
    payload = solve_payload(params_in.to_rockfluid(), req.xi)
    if req.name is not None:
        payload["deck"] = req.name
    return payload


@app.get("/api/solve/{name}", tags=["solve"],
         summary="点名一档直接出完整解（供页面首屏调用）")
def solve_named(name: str) -> dict:
    validate_name(name)
    params_in = store.get(name)
    payload = solve_payload(params_in.to_rockfluid())
    payload["deck"] = name
    return payload


@app.get("/api/health", tags=["meta"], summary="健康检查")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------- static ----
# Mounted last: /api routes above take precedence, everything else falls
# through to the single-page frontend.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
