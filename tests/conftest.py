"""Shared fixtures for the test suite."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app
from app.models import ParamsInput


@pytest.fixture(scope="session")
def client(tmp_path_factory) -> TestClient:
    # Isolate deck files from the shipped data/ directory.
    app_main.store = app_main.DeckStore(tmp_path_factory.mktemp("decks"))
    return TestClient(app)


@pytest.fixture
def default_params() -> dict:
    return {
        "mu_w": 1.0, "mu_o": 2.0, "swc": 0.2, "sor": 0.2,
        "krw0": 1.0, "kro0": 1.0, "nw": 2.0, "no": 2.0,
    }


def make_params(**over) -> ParamsInput:
    base = dict(mu_w=1.0, mu_o=2.0, swc=0.2, sor=0.2,
                krw0=1.0, kro0=1.0, nw=2.0, no=2.0)
    base.update(over)
    return ParamsInput(**base)
