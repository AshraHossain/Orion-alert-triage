"""Credibility tracker for tools.

Each tool carries a moving-average score that moves with its observed
reliability. Scores are persisted to JSON between runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALPHA = 0.2
FLOOR = 0.1
INITIAL = 1.0


def update(score: float, outcome: int, alpha: float = ALPHA) -> float:
    """Update a score with a new outcome using exponential moving average.

    score = (1 - α) × score + α × outcome
    """
    new_score = (1 - alpha) * score + alpha * outcome
    return max(new_score, FLOOR)


class CredibilityStore:
    """In-memory store of credibility scores, backed by JSON persistence."""

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self._scores = scores or {}

    def get(self, tool_name: str) -> float:
        """Get the current score for a tool (INITIAL if unknown)."""
        return self._scores.get(tool_name, INITIAL)

    def record(self, tool_name: str, outcome: int) -> None:
        """Record an outcome for a tool and update its score."""
        current = self.get(tool_name)
        self._scores[tool_name] = update(current, outcome, alpha=ALPHA)

    def save(self, path: Path) -> None:
        """Persist scores to JSON."""
        path.write_text(json.dumps(self._scores))

    @staticmethod
    def load(path: Path) -> CredibilityStore:
        """Load scores from JSON, or start fresh if file doesn't exist."""
        if not path.exists():
            return CredibilityStore()

        data = json.loads(path.read_text())
        scores = {k: float(v) for k, v in data.items()}
        return CredibilityStore(scores)
