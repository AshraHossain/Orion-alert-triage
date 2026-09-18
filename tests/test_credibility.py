"""Tests for the credibility tracker.

The tracker holds a moving-average score per tool, with a floor, and persists
to JSON so scores survive between runs.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from credibility import CredibilityStore, update


ALPHA = 0.2
FLOOR = 0.1
INITIAL = 1.0


def test_update_the_credibility_rule() -> None:
    """score = (1 - α) × score + α × outcome."""
    score = update(1.0, outcome=1, alpha=ALPHA)
    assert score == 0.8 * 1.0 + 0.2 * 1


def test_update_a_failing_tool_tanks_the_score() -> None:
    """A tool that fails goes from 1.0 to 0.2."""
    score = update(1.0, outcome=0, alpha=ALPHA)
    assert score == 0.8 * 1.0 + 0.2 * 0


def test_update_floor_prevents_scores_below_0_1() -> None:
    """Even after five failures, the floor is 0.1, not 0."""
    score = 1.0
    for _ in range(10):
        score = update(score, outcome=0, alpha=ALPHA)
        assert score >= FLOOR


def test_update_recovery_from_the_floor() -> None:
    """A tool at the floor recovers with successes."""
    score = FLOOR
    score = update(score, outcome=1, alpha=ALPHA)
    assert score > FLOOR


def test_credibility_store_starts_empty() -> None:
    store = CredibilityStore()

    assert store.get("sanctions_screen") == INITIAL


def test_credibility_store_records_an_outcome() -> None:
    store = CredibilityStore()
    store.record("sanctions_screen", outcome=1)

    assert store.get("sanctions_screen") == update(INITIAL, outcome=1, alpha=ALPHA)


def test_credibility_store_persists_to_json() -> None:
    """Scores survive a round-trip through JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "scores.json"

        store = CredibilityStore()
        store.record("sanctions_screen", outcome=0)
        store.record("transaction_graph", outcome=1)
        store.save(path)

        assert path.exists()

        new_store = CredibilityStore.load(path)
        assert new_store.get("sanctions_screen") == store.get("sanctions_screen")
        assert new_store.get("transaction_graph") == store.get("transaction_graph")


def test_credibility_store_fresh_load_gives_initial_for_unknown_tools() -> None:
    """A tool not yet in the store has INITIAL score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "scores.json"
        path.write_text("{}")

        store = CredibilityStore.load(path)
        assert store.get("unknown_tool") == INITIAL


def test_credibility_store_load_on_missing_file_starts_fresh() -> None:
    """If the store file doesn't exist, start with empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nonexistent.json"

        store = CredibilityStore.load(path)
        assert store.get("any_tool") == INITIAL


def test_credibility_store_multiple_outcomes_converge() -> None:
    """Many outcomes converge the score to their average."""
    store = CredibilityStore()

    for _ in range(100):
        store.record("sanctions_screen", outcome=1)
        store.record("transaction_graph", outcome=0)

    s1 = store.get("sanctions_screen")
    s2 = store.get("transaction_graph")

    assert s1 > 0.5
    assert s2 < 0.5
