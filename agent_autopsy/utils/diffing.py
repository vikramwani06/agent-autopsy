"""Utilities for comparing and diffing span inputs/outputs."""

import json
from typing import Any


def normalize_value(value: Any) -> Any:
    """Normalize a value for comparison (handles nested dicts, lists, strings)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value.strip()
    if isinstance(value, dict):
        return {k: normalize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    return value


def shallow_diff(a: Any, b: Any) -> dict[str, Any]:
    """Compute a shallow diff between two values.

    Returns a dict with keys: 'added', 'removed', 'changed', 'unchanged'.
    Works best with dict inputs; falls back to equality check for scalars.
    """
    a_norm = normalize_value(a)
    b_norm = normalize_value(b)

    if not isinstance(a_norm, dict) or not isinstance(b_norm, dict):
        is_equal = a_norm == b_norm
        return {
            "added": {},
            "removed": {},
            "changed": {} if is_equal else {"value": {"from": a_norm, "to": b_norm}},
            "unchanged": {"value": a_norm} if is_equal else {},
        }

    a_keys = set(a_norm.keys())
    b_keys = set(b_norm.keys())

    added = {k: b_norm[k] for k in b_keys - a_keys}
    removed = {k: a_norm[k] for k in a_keys - b_keys}
    changed = {
        k: {"from": a_norm[k], "to": b_norm[k]}
        for k in a_keys & b_keys
        if a_norm[k] != b_norm[k]
    }
    unchanged = {k: a_norm[k] for k in a_keys & b_keys if a_norm[k] == b_norm[k]}

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }


def values_are_equivalent(a: Any, b: Any) -> bool:
    """Check if two values are semantically equivalent after normalization."""
    return normalize_value(a) == normalize_value(b)


def extract_keys(value: Any) -> set[str]:
    """Extract top-level keys from a value (dict or JSON string)."""
    normalized = normalize_value(value)
    if isinstance(normalized, dict):
        return set(normalized.keys())
    return set()


def is_empty_output(value: Any) -> bool:
    """Check if an output value is effectively empty."""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return True
        try:
            parsed = json.loads(stripped)
            return is_empty_output(parsed)
        except (json.JSONDecodeError, TypeError):
            return False
    if isinstance(value, dict):
        return len(value) == 0 or all(
            is_empty_output(v) for v in value.values()
        )
    if isinstance(value, list):
        return len(value) == 0
    return False
