"""Simulated tools for ORION alert triage.

All tools are deterministic: canned data and scripted failures for test
repeatability.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from registry import Registry, ToolSpec


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
    del country
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
        del country
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


def build_registry() -> Registry:
    """Assemble the complete registry for ORION alert triage.

    Each build returns a fresh adverse_media_search tool with its own
    failure counter, so multiple runs in one process do not interfere.
    """
    return Registry([
        ToolSpec(
            name="sanctions_screen",
            description="Screen a name and country against international sanctions lists (OFAC, EU, UN). Returns whether the name hits and which lists were checked.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The person or entity name"},
                    "country": {"type": "string", "description": "ISO country code"},
                },
                "required": ["name", "country"],
            },
            run=sanctions_screen,
            allowed_fields=frozenset(
                {"customer.name", "customer.country", "customer.date_of_birth"}
            ),
        ),
        ToolSpec(
            name="adverse_media_search",
            description="Search for adverse media coverage of a customer. Returns articles with headlines, sources and publication dates.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The person or entity name"},
                    "country": {"type": "string", "description": "ISO country code"},
                },
                "required": ["name", "country"],
            },
            run=make_adverse_media_search(),
            allowed_fields=frozenset({"customer.name", "customer.country"}),
        ),
        ToolSpec(
            name="transaction_graph",
            description="Retrieve the transaction graph for a customer. Returns known counterparties and flags those with risk indicators.",
            input_schema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The customer ID"},
                },
                "required": ["customer_id"],
            },
            run=transaction_graph,
            allowed_fields=frozenset({"customer.customer_id"}),
        ),
        ToolSpec(
            name="risk_score",
            description="Calculate overall risk from sanctions, adverse media, and transaction graph findings. Returns a score (0-100) and risk band (low/medium/high).",
            input_schema={
                "type": "object",
                "properties": {
                    "sanctions_hit": {"type": "boolean"},
                    "adverse_count": {"type": "integer"},
                    "flagged_counterparties": {"type": "integer"},
                },
                "required": ["sanctions_hit", "adverse_count", "flagged_counterparties"],
            },
            run=risk_score,
            allowed_fields=frozenset(),
        ),
    ])
