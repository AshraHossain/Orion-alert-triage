"""Tests for the permission scope gate.

The gate matches on argument *values*, not argument names: the model chooses
what to put in each argument, so a national ID is a leak whether it arrives in
a field called ``name``, ``query`` or anything else.

Specs are built locally rather than taken from ``build_registry()`` so these
tests pin the gate's behaviour, not any one tool's current scope.
"""

from __future__ import annotations

from typing import Any

import pytest

from registry import ToolSpec
from scope import ScopeViolation, check_scope, flatten


def spec_allowing(*fields: str, name: str = "adverse_media_search") -> ToolSpec:
    """Build a spec whose only interesting property is its scope."""
    return ToolSpec(
        name=name,
        description="scope test stand-in",
        input_schema={"type": "object", "properties": {}, "required": []},
        run=lambda **_kwargs: {},
        allowed_fields=frozenset(fields),
    )


def test_flatten_the_alert_fixture(alert: dict[str, Any]) -> None:
    """The alert is nested; the gate works on the flat form."""
    flat = flatten(alert)

    assert flat["customer.customer_id"] == "CUST-88421"
    assert flat["customer.name"] == "Marek Dvorak"
    assert flat["customer.national_id"] == "CZ-760415-2231"
    assert flat["counterparty.name"] == "Vantage Freight OU"
    assert flat["transaction.amount_usd"] == "48750.0"


def test_flatten_turns_numbers_to_strings() -> None:
    """Gate matching is on strings, so 48750.0 (float) becomes "48750.0"."""
    flat = flatten({"x": {"y": 1}})

    assert flat["x.y"] == "1"
    assert isinstance(flat["x.y"], str)


def test_flatten_skips_nested_collections() -> None:
    """Only leaf values are flattened; nested dicts and lists are skipped."""
    flat = flatten(
        {
            "a": {"b": 1, "c": {"d": 2}},
            "e": [1, 2, 3],
        }
    )

    assert "a.c" not in flat
    assert "e" not in flat
    assert flat == {"a.b": "1"}


def test_flatten_with_a_custom_prefix() -> None:
    """The prefix is prepended to all keys."""
    flat = flatten({"x": 1}, prefix="pre.")

    assert flat == {"pre.x": "1"}


def test_check_scope_permits_an_argument_within_scope() -> None:
    spec = spec_allowing("customer.name")
    arguments = {"name": "Marek Dvorak"}

    check_scope(spec, arguments, flatten({"customer": {"name": "Marek Dvorak"}}))


def test_check_scope_refuses_an_argument_outside_scope() -> None:
    spec = spec_allowing("customer.name")
    arguments = {"query": "CZ-760415-2231"}
    flat = flatten({"customer": {"national_id": "CZ-760415-2231"}})

    with pytest.raises(ScopeViolation, match="national_id"):
        check_scope(spec, arguments, flat)


def test_check_scope_matches_on_values_not_keys() -> None:
    """The argument key is irrelevant; matching is on the *value*."""
    spec = spec_allowing("customer.name")
    arguments = {"any_key": "Marek Dvorak"}
    flat = flatten({"customer": {"name": "Marek Dvorak"}})

    check_scope(spec, arguments, flat)


def test_short_values_must_equal_a_whole_field() -> None:
    """Values shorter than 4 chars don't match substrings; only exact values."""
    spec = spec_allowing("customer.country")
    flat = flatten({"customer": {"country": "CZ"}})

    arguments = {"where": "CZ"}
    check_scope(spec, arguments, flat)

    arguments = {"query": "The CZ team"}
    with pytest.raises(ScopeViolation):
        check_scope(spec, arguments, flat)


def test_longer_values_match_substrings_case_insensitively() -> None:
    """Values 4+ chars match as substrings, normalized (lower, no punctuation)."""
    spec = spec_allowing("customer.name")
    flat = flatten({"customer": {"name": "Marek Dvorak"}})

    arguments = {"query": "email@marek-dvorak.co.uk"}
    check_scope(spec, arguments, flat)

    arguments = {"query": "MAREK DVORAK"}
    check_scope(spec, arguments, flat)


def test_shared_values_are_permitted() -> None:
    """If an argument value matches a field the spec allows, it is permitted."""
    spec = spec_allowing("customer.country")
    flat = flatten({"customer": {"country": "GB"}})

    arguments = {"query": "operations in GB"}
    check_scope(spec, arguments, flat)


def test_empty_values_never_match() -> None:
    """An empty string or ``None`` in a field always matches (would be useless
    safety)."""
    spec = spec_allowing("customer.national_id")
    flat = flatten({"customer": {"national_id": ""}})

    arguments = {"query": ""}
    with pytest.raises(ScopeViolation):
        check_scope(spec, arguments, flat)

    flat = flatten({"customer": {"national_id": None}})
    arguments = {"query": "CZ-760415-2231"}

    with pytest.raises(ScopeViolation):
        check_scope(spec, arguments, flat)


def test_the_fixture_case_passes_sanctions_screen() -> None:
    """sanctions_screen has access to name and country; the call carries both."""
    from tools import build_registry

    registry = build_registry()
    spec = registry.get("sanctions_screen")
    flat = flatten({"customer": {"name": "Marek Dvorak", "country": "CZ"}})
    arguments = {"name": "Marek Dvorak", "country": "CZ"}

    check_scope(spec, arguments, flat)


def test_the_fixture_case_rejects_adverse_media_accessing_national_id() -> None:
    """adverse_media_search is not allowed the national_id; a call carrying it
    is refused."""
    from tools import build_registry

    registry = build_registry()
    spec = registry.get("adverse_media_search")
    flat = flatten(
        {
            "customer": {
                "name": "Marek Dvorak",
                "country": "CZ",
                "national_id": "CZ-760415-2231",
            }
        }
    )
    arguments = {"name": "Marek Dvorak", "country": "CZ", "national_id": "CZ-760415-2231"}

    with pytest.raises(ScopeViolation, match="national_id"):
        check_scope(spec, arguments, flat)
