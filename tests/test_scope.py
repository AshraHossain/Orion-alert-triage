"""Tests for the permission scope gate.

The gate matches on argument *values*, not argument names: the model chooses
what to put in each argument, so a national ID is a leak whether it arrives in
a field called ``name``, ``query`` or anything else.

Specs are built locally rather than taken from ``build_registry()`` so these
tests pin the gate's behaviour, not any one tool's current scope.
"""

from __future__ import annotations

import copy
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


MEDIA_SCOPE = ("customer.name", "customer.country")


def test_flatten_produces_dotted_paths_to_leaf_values(alert: dict[str, Any]) -> None:
    flat = flatten(alert)

    assert flat["customer.national_id"] == "CZ-760415-2231"
    assert flat["counterparty.country"] == "EE"
    assert flat["alert_id"] == "ALRT-2026-0917"


def test_flatten_turns_every_leaf_into_a_string(alert: dict[str, Any]) -> None:
    """The gate compares text, so a number must become text first."""
    assert flatten(alert)["transaction.amount_usd"] == "48750.0"


def test_flatten_keeps_only_leaves(alert: dict[str, Any]) -> None:
    """``customer`` is a container, not a value anyone could leak."""
    flat = flatten(alert)

    assert "customer" not in flat
    assert "transaction" not in flat


def test_a_call_using_only_allowed_values_passes(alert: dict[str, Any]) -> None:
    check_scope(
        spec_allowing(*MEDIA_SCOPE),
        {"name": "Marek Dvorak", "country": "CZ"},
        alert,
    )


def test_the_national_id_is_refused(alert: dict[str, Any]) -> None:
    with pytest.raises(ScopeViolation) as caught:
        check_scope(
            spec_allowing(*MEDIA_SCOPE),
            {"name": "Marek Dvorak", "country": "CZ", "id": "CZ-760415-2231"},
            alert,
        )

    assert caught.value.tool == "adverse_media_search"
    assert caught.value.fields == ["customer.national_id"]


def test_the_refusal_message_names_the_tool_and_the_field(alert: dict[str, Any]) -> None:
    """This text is what the model reads, so it has to say what to drop."""
    with pytest.raises(ScopeViolation, match="adverse_media_search") as caught:
        check_scope(spec_allowing(*MEDIA_SCOPE), {"id": "CZ-760415-2231"}, alert)

    assert "customer.national_id" in str(caught.value)


def test_non_string_arguments_pass(alert: dict[str, Any]) -> None:
    """``risk_score`` is allowed no alert fields at all, and takes only numbers."""
    check_scope(
        spec_allowing(name="risk_score"),
        {"sanctions_hit": False, "adverse_count": 2, "flagged_counterparties": 1},
        alert,
    )


def test_declaring_a_field_the_alert_lacks_is_harmless(alert: dict[str, Any]) -> None:
    check_scope(
        spec_allowing(*MEDIA_SCOPE, "customer.middle_name"),
        {"name": "Marek Dvorak", "country": "CZ"},
        alert,
    )


def test_a_restricted_value_inside_free_text_is_refused(alert: dict[str, Any]) -> None:
    with pytest.raises(ScopeViolation) as caught:
        check_scope(
            spec_allowing(*MEDIA_SCOPE),
            {"name": "Marek Dvorak CZ-760415-2231", "country": "CZ"},
            alert,
        )

    assert caught.value.fields == ["customer.national_id"]


def test_a_reformatted_value_is_still_refused(alert: dict[str, Any]) -> None:
    """Spaces instead of hyphens, lower case: still the same ID."""
    with pytest.raises(ScopeViolation):
        check_scope(
            spec_allowing(*MEDIA_SCOPE),
            {"name": "Marek Dvorak", "country": "CZ", "id": "cz 760415 2231"},
            alert,
        )


def test_a_restricted_value_nested_in_a_structure_is_refused(
    alert: dict[str, Any],
) -> None:
    with pytest.raises(ScopeViolation) as caught:
        check_scope(
            spec_allowing(*MEDIA_SCOPE),
            {"people": [{"name": "Marek Dvorak", "ids": ["CZ-760415-2231"]}]},
            alert,
        )

    assert caught.value.fields == ["customer.national_id"]


def test_every_restricted_field_is_reported_in_sorted_order(
    alert: dict[str, Any],
) -> None:
    """Sorted, so the same bad call always produces the same message."""
    with pytest.raises(ScopeViolation) as caught:
        check_scope(
            spec_allowing(*MEDIA_SCOPE),
            {"name": "Marek Dvorak CZ-760415-2231 born 1976-04-15"},
            alert,
        )

    assert caught.value.fields == ["customer.date_of_birth", "customer.national_id"]


def test_a_short_restricted_value_inside_a_word_is_allowed(
    alert: dict[str, Any],
) -> None:
    """``EE`` is the counterparty's country, and also two letters of 'freelance'.

    Substring-matching two-letter values would refuse almost any free text.
    """
    check_scope(
        spec_allowing(*MEDIA_SCOPE),
        {"name": "Marek Dvorak", "country": "CZ", "context": "freelance consultant"},
        alert,
    )


def test_a_short_restricted_value_as_a_whole_argument_is_refused(
    alert: dict[str, Any],
) -> None:
    with pytest.raises(ScopeViolation) as caught:
        check_scope(
            spec_allowing(*MEDIA_SCOPE),
            {"name": "Marek Dvorak", "country": "EE"},
            alert,
        )

    assert caught.value.fields == ["counterparty.country"]


def test_a_value_shared_with_an_allowed_field_is_permitted(
    alert: dict[str, Any],
) -> None:
    """Customer and counterparty in one country: the gate cannot tell which was meant.

    Refusing would block every legitimate call that mentions the country.
    """
    same_country = copy.deepcopy(alert)
    same_country["counterparty"]["country"] = "CZ"

    check_scope(
        spec_allowing(*MEDIA_SCOPE),
        {"name": "Marek Dvorak", "country": "CZ"},
        same_country,
    )


def test_an_empty_restricted_value_never_matches(alert: dict[str, Any]) -> None:
    """The empty string is a substring of every string.

    Without this rule, one blank field in an alert would refuse every call.
    """
    blank_id = copy.deepcopy(alert)
    blank_id["customer"]["national_id"] = ""

    check_scope(
        spec_allowing(*MEDIA_SCOPE),
        {"name": "Marek Dvorak", "country": "CZ"},
        blank_id,
    )
