"""Credibility scoring: a per-tool moving average with a floor, persisted as JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

ALPHA = 0.2
FLOOR = 0.1
INITIAL = 1.0


def update(score: float, success: bool) -> float:
    outcome = 1.0 if success else 0.0
    return max(FLOOR, (1 - ALPHA) * score + ALPHA * outcome)


class CredibilityStore:
    def __init__(self, scores: Mapping[str, float] | None = None) -> None:
        self._scores = dict(scores or {})

    def get(self, tool: str) -> float:
        return self._scores.get(tool, INITIAL)

    def record(self, tool: str, success: bool) -> tuple[float, float]:
        before = self.get(tool)
        after = update(before, success)
        self._scores[tool] = after
        return before, after

    def save(self, path: Path) -> None:
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(self._scores, indent=2, sort_keys=True))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> CredibilityStore:
        # A corrupt file raises (JSONDecodeError is a ValueError): resetting
        # would silently restore trust in tools that had earned distrust.
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text()))
