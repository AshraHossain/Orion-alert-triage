"""Dynamic tool registry for ORION orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


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
