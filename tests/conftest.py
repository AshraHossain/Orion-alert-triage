"""Test configuration: make ``src/`` importable and load the alert fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def alert() -> dict[str, Any]:
    """The single flagged-transaction alert every phase is built around.

    Returns:
        The parsed contents of ``alerts/alert-001.json``.
    """
    return json.loads((PROJECT_DIR / "alerts" / "alert-001.json").read_text())
