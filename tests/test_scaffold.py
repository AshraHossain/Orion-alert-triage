"""Proves the project layout works before any real code exists.

If these fail, nothing else in the suite can be trusted: either ``src/`` is
not importable or the alert fixture is malformed.
"""

from __future__ import annotations

from typing import Any


def test_alert_fixture_has_the_fields_the_tools_need(alert: dict[str, Any]) -> None:
    assert alert["alert_id"] == "ALRT-2026-0917"
    assert alert["customer"]["name"] == "Marek Dvorak"
    assert alert["customer"]["country"] == "CZ"
    assert alert["customer"]["customer_id"] == "CUST-88421"


def test_alert_fixture_carries_a_restricted_field(alert: dict[str, Any]) -> None:
    """``national_id`` is the field the Phase 2 scope gate must refuse to leak.

    It is asserted here so that removing it from the fixture -- which would
    silently turn the Phase 2 tests into no-ops -- fails loudly instead.
    """
    assert alert["customer"]["national_id"] == "CZ-760415-2231"
