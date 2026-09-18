"""Tests for the dynamic tool registry.

No tool is actually executed here -- the registry's job is to hold specs and
render them, not to run anything. Callables are stand-ins.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from registry import ToolSpec


def make_spec(name: str = "sanctions_screen") -> ToolSpec:
    """Build a throwaway spec for registry tests."""
    return ToolSpec(
        name=name,
        description=f"description of {name}",
        input_schema={"type": "object", "properties": {}, "required": []},
        run=lambda **_kwargs: {"ok": True},
        allowed_fields=frozenset({"customer.name"}),
    )


def test_tool_spec_carries_its_permission_scope() -> None:
    spec = make_spec()

    assert spec.name == "sanctions_screen"
    assert spec.allowed_fields == frozenset({"customer.name"})
    assert spec.run() == {"ok": True}


def test_tool_spec_is_immutable() -> None:
    """A spec is configuration, not state.

    Phase 3 keeps credibility scores in their own store precisely so that
    nothing mutates a spec mid-run; freezing it makes that impossible rather
    than merely discouraged.
    """
    spec = make_spec()

    with pytest.raises(FrozenInstanceError):
        spec.name = "something_else"  # type: ignore[misc]
