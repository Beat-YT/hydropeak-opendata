"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def summer_feed() -> Any:
    """The real feed as served in August 2026 (business-only events)."""
    return load_fixture("feed_summer_2026.json")


@pytest.fixture
def winter_feed() -> Any:
    """A winter-shaped feed with residential (CPC-D / TPC-DPC) events."""
    return load_fixture("feed_winter.json")
