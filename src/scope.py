"""Permission scope gate.

A tool call carries argument values chosen by the model, not alert field
paths, so the gate matches on values: a national ID is a leak whatever the
argument holding it is called.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any

from registry import ToolSpec

MIN_SUBSTRING_LENGTH = 4


class ScopeViolation(Exception):  # noqa: N818 -- name fixed by the spec
    """A tool call carries the value of an alert field outside the tool's scope."""

    def __init__(self, tool: str, fields: list[str]) -> None:
        self.tool = tool
        self.fields = fields
        super().__init__(f"{tool} may not receive: {', '.join(fields)}")


def flatten(alert: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    """Map dotted paths to every leaf value, as text."""
    flat: dict[str, str] = {}
    for key, value in alert.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(flatten(value, prefix=f"{path}."))
        else:
            flat[path] = str(value)
    return flat


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _strings(item)


def check_scope(
    spec: ToolSpec, arguments: Mapping[str, Any], alert: Mapping[str, Any]
) -> None:
    """Refuse the call if any argument carries a restricted alert value."""
    flat = {path: _normalize(value) for path, value in flatten(alert).items()}
    allowed_values = {v for path, v in flat.items() if path in spec.allowed_fields}
    restricted = {
        path: v
        for path, v in flat.items()
        if path not in spec.allowed_fields and v and v not in allowed_values
    }

    args = [_normalize(s) for s in _strings(arguments)]
    # ponytail: exact normalized matching only; an encoded or partial value
    # (base64 ID, last four digits) passes. Deliberate v1 limit per the spec.
    found = sorted(
        path
        for path, v in restricted.items()
        if any(
            v == arg if len(v) < MIN_SUBSTRING_LENGTH else v in arg for arg in args
        )
    )
    if found:
        raise ScopeViolation(spec.name, found)
