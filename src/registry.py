"""Dynamic tool registry for ORION orchestration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    """A tool's static configuration: name, contract, permission scope, and callable.

    Frozen to prevent mutation during execution. Credibility scores live in a
    separate store (Phase 3), not here.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    run: Callable[..., Any]
    allowed_fields: frozenset[str]


class Registry:
    """Dynamic tool registry: tools can be added and removed while the system runs.

    Tools are keyed by name; names are kept sorted so the tool list is stable
    for prompt caching.
    """

    def __init__(self, specs: Iterable[ToolSpec] = ()) -> None:
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs:
            self.add(spec)

    def add(self, spec: ToolSpec) -> None:
        """Register a tool.

        Raises ValueError if a tool with this name is already registered.
        """
        if spec.name in self._specs:
            raise ValueError(f"Tool '{spec.name}' is already registered")
        self._specs[spec.name] = spec

    def remove(self, name: str) -> None:
        """Unregister a tool by name.

        Raises KeyError if the tool does not exist.
        """
        del self._specs[name]

    def get(self, name: str) -> ToolSpec:
        """Retrieve a tool spec by name.

        Raises KeyError if the tool does not exist.
        """
        return self._specs[name]

    def names(self) -> list[str]:
        """Return all registered tool names, sorted."""
        return sorted(self._specs.keys())

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._specs)

    def to_tool_params(self) -> list[dict[str, Any]]:
        """Render the registry as Anthropic API tool parameters.

        Returns tool definitions in sorted order, carrying only the fields
        the API expects: name, description, and input_schema.
        """
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
            }
            for spec_name in self.names()
            for spec in [self._specs[spec_name]]
        ]
