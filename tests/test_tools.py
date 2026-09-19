"""Tests for the four simulated tools.

Every tool is deterministic: the data is canned and the one failure is
scripted, so a test run never depends on chance, a clock, or a network.
"""

from __future__ import annotations

import pytest

from tools import (
    ToolTimeoutError,
    make_adverse_media_search,
    risk_score,
    sanctions_screen,
    transaction_graph,
)


def test_sanctions_screen_clears_the_fixture_customer() -> None:
    result = sanctions_screen(name="Marek Dvorak", country="CZ")

    assert result["hit"] is False
    assert result["matches"] == []
    assert "OFAC" in result["lists_checked"]


def test_sanctions_screen_hits_on_a_listed_name() -> None:
    """A tool that can only ever say 'no' proves nothing in Phase 5."""
    result = sanctions_screen(name="Vantage Freight OU", country="EE")

    assert result["hit"] is True
    assert result["matches"] != []


def test_transaction_graph_finds_a_flagged_counterparty() -> None:
    """This is one half of the conflict the Phase 5 resolver must settle."""
    result = transaction_graph(customer_id="CUST-88421")

    assert result["flagged_count"] == 1
    flagged = [c for c in result["counterparties"] if c["flagged"]]
    assert len(flagged) == 1
    assert flagged[0]["name"] == "Vantage Freight OU"
    assert flagged[0]["reason"]


def test_transaction_graph_returns_unflagged_counterparties_too() -> None:
    """A graph with nothing but flagged nodes is not a graph, it is an alarm."""
    result = transaction_graph(customer_id="CUST-88421")

    assert len(result["counterparties"]) > 1
    assert any(not c["flagged"] for c in result["counterparties"])


def test_transaction_graph_on_an_unknown_customer_is_empty_not_an_error() -> None:
    result = transaction_graph(customer_id="CUST-00000")

    assert result["counterparties"] == []
    assert result["flagged_count"] == 0


def test_adverse_media_search_times_out_on_the_first_call() -> None:
    search = make_adverse_media_search()

    with pytest.raises(ToolTimeoutError):
        search(name="Marek Dvorak", country="CZ")


def test_adverse_media_search_succeeds_on_the_retry() -> None:
    """The failure is transient — this is what makes a retry worth trying."""
    search = make_adverse_media_search()

    with pytest.raises(ToolTimeoutError):
        search(name="Marek Dvorak", country="CZ")
    result = search(name="Marek Dvorak", country="CZ")

    assert result["adverse_count"] == 2
    assert len(result["articles"]) == 2
    assert all(article["headline"] for article in result["articles"])


def test_failure_count_is_configurable() -> None:
    """Phase 3 needs a tool that always fails to drive a score to the floor."""
    search = make_adverse_media_search(fail_times=3)

    for _ in range(3):
        with pytest.raises(ToolTimeoutError):
            search(name="Marek Dvorak", country="CZ")
    assert search(name="Marek Dvorak", country="CZ")["adverse_count"] == 2


def test_a_never_failing_instance_can_be_built() -> None:
    search = make_adverse_media_search(fail_times=0)

    assert search(name="Marek Dvorak", country="CZ")["adverse_count"] == 2


def test_each_instance_counts_its_own_failures() -> None:
    """State must live in the instance, not in the module.

    A module-level counter would leak between tests and between runs: the
    second test to call it would get a pass where it expected a failure.
    """
    first = make_adverse_media_search()
    second = make_adverse_media_search()

    with pytest.raises(ToolTimeoutError):
        first(name="Marek Dvorak", country="CZ")
    first(name="Marek Dvorak", country="CZ")

    with pytest.raises(ToolTimeoutError):
        second(name="Marek Dvorak", country="CZ")


def test_an_unknown_name_returns_no_adverse_coverage() -> None:
    search = make_adverse_media_search(fail_times=0)

    result = search(name="Nobody At All", country="CZ")

    assert result["articles"] == []
    assert result["adverse_count"] == 0


def test_a_clean_customer_scores_low() -> None:
    result = risk_score(sanctions_hit=False, adverse_count=0, flagged_counterparties=0)

    assert result["score"] == 10
    assert result["band"] == "low"


def test_a_sanctions_hit_dominates_the_score() -> None:
    result = risk_score(sanctions_hit=True, adverse_count=0, flagged_counterparties=0)

    assert result["score"] == 60
    assert result["band"] == "medium"


def test_the_fixture_case_scores_medium() -> None:
    """The real case: no sanctions hit, two articles, one flagged counterparty."""
    result = risk_score(sanctions_hit=False, adverse_count=2, flagged_counterparties=1)

    assert result["score"] == 50
    assert result["band"] == "medium"


def test_evidence_accumulates_into_the_high_band() -> None:
    result = risk_score(sanctions_hit=True, adverse_count=2, flagged_counterparties=1)

    assert result["score"] == 100
    assert result["band"] == "high"


def test_the_score_is_capped_at_100() -> None:
    result = risk_score(sanctions_hit=True, adverse_count=20, flagged_counterparties=9)

    assert result["score"] == 100


@pytest.mark.parametrize(
    ("adverse_count", "expected_band"),
    [(0, "low"), (2, "low"), (3, "medium"), (5, "medium"), (9, "high")],
)
def test_band_boundaries(adverse_count: int, expected_band: str) -> None:
    result = risk_score(
        sanctions_hit=False, adverse_count=adverse_count, flagged_counterparties=0
    )

    assert result["band"] == expected_band
