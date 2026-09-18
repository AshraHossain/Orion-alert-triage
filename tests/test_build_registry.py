"""Tests for the assembled registry.

This is the seam every later phase starts from: the scope gate reads the
``allowed_fields`` asserted here, and the credibility tracker keys on these
exact tool names.
"""

from __future__ import annotations

from registry import Registry
from tools import build_registry

EXPECTED_SCOPES = {
    "sanctions_screen": frozenset(
        {"customer.name", "customer.country", "customer.date_of_birth"}
    ),
    "adverse_media_search": frozenset({"customer.name", "customer.country"}),
    "transaction_graph": frozenset({"customer.customer_id"}),
    "risk_score": frozenset(),
}


def test_all_four_tools_are_registered() -> None:
    registry = build_registry()

    assert isinstance(registry, Registry)
    assert registry.names() == [
        "adverse_media_search",
        "risk_score",
        "sanctions_screen",
        "transaction_graph",
    ]


def test_each_tool_declares_the_scope_the_gate_will_enforce() -> None:
    registry = build_registry()

    actual = {name: registry.get(name).allowed_fields for name in registry.names()}

    assert actual == EXPECTED_SCOPES


def test_adverse_media_may_not_receive_the_national_id() -> None:
    """The single most important assertion in Phase 1.

    Phase 2's gate is only as good as this declaration. If ``national_id``
    ever appears in this tool's scope, the gate will dutifully permit the
    leak it exists to prevent.
    """
    scope = build_registry().get("adverse_media_search").allowed_fields

    assert "customer.national_id" not in scope


def test_risk_score_needs_no_alert_fields_at_all() -> None:
    """It consumes other tools' findings, never the customer's data."""
    assert build_registry().get("risk_score").allowed_fields == frozenset()


def test_every_tool_has_a_description_the_model_can_act_on() -> None:
    registry = build_registry()

    for param in registry.to_tool_params():
        assert len(param["description"]) > 40, param["name"]
        assert param["input_schema"]["type"] == "object"


def test_each_build_gets_a_fresh_adverse_media_tool() -> None:
    """Two runs in one process must not share a failure counter.

    Without this, the second run in a batch would never see the timeout, and
    the retry path would silently stop being exercised.
    """
    first = build_registry().get("adverse_media_search").run
    second = build_registry().get("adverse_media_search").run

    assert first is not second
