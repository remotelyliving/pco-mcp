"""Tests for PagedResult and envelope helpers."""
from pco_mcp.pco._envelope import make_envelope, merge_filters
from pco_mcp.pco.client import PagedResult


class TestPagedResult:
    def test_stores_fields(self) -> None:
        pr = PagedResult(items=[1, 2, 3], total_count=10, truncated=False)
        assert pr.items == [1, 2, 3]
        assert pr.total_count == 10
        assert pr.truncated is False

    def test_iterates_like_list(self) -> None:
        pr = PagedResult(items=[1, 2, 3], total_count=None, truncated=False)
        assert list(pr) == [1, 2, 3]

    def test_len_like_list(self) -> None:
        pr = PagedResult(items=[1, 2, 3], total_count=None, truncated=False)
        assert len(pr) == 3

    def test_indexable_like_list(self) -> None:
        pr = PagedResult(items=["a", "b", "c"], total_count=None, truncated=False)
        assert pr[0] == "a"
        assert pr[-1] == "c"


class TestMakeEnvelope:
    def test_wraps_items_with_meta(self) -> None:
        pr = PagedResult(items=[{"raw": 1}], total_count=42, truncated=True)
        env = make_envelope(pr, simplified=[{"id": "1"}], params={"filter": "future"})
        assert env == {
            "items": [{"id": "1"}],
            "meta": {"total_count": 42, "truncated": True, "filters_applied": {"filter": "future"}},
        }

    def test_empty_items_still_includes_meta(self) -> None:
        pr = PagedResult(items=[], total_count=0, truncated=False)
        env = make_envelope(pr, simplified=[], params={"foo": "bar"})
        assert env["items"] == []
        assert env["meta"] == {"total_count": 0, "truncated": False, "filters_applied": {"foo": "bar"}}

    def test_none_total_count_passes_through(self) -> None:
        pr = PagedResult(items=[1], total_count=None, truncated=False)
        env = make_envelope(pr, simplified=[1], params={})
        assert env["meta"]["total_count"] is None

    def test_strips_plumbing_keys_from_filters_applied(self) -> None:
        pr = PagedResult(items=[], total_count=0, truncated=False)
        env = make_envelope(pr, simplified=[], params={
            "filter": "future",
            "include": "owner",
            "order": "starts_at",
            "per_page": 100,
            "where[x]": "y",
        })
        assert env["meta"]["filters_applied"] == {"filter": "future", "where[x]": "y"}


class TestMergeFilters:
    def test_overrides_win(self) -> None:
        result = merge_filters({"filter": "future"}, {"filter": "past"})
        assert result == {"filter": "past"}

    def test_none_value_removes_default(self) -> None:
        result = merge_filters({"filter": "future", "order": "starts_at"}, {"filter": None})
        assert result == {"order": "starts_at"}

    def test_defaults_preserved_without_override(self) -> None:
        result = merge_filters({"filter": "future"}, {})
        assert result == {"filter": "future"}

    def test_adds_new_keys_from_overrides(self) -> None:
        result = merge_filters({"filter": "future"}, {"where[starts_at][gte]": "2025-01-01"})
        assert result == {"filter": "future", "where[starts_at][gte]": "2025-01-01"}
