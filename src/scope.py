"""Permission scope gate for ORION.

The gate matches on argument *values*, not names: a leaked national ID is a leak
regardless of what parameter it's in. Matching is substring-based for long
values, exact-match only for short ones.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from registry import ToolSpec

MIN_SUBSTRING_LENGTH = 4


class ScopeViolation(ValueError):
    """A tool call carries an argument value outside the tool's scope."""


def flatten(data: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict to path → value, one level only.

    Only scalar leaf values are included; nested dicts and lists are skipped.
    All values are converted to strings.
    """
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, Mapping):
            for nested_key, nested_value in value.items():
                nested_full_key = f"{full_key}.{nested_key}"
                if not isinstance(nested_value, (dict, list, Mapping)):
                    result[nested_full_key] = str(nested_value) if nested_value is not None else ""
        elif not isinstance(value, (dict, list)):
            result[full_key] = str(value) if value is not None else ""
    return result


def _normalize(value: str) -> str:
    """Normalize a string for matching: lowercase, remove non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def check_scope(spec: ToolSpec, arguments: dict[str, Any], flat: dict[str, str]) -> None:
    """Verify that tool arguments contain no values outside the tool's scope.

    Raises ScopeViolation if any argument value matches a field the spec doesn't
    allow.
    """
    allowed = spec.allowed_fields

    for arg_value in arguments.values():
        if not isinstance(arg_value, str):
            arg_value = str(arg_value)

        arg_normalized = _normalize(arg_value)

        for field_path, field_value in flat.items():
            if not field_value:
                raise ScopeViolation(
                    f"Argument carries {field_path}={field_value}, which is outside scope {allowed}"
                )

            if field_path in allowed:
                continue

            field_normalized = _normalize(field_value)

            if len(field_value) < MIN_SUBSTRING_LENGTH:
                if arg_normalized == field_normalized:
                    raise ScopeViolation(
                        f"Argument carries {field_path}={field_value}, which is outside scope {allowed}"
                    )
            else:
                if field_normalized in arg_normalized or arg_normalized in field_normalized:
                    raise ScopeViolation(
                        f"Argument carries {field_path}={field_value}, which is outside scope {allowed}"
                    )
