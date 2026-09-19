"""具名物性档：本地 JSON 文件持久化。

文件位置由环境变量 BL_PROFILES_FILE 指定，默认落在工作目录 data/profiles.json。
服务启动时若文件不存在，则写入内置的几档参考参数。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .models import validate_params

_LOCK = threading.Lock()

# 物性档字段（与 CoreyParams 对应）
FIELDS = ("mu_w", "mu_o", "swc", "sor", "krw0", "kro0", "nw", "no")

DEFAULT_PROFILES: dict[str, dict[str, float]] = {
    # 对称基准：等粘度、等幂次、等端点 —— f 在可动区间中点附近对称
    "symmetric": {
        "mu_w": 1.0, "mu_o": 1.0, "swc": 0.2, "sor": 0.2,
        "krw0": 1.0, "kro0": 1.0, "nw": 2.0, "no": 2.0,
    },
    # 常规油藏水驱：油比水粘（4:1），M≈12，不利流度比，前缘锐、易早期水窜
    "standard": {
        "mu_w": 1.0, "mu_o": 4.0, "swc": 0.2, "sor": 0.2,
        "krw0": 0.3, "kro0": 0.9, "nw": 2.0, "no": 2.0,
    },
    # 有利流度比（增粘水/聚合物式）：M≈0.75，Swf 升高、前缘变钝、趋活塞式
    "favorable": {
        "mu_w": 4.0, "mu_o": 1.0, "swc": 0.2, "sor": 0.2,
        "krw0": 0.3, "kro0": 0.9, "nw": 2.0, "no": 2.0,
    },
    # 高粘原油：水油粘度比很低，极不利，前缘贴向束缚水
    "heavy_oil": {
        "mu_w": 0.2, "mu_o": 5.0, "swc": 0.15, "sor": 0.15,
        "krw0": 0.2, "kro0": 1.0, "nw": 2.5, "no": 2.0,
    },
}


def profiles_path() -> Path:
    return Path(os.environ.get("BL_PROFILES_FILE", "data/profiles.json"))


def _ensure_file() -> Path:
    path = profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            json.dumps(DEFAULT_PROFILES, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return path


def _load_raw() -> dict[str, dict[str, float]]:
    path = _ensure_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"物性档文件损坏：{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("物性档文件顶层必须是对象 {name: params}")
    return data


def _write_raw(data: dict[str, dict[str, float]]) -> None:
    path = _ensure_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def list_profiles() -> dict[str, dict[str, float]]:
    """列出全部具名档（原始字段，附带校验后的值）。"""
    with _LOCK:
        return {name: dict(params) for name, params in _load_raw().items()}


def get_profile(name: str):
    """按名取档；不存在抛 KeyError。返回校验后的 CoreyParams 与原始字段。"""
    with _LOCK:
        raw = _load_raw()
    if name not in raw:
        raise KeyError(name)
    params = raw[name]
    p = validate_params(**{k: params[k] for k in FIELDS})
    return p, dict(params)


def upsert_profile(name: str, fields: dict[str, float]) -> dict[str, float]:
    """登记或更新一档；字段先过校验再落盘。返回规范化后的字段。"""
    clean = {k: float(fields[k]) for k in FIELDS}
    validate_params(**clean)  # 拒绝则不落盘
    with _LOCK:
        raw = _load_raw()
        raw[name] = clean
        _write_raw(raw)
    return dict(clean)


def delete_profile(name: str) -> None:
    with _LOCK:
        raw = _load_raw()
        if name not in raw:
            raise KeyError(name)
        del raw[name]
        _write_raw(raw)
