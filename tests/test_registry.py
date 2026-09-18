"""Tests for the dynamic tool registry.

No tool is actually executed here -- the registry's job is to hold specs and
render them, not to run anything. Callables are stand-ins.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from registry import Registry, ToolSpec


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


def test_registry_starts_empty() -> None:
    assert len(Registry()) == 0
    assert Registry().names() == []


def test_registry_is_built_from_an_iterable_of_specs() -> None:
    registry = Registry([make_spec("alpha"), make_spec("beta")])

    assert len(registry) == 2
    assert registry.names() == ["alpha", "beta"]


def test_names_are_sorted_so_the_tool_list_is_stable() -> None:
    """Prompt caching keys on an exact prefix, and the tool list is part of it.

    A registry that returned tools in insertion order would silently change
    the cached prefix whenever registration order changed.
    """
    registry = Registry([make_spec("zulu"), make_spec("alpha")])

    assert registry.names() == ["alpha", "zulu"]


def test_a_tool_can_be_added_while_the_system_runs() -> None:
    registry = Registry([make_spec("alpha")])

    registry.add(make_spec("beta"))

    assert registry.names() == ["alpha", "beta"]


def test_adding_a_duplicate_name_is_refused() -> None:
    """Two tools with one name means the model's call is ambiguous."""
    registry = Registry([make_spec("alpha")])

    with pytest.raises(ValueError, match="alpha"):
        registry.add(make_spec("alpha"))


def test_a_tool_can_be_removed_while_the_system_runs() -> None:
    registry = Registry([make_spec("alpha"), make_spec("beta")])

    registry.remove("alpha")

    assert registry.names() == ["beta"]


def test_removing_an_unknown_tool_is_an_error() -> None:
    with pytest.raises(KeyError, match="ghost"):
        Registry().remove("ghost")


def test_get_returns_the_spec() -> None:
    spec = make_spec("alpha")

    assert Registry([spec]).get("alpha") is spec


def test_get_on_an_unknown_tool_is_an_error() -> None:
    with pytest.raises(KeyError, match="ghost"):
        Registry().get("ghost")


def test_to_tool_params_renders_what_the_api_expects() -> None:
    """The API wants exactly name, description and input_schema — no more.

    ``allowed_fields`` is ORION's own business: the scope gate reads it, and
    sending it to the API would be a meaningless key in the request.
    """
    registry = Registry([make_spec("alpha")])

    params = registry.to_tool_params()

    assert params == [
        {
            "name": "alpha",
            "description": "description of alpha",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
    ]


def test_to_tool_params_is_sorted_like_names() -> None:
    registry = Registry([make_spec("zulu"), make_spec("alpha")])

    assert [param["name"] for param in registry.to_tool_params()] == ["alpha", "zulu"]


def test_to_tool_params_reflects_a_removed_tool() -> None:
    """This is the whole point of a *dynamic* registry."""
    registry = Registry([make_spec("alpha"), make_spec("beta")])

    registry.remove("beta")

    assert [param["name"] for param in registry.to_tool_params()] == ["alpha"]
