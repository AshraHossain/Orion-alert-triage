"""Tests for credibility scoring.

The update rule is an exponential moving average with a floor:
``score = max(FLOOR, (1 - ALPHA) * score + ALPHA * outcome)``, where outcome
is 1.0 for success and 0.0 for failure. The expected numbers below are that
formula worked by hand, so each one pins the constants as well as the logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from credibility import FLOOR, CredibilityStore, update


def test_a_success_at_full_trust_stays_at_full_trust() -> None:
    assert update(1.0, success=True) == pytest.approx(1.0)


def test_a_failure_at_full_trust_costs_a_fifth() -> None:
    """0.8 * 1.0 + 0.2 * 0.0 = 0.8"""
    assert update(1.0, success=False) == pytest.approx(0.8)


def test_a_success_recovers_part_of_the_loss() -> None:
    """0.8 * 0.8 + 0.2 * 1.0 = 0.84 -- not all the way back."""
    assert update(0.8, success=True) == pytest.approx(0.84)


def test_repeated_failures_stop_at_the_floor() -> None:
    score = 1.0
    for _ in range(50):
        score = update(score, success=False)

    assert score == pytest.approx(FLOOR)


def test_the_floor_applies_within_a_single_step() -> None:
    """0.8 * 0.11 = 0.088, which is below the floor, so the floor wins."""
    assert update(0.11, success=False) == pytest.approx(0.1)


def test_a_tool_at_the_floor_can_recover() -> None:
    """0.8 * 0.1 + 0.2 * 1.0 = 0.28 -- recoverable distrust, not a death sentence."""
    assert update(0.1, success=True) == pytest.approx(0.28)


def test_the_score_never_exceeds_full_trust() -> None:
    score = FLOOR
    for _ in range(200):
        score = update(score, success=True)
        assert score <= 1.0

    assert score == pytest.approx(1.0)


def test_an_unknown_tool_starts_fully_trusted() -> None:
    assert CredibilityStore().get("sanctions_screen") == pytest.approx(1.0)


def test_record_returns_the_score_before_and_after() -> None:
    """The audit trail needs both, and computing 'before' afterwards is too late."""
    store = CredibilityStore()

    before, after = store.record("adverse_media_search", success=False)

    assert before == pytest.approx(1.0)
    assert after == pytest.approx(0.8)
    assert store.get("adverse_media_search") == pytest.approx(0.8)


def test_tools_are_scored_independently() -> None:
    store = CredibilityStore()

    store.record("adverse_media_search", success=False)

    assert store.get("sanctions_screen") == pytest.approx(1.0)


def test_the_store_starts_from_given_scores() -> None:
    store = CredibilityStore({"adverse_media_search": 0.5})

    assert store.get("adverse_media_search") == pytest.approx(0.5)


def test_the_store_does_not_share_the_dict_it_was_given() -> None:
    """The same trap as the frozenset in ToolSpec, from the other direction.

    If the store kept a reference to the caller's dict, recording an outcome
    would silently rewrite a dict the caller thinks it still owns.
    """
    initial = {"adverse_media_search": 0.5}
    store = CredibilityStore(initial)

    store.record("adverse_media_search", success=True)

    assert initial == {"adverse_media_search": 0.5}


def test_scores_survive_a_save_and_load(tmp_path: Path) -> None:
    path = tmp_path / "credibility.json"
    store = CredibilityStore()
    store.record("adverse_media_search", success=False)

    store.save(path)
    reloaded = CredibilityStore.load(path)

    assert reloaded.get("adverse_media_search") == pytest.approx(0.8)
    assert reloaded.get("sanctions_screen") == pytest.approx(1.0)


def test_the_saved_file_is_plain_json(tmp_path: Path) -> None:
    """A reviewer should be able to open it and see why a tool was distrusted."""
    path = tmp_path / "credibility.json"
    store = CredibilityStore()
    store.record("adverse_media_search", success=False)

    store.save(path)

    assert json.loads(path.read_text()) == {"adverse_media_search": pytest.approx(0.8)}


def test_loading_a_missing_file_starts_fresh(tmp_path: Path) -> None:
    """The very first run has no history, and that is not an error."""
    store = CredibilityStore.load(tmp_path / "never-written.json")

    assert store.get("adverse_media_search") == pytest.approx(1.0)


def test_a_corrupt_file_is_an_error_not_a_reset(tmp_path: Path) -> None:
    """Silently starting fresh would erase every tool's history of failures.

    A tool that had earned distrust would be fully trusted again, and nothing
    would say so. Failing loudly is the safe choice.
    """
    path = tmp_path / "credibility.json"
    path.write_text("{not valid json")

    with pytest.raises(ValueError):
        CredibilityStore.load(path)
