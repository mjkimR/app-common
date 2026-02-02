"""Unit app_tests for app_base.base.schemas.paginated module."""

from app_base.base.schemas.paginated import PaginatedList


class TestPaginatedListFirst:
    """Tests for the 'first' computed property."""

    def test_first_true_when_offset_is_zero(self):
        """Should return True when offset is 0."""
        paginated = PaginatedList(items=[], offset=0, limit=10)
        assert paginated.first is True

    def test_first_false_when_offset_is_nonzero(self):
        """Should return False when offset is not 0."""
        paginated = PaginatedList(items=[], offset=10, limit=10)
        assert paginated.first is False

    def test_first_true_with_items(self):
        """Should return True with items when offset is 0."""
        paginated = PaginatedList(items=["a", "b", "c"], offset=0, limit=10, total_count=3)
        assert paginated.first is True


class TestPaginatedListLast:
    """Tests for the 'last' computed property."""

    def test_last_true_when_no_more_items(self):
        """Should return True when current page is the last page."""
        paginated = PaginatedList(items=["a", "b"], offset=0, limit=10, total_count=2)
        assert paginated.last is True

    def test_last_false_when_more_items_exist(self):
        """Should return False when there are more items after current page."""
        paginated = PaginatedList(items=["a", "b"], offset=0, limit=2, total_count=10)
        assert paginated.last is False

    def test_last_true_when_exactly_at_end(self):
        """Should return True when offset + limit equals total_count."""
        paginated = PaginatedList(items=["a", "b"], offset=8, limit=2, total_count=10)
        assert paginated.last is True

    def test_last_true_when_past_end(self):
        """Should return True when offset + limit exceeds total_count."""
        paginated = PaginatedList(items=["a"], offset=9, limit=10, total_count=10)
        assert paginated.last is True

    def test_last_none_when_limit_is_none(self):
        """Should return None when limit is None."""
        paginated = PaginatedList(items=["a", "b"], offset=0, limit=None, total_count=10)
        assert paginated.last is None

    def test_last_none_when_total_count_is_none(self):
        """Should return None when total_count is None."""
        paginated = PaginatedList(items=["a", "b"], offset=0, limit=10, total_count=None)
        assert paginated.last is None

    def test_last_none_when_both_none(self):
        """Should return None when both limit and total_count are None."""
        paginated = PaginatedList(items=["a", "b"], offset=0, limit=None, total_count=None)
        assert paginated.last is None


class TestPaginatedListEdgeCases:
    """Edge case app_tests for PaginatedList."""

    def test_empty_items(self):
        """Should handle empty items list."""
        paginated = PaginatedList(items=[], offset=0, limit=10, total_count=0)
        assert paginated.first is True
        assert paginated.last is True
        assert len(paginated.items) == 0

    def test_single_item_single_page(self):
        """Should handle single item on single page."""
        paginated = PaginatedList(items=["item"], offset=0, limit=10, total_count=1)
        assert paginated.first is True
        assert paginated.last is True

    def test_middle_page(self):
        """Should correctly identify middle page."""
        paginated = PaginatedList(items=["a", "b"], offset=10, limit=2, total_count=100)
        assert paginated.first is False
        assert paginated.last is False

    def test_last_page_partial(self):
        """Should handle last page with fewer items than limit."""
        paginated = PaginatedList(items=["a"], offset=9, limit=2, total_count=10)
        assert paginated.first is False
        assert paginated.last is True

    def test_large_offset_beyond_total(self):
        """Should handle offset beyond total count."""
        paginated = PaginatedList(items=[], offset=100, limit=10, total_count=50)
        assert paginated.first is False
        assert paginated.last is True


class TestPaginatedListSerialization:
    """Tests for PaginatedList serialization."""

    def test_model_dump_includes_computed_fields(self):
        """Should include computed fields in model_dump."""
        paginated = PaginatedList(items=["a", "b"], offset=0, limit=10, total_count=2)
        dumped = paginated.model_dump()

        assert "first" in dumped
        assert "last" in dumped
        assert dumped["first"] is True
        assert dumped["last"] is True

    def test_model_dump_with_complex_items(self):
        """Should handle complex items in serialization."""
        items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
        paginated = PaginatedList(items=items, offset=0, limit=10, total_count=2)
        dumped = paginated.model_dump()

        assert dumped["items"] == items
        assert dumped["total_count"] == 2
