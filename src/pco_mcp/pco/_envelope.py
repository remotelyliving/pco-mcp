"""Helpers for building list-tool response envelopes."""
from typing import Any

from pco_mcp.pco.client import PagedResult


def make_envelope(
    result: PagedResult,
    simplified: list[Any],
    filters_applied: dict[str, Any],
) -> dict[str, Any]:
    """Wrap a simplified list + PagedResult metadata into the standard envelope.

    Shape: {items, meta: {total_count, truncated, filters_applied}}.
    filters_applied mirrors the params actually sent to PCO so the model can
    see the scope of what it received.
    """
    return {
        "items": simplified,
        "meta": {
            "total_count": result.total_count,
            "truncated": result.truncated,
            "filters_applied": filters_applied,
        },
    }


def merge_filters(
    defaults: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Merge override params over defaults. None values in overrides REMOVE the default.

    Example:
        merge_filters({"filter": "future"}, {"filter": None}) == {}
        merge_filters({"filter": "future"}, {"where[x]": "y"}) == {"filter": "future", "where[x]": "y"}
    """
    merged = dict(defaults)
    for key, value in overrides.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged
