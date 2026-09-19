"""Named rock/fluid decks persisted as local JSON files.

Each deck is one JSON object under ``data_dir`` (filename ``<name>.json``)
holding the eight parameter fields.  Deck names are restricted to a safe
character set so they cannot escape the data directory.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Iterator

from .models import ParamsInput

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

#: Decks created on first start so the service is useful immediately.
#: 约定：驱替“有利”指经典流度比 M=(krw0*mu_o)/(kro0*mu_w) 下降
#: （即 μw/μo 上升），此时 Swf 升高、前缘变钝。
DEFAULT_DECKS: dict[str, dict] = {
    "default": {
        "mu_w": 1.0, "mu_o": 2.0, "swc": 0.2, "sor": 0.2,
        "krw0": 1.0, "kro0": 1.0, "nw": 2.0, "no": 2.0,
    },
    "favorable": {
        # 油稀/水相对更稠：μw/μo = 2, M = 0.5 -> 高 Swf、活塞式
        "mu_w": 2.0, "mu_o": 1.0, "swc": 0.2, "sor": 0.2,
        "krw0": 0.6, "kro0": 1.0, "nw": 2.0, "no": 2.0,
    },
    "unfavorable": {
        # 油稠、水相高流动：μw/μo = 0.125, M = 8 -> 低 Swf、长指进型稀疏波
        "mu_w": 0.5, "mu_o": 4.0, "swc": 0.2, "sor": 0.2,
        "krw0": 0.3, "kro0": 1.0, "nw": 2.0, "no": 2.0,
    },
    "high_residual_oil": {
        "mu_w": 1.0, "mu_o": 2.0, "swc": 0.2, "sor": 0.4,
        "krw0": 0.8, "kro0": 1.0, "nw": 3.0, "no": 2.0,
    },
}


class UnknownDeckError(KeyError):
    """Raised when a named deck does not exist (maps to HTTP 404)."""


class DeckExistsError(ValueError):
    """Raised on POST of a deck whose name is already taken."""


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(
            "档名不合法：只允许字母/数字/下划线/点/连字符，长度 1-64，"
            "且以字母或数字开头"
        )
    return name


class DeckStore:
    """File-backed deck directory, safe for concurrent reads/writes."""

    def __init__(self, data_dir: str | Path) -> None:
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._seed()

    def _seed(self) -> None:
        with self._lock:
            for name, payload in DEFAULT_DECKS.items():
                path = self._path(name)
                if not path.exists():
                    path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

    def _path(self, name: str) -> Path:
        validate_name(name)
        return self.dir / f"{name}.json"

    def get(self, name: str) -> ParamsInput:
        path = self._path(name)
        if not path.exists():
            raise UnknownDeckError(f"未知物性档：{name!r}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ParamsInput(**payload)

    def list(self) -> dict[str, ParamsInput]:
        out: dict[str, ParamsInput] = {}
        for path in sorted(self.dir.glob("*.json")):
            try:
                out[path.stem] = ParamsInput(
                    **json.loads(path.read_text(encoding="utf-8"))
                )
            except (ValueError, json.JSONDecodeError):
                continue
        return out

    def create(self, name: str, params: ParamsInput) -> None:
        path = self._path(name)
        with self._lock:
            if path.exists():
                raise DeckExistsError(f"物性档 {name!r} 已存在")
            path.write_text(
                json.dumps(params.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def replace(self, name: str, params: ParamsInput) -> None:
        path = self._path(name)
        with self._lock:
            if not path.exists():
                raise UnknownDeckError(f"未知物性档：{name!r}")
            path.write_text(
                json.dumps(params.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def upsert(self, name: str, params: ParamsInput) -> bool:
        """Return True if the deck already existed (updated), False if created."""
        existed = self._path(name).exists()
        (self.replace if existed else self.create)(name, params)
        return existed

    def __iter__(self) -> Iterator[str]:  # pragma: no cover - trivial
        return iter(self.list())
