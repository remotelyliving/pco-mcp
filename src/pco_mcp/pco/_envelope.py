"""Helpers for building list-tool response envelopes."""
from typing import Any

from pco_mcp.pco.client import PagedResult


PLUMBING_KEYS: frozenset[str] = frozenset({"include", "order", "per_page"})


def make_envelope(
    result: PagedResult,
    simplified: list[Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Wrap a simplified list + PagedResult metadata into the standard envelope.

    Shape: {items, meta: {total_count, truncated, filters_applied}}.
    `params` is the full param dict sent to PCO; plumbing keys (include,
    order, per_page) are stripped so `meta.filters_applied` reflects only
    scoping filters that affect truthfulness.
    """
    filters_applied = {k: v for k, v in params.items() if k not in PLUMBING_KEYS}
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


def index_included(included: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Build a (type, id) -> record lookup from a JSON:API `included` array."""
    return {(rec["type"], rec["id"]): rec for rec in included}
