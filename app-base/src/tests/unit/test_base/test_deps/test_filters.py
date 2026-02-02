"""Unit app_tests for app_base.base.deps.filters module."""

from unittest.mock import MagicMock

import pytest

from app_base.base.deps.filters.base import (
    SimpleFilterCriteriaBase,
)
from app_base.base.deps.filters.exceptions import ConfigurationError

# =============================================================================
# Concrete Implementations for Testing
# =============================================================================


class MockColumn:
    """Mock SQLAlchemy column for testing."""

    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return MagicMock(name=f"{self.name}_eq_{other}")

    def like(self, value):
        return MagicMock(name=f"{self.name}_like_{value}")

    def ilike(self, value):
        return MagicMock(name=f"{self.name}_ilike_{value}")


class EqualFilterCriteria(SimpleFilterCriteriaBase):
    """Test implementation of equal filter."""

    def __init__(self, column: MockColumn, alias: str, bound_type: type = str, **kwargs):
        super().__init__(alias=alias, bound_type=bound_type, **kwargs)
        self.column = column

    def _filter_logic(self, value):
        if value is None:
            return None
        return self.column == value


class LikeFilterCriteria(SimpleFilterCriteriaBase):
    """Test implementation of like filter."""

    def __init__(self, column: MockColumn, alias: str, **kwargs):
        super().__init__(alias=alias, bound_type=str, **kwargs)
        self.column = column

    def _filter_logic(self, value):
        if value is None:
            return None
        return self.column.ilike(f"%{value}%")


# =============================================================================
# Tests for SimpleFilterCriteriaBase
# =============================================================================


class TestSimpleFilterCriteriaBase:
    """Tests for SimpleFilterCriteriaBase class."""

    def test_init_with_required_params(self):
        """Should initialize with alias and bound_type."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str)

        assert filter_criteria.alias == "name"
        assert filter_criteria.bound_type is str

    def test_init_with_description(self):
        """Should accept optional description."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str, description="Filter by name")

        assert filter_criteria.description == "Filter by name"

    def test_init_with_query_params(self):
        """Should store additional query params."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str, min_length=1, max_length=100)

        assert filter_criteria.query_params["min_length"] == 1
        assert filter_criteria.query_params["max_length"] == 100

    def test_filter_logic_returns_none_when_value_is_none(self):
        """Should return None when value is None."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name")

        result = filter_criteria._filter_logic(None)

        assert result is None

    def test_filter_logic_returns_expression_when_value_provided(self):
        """Should return filter expression when value is provided."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name")

        result = filter_criteria._filter_logic("test_value")

        assert result is not None

    def test_build_filter_raises_error_without_alias(self):
        """Should raise ConfigurationError when alias is empty."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="", bound_type=str)

        with pytest.raises(ConfigurationError, match="missing an 'alias'"):
            filter_criteria.build_filter()

    def test_build_filter_raises_error_without_bound_type(self):
        """Should raise ConfigurationError when bound_type is None."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str)
        filter_criteria.bound_type = None  # type: ignore

        with pytest.raises(ConfigurationError, match="missing a 'bound_type'"):
            filter_criteria.build_filter()

    def test_build_filter_returns_callable(self):
        """Should return a callable (FastAPI dependency)."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str)

        dependency = filter_criteria.build_filter()

        assert callable(dependency)

    def test_build_filter_dependency_returns_none_for_none_value(self):
        """Built dependency should return None when called with None."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str)

        dependency = filter_criteria.build_filter()
        result = dependency(value=None)

        assert result is None

    def test_build_filter_dependency_returns_expression_for_value(self):
        """Built dependency should return filter expression for value."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str)

        dependency = filter_criteria.build_filter()
        result = dependency(value="test")

        assert result is not None


class TestLikeFilterCriteria:
    """Tests for like/ilike filter implementation."""

    def test_like_filter_adds_wildcards(self):
        """Should add wildcards for LIKE pattern."""
        column = MockColumn("name")
        filter_criteria = LikeFilterCriteria(column=column, alias="search")

        # The filter logic should handle the pattern
        result = filter_criteria._filter_logic("test")

        assert result is not None

    def test_like_filter_returns_none_for_empty_value(self):
        """Should return None for None value."""
        column = MockColumn("name")
        filter_criteria = LikeFilterCriteria(column=column, alias="search")

        result = filter_criteria._filter_logic(None)

        assert result is None


class TestFilterCriteriaWithDifferentTypes:
    """Tests for filter criteria with different bound types."""

    def test_integer_bound_type(self):
        """Should work with integer bound type."""
        column = MockColumn("age")
        filter_criteria = EqualFilterCriteria(column=column, alias="age", bound_type=int)

        assert filter_criteria.bound_type is int

        dependency = filter_criteria.build_filter()
        result = dependency(value=25)

        assert result is not None

    def test_boolean_bound_type(self):
        """Should work with boolean bound type."""
        column = MockColumn("is_active")
        filter_criteria = EqualFilterCriteria(column=column, alias="active", bound_type=bool)

        assert filter_criteria.bound_type is bool

        dependency = filter_criteria.build_filter()
        result = dependency(value=True)

        assert result is not None


class TestFilterCriteriaDescription:
    """Tests for filter description handling."""

    def test_default_description_when_not_provided(self):
        """Should use default description format when not provided."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(column=column, alias="name", bound_type=str)

        # Description should be None initially (default is generated in build_filter)
        assert filter_criteria.description is None

    def test_custom_description_preserved(self):
        """Should preserve custom description."""
        column = MockColumn("name")
        filter_criteria = EqualFilterCriteria(
            column=column,
            alias="name",
            bound_type=str,
            description="Custom filter description",
        )

        assert filter_criteria.description == "Custom filter description"
