"""Simulated tools for ORION alert triage.

All tools are deterministic: canned data and scripted failures for test
repeatability.
"""

from __future__ import annotations

from typing import Any, Callable


class ToolTimeoutError(RuntimeError):
    """Tool failed with a transient error (network, timeout, rate-limit)."""


_WATCHLIST = {"vantage freight ou"}
_LISTS = ["OFAC", "EU", "UN"]
_CUSTOMERS = {
    "CUST-88421": [
        {
            "name": "Acme Trading Ltd",
            "country": "GB",
            "flagged": False,
        },
        {
            "name": "Vantage Freight OU",
            "country": "EE",
            "flagged": True,
            "reason": "Listed on sanctions watchlist",
        },
        {
            "name": "Sterling Logistics",
            "country": "US",
            "flagged": False,
        },
    ]
}


def sanctions_screen(name: str, country: str) -> dict[str, Any]:
    """Screen a name and country against international sanctions lists.

    Returns whether the name hits any list and which lists were checked.
    Matching is case-insensitive.
    """
    normalized = name.lower()
    hit = normalized in _WATCHLIST
    matches = [name] if hit else []
    return {
        "hit": hit,
        "matches": matches,
        "lists_checked": _LISTS,
    }


def transaction_graph(customer_id: str) -> dict[str, Any]:
    """Retrieve the transaction graph for a customer.

    Returns known counterparties, flagged status, and reason if flagged.
    Unknown customers return an empty graph.
    """
    counterparties = _CUSTOMERS.get(customer_id, [])
    flagged_count = sum(1 for c in counterparties if c.get("flagged", False))
    return {
        "counterparties": counterparties,
        "flagged_count": flagged_count,
    }


def make_adverse_media_search(fail_times: int = 1) -> Callable[[str, str], dict[str, Any]]:
    """Factory for the adverse media search tool.

    Returns a stateful callable that fails on its first `fail_times` calls,
    then succeeds. Each instance maintains its own failure count.
    """
    calls = 0

    def search(name: str, country: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1

        if calls <= fail_times:
            raise ToolTimeoutError(f"Search timeout on attempt {calls}")

        articles = []
        if name == "Marek Dvorak":
            articles = [
                {
                    "headline": "Czech businessman under investigation",
                    "source": "Reuters",
                    "published": "2026-09-01",
                },
                {
                    "headline": "New sanctions on Eastern European entities",
                    "source": "Bloomberg",
                    "published": "2026-08-15",
                },
            ]

        return {
            "articles": articles,
            "adverse_count": len(articles),
        }

    return search


def risk_score(
    sanctions_hit: bool, adverse_count: int, flagged_counterparties: int
) -> dict[str, Any]:
    """Calculate overall risk based on three dimensions.

    Sanctions hits dominate; adverse media and flagged counterparties add up.
    Base score is 10 (no alert reaches triage at zero risk).
    """
    score = min(
        100,
        10
        + (50 if sanctions_hit else 0)
        + 10 * adverse_count
        + 20 * flagged_counterparties,
    )

    if score >= 70:
        band = "high"
    elif score >= 40:
        band = "medium"
    else:
        band = "low"

    return {
        "score": score,
        "band": band,
    }
