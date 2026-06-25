"""Unit tests for app_layer_base.base.deps.filters.prebuilt.filter_string module."""

from enum import StrEnum

import pytest
from app_layer_base.base.deps.filters.prebuilt.filter_string import (
    EnumFilter,
    StringAnyFilter,
    StringExactFilter,
    StringILikeFilter,
    StringLikeFilter,
)
from sqlalchemy import Enum, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DeclBase(DeclarativeBase):
    """Test declarative base."""

    pass


class FilterStatusEnum(StrEnum):
    """Test enum for EnumFilter tests."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class FilterTestModel(DeclBase):
    """Test model containing various field types."""

    __tablename__ = "filter_test_model"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    status: Mapped[FilterStatusEnum] = mapped_column(Enum(FilterStatusEnum))


class TestStringILikeFilter:
    """Tests for StringILikeFilter class."""

    def test_init_defaults(self):
        """Should initialize with correct default values."""
        filter_criteria = StringILikeFilter(FilterTestModel, "name")

        assert filter_criteria.model is FilterTestModel
        assert filter_criteria.field_name == "name"
        assert filter_criteria.alias == "filter_name"
        assert filter_criteria.bound_type is str
        assert (
            filter_criteria.description
            == "Filter FilterTestModel by field 'name' using case-insensitive substring match"
        )

    def test_init_custom_values(self):
        """Should accept custom alias and description."""
        filter_criteria = StringILikeFilter(
            FilterTestModel,
            "name",
            alias="custom_alias",
            description="Custom description",
        )

        assert filter_criteria.alias == "custom_alias"
        assert filter_criteria.description == "Custom description"

    def test_init_raises_value_error_for_invalid_field(self):
        """Should raise ValueError if field name does not exist on model."""
        with pytest.raises(ValueError, match="does not have a field named 'nonexistent'"):
            StringILikeFilter(FilterTestModel, "nonexistent")

    def test_filter_logic_returns_none_when_value_is_none(self):
        """Should return None when search value is None."""
        filter_criteria = StringILikeFilter(FilterTestModel, "name")
        assert filter_criteria._filter_logic(None) is None

    def test_filter_logic_returns_ilike_expression(self):
        """Should return correct case-insensitive LIKE expression."""
        filter_criteria = StringILikeFilter(FilterTestModel, "name")
        expr = filter_criteria._filter_logic("test_val")

        expected = FilterTestModel.name.ilike("%test_val%")
        assert expr is not None
        assert expr.compare(expected)


class TestStringLikeFilter:
    """Tests for StringLikeFilter class."""

    def test_init_defaults(self):
        """Should initialize with correct default values."""
        filter_criteria = StringLikeFilter(FilterTestModel, "name")

        assert filter_criteria.model is FilterTestModel
        assert filter_criteria.field_name == "name"
        assert filter_criteria.alias == "filter_name"
        assert filter_criteria.bound_type is str
        assert filter_criteria.description == "Filter FilterTestModel by field 'name' using substring match"

    def test_init_custom_values(self):
        """Should accept custom alias and description."""
        filter_criteria = StringLikeFilter(
            FilterTestModel,
            "name",
            alias="custom_alias",
            description="Custom description",
        )

        assert filter_criteria.alias == "custom_alias"
        assert filter_criteria.description == "Custom description"

    def test_init_raises_value_error_for_invalid_field(self):
        """Should raise ValueError if field name does not exist on model."""
        with pytest.raises(ValueError, match="does not have a field named 'nonexistent'"):
            StringLikeFilter(FilterTestModel, "nonexistent")

    def test_filter_logic_returns_none_when_value_is_none(self):
        """Should return None when search value is None."""
        filter_criteria = StringLikeFilter(FilterTestModel, "name")
        assert filter_criteria._filter_logic(None) is None

    def test_filter_logic_returns_like_expression(self):
        """Should return correct case-sensitive LIKE expression."""
        filter_criteria = StringLikeFilter(FilterTestModel, "name")
        expr = filter_criteria._filter_logic("test_val")

        expected = FilterTestModel.name.like("%test_val%")
        assert expr is not None
        assert expr.compare(expected)


class TestStringExactFilter:
    """Tests for StringExactFilter class."""

    def test_init_defaults(self):
        """Should initialize with correct default values."""
        filter_criteria = StringExactFilter(FilterTestModel, "name")

        assert filter_criteria.model is FilterTestModel
        assert filter_criteria.field_name == "name"
        assert filter_criteria.alias == "filter_name"
        assert filter_criteria.bound_type is str
        assert filter_criteria.description == "Filter FilterTestModel by field 'name' using exact match"

    def test_init_custom_values(self):
        """Should accept custom alias and description."""
        filter_criteria = StringExactFilter(
            FilterTestModel,
            "name",
            alias="custom_alias",
            description="Custom description",
        )

        assert filter_criteria.alias == "custom_alias"
        assert filter_criteria.description == "Custom description"

    def test_init_raises_value_error_for_invalid_field(self):
        """Should raise ValueError if field name does not exist on model."""
        with pytest.raises(ValueError, match="does not have a field named 'nonexistent'"):
            StringExactFilter(FilterTestModel, "nonexistent")

    def test_filter_logic_returns_none_when_value_is_none(self):
        """Should return None when search value is None."""
        filter_criteria = StringExactFilter(FilterTestModel, "name")
        assert filter_criteria._filter_logic(None) is None

    def test_filter_logic_returns_equality_expression(self):
        """Should return correct exact match expression."""
        filter_criteria = StringExactFilter(FilterTestModel, "name")
        expr = filter_criteria._filter_logic("test_val")

        expected = FilterTestModel.name == "test_val"
        assert expr is not None
        assert expr.compare(expected)


class TestStringAnyFilter:
    """Tests for StringAnyFilter class."""

    def test_init_defaults(self):
        """Should initialize with correct default values."""
        filter_criteria = StringAnyFilter(FilterTestModel, "name")

        assert filter_criteria.model is FilterTestModel
        assert filter_criteria.field_name == "name"
        assert filter_criteria.alias == "filter_name_any"
        assert filter_criteria.bound_type == list[str]
        assert (
            filter_criteria.description == "Filter FilterTestModel by field 'name' matching any of the provided values"
        )

    def test_init_custom_values(self):
        """Should accept custom alias and description."""
        filter_criteria = StringAnyFilter(
            FilterTestModel,
            "name",
            alias="custom_alias",
            description="Custom description",
        )

        assert filter_criteria.alias == "custom_alias"
        assert filter_criteria.description == "Custom description"

    def test_init_raises_value_error_for_invalid_field(self):
        """Should raise ValueError if field name does not exist on model."""
        with pytest.raises(ValueError, match="does not have a field named 'nonexistent'"):
            StringAnyFilter(FilterTestModel, "nonexistent")

    @pytest.mark.parametrize("invalid_val", [None, [], "not_a_list"])
    def test_filter_logic_returns_none_for_invalid_values(self, invalid_val):
        """Should return None when value is None, empty list, or not a list."""
        filter_criteria = StringAnyFilter(FilterTestModel, "name")
        assert filter_criteria._filter_logic(invalid_val) is None

    def test_filter_logic_returns_in_expression(self):
        """Should return correct IN expression for non-empty lists."""
        filter_criteria = StringAnyFilter(FilterTestModel, "name")
        expr = filter_criteria._filter_logic(["val1", "val2"])

        expected = FilterTestModel.name.in_(["val1", "val2"])
        assert expr is not None
        assert expr.compare(expected)


class TestEnumFilter:
    """Tests for EnumFilter class."""

    def test_init_defaults(self):
        """Should initialize with correct default values."""
        filter_criteria = EnumFilter(FilterTestModel, "status", FilterStatusEnum)

        assert filter_criteria.model is FilterTestModel
        assert filter_criteria.field_name == "status"
        assert filter_criteria.alias == "filter_status"
        assert filter_criteria.bound_type is FilterStatusEnum
        assert (
            filter_criteria.description == "Filter FilterTestModel by field 'status' matching FilterStatusEnum values"
        )

    def test_init_custom_values(self):
        """Should accept custom alias and description."""
        filter_criteria = EnumFilter(
            FilterTestModel,
            "status",
            FilterStatusEnum,
            alias="custom_alias",
            description="Custom description",
        )

        assert filter_criteria.alias == "custom_alias"
        assert filter_criteria.description == "Custom description"

    def test_init_raises_value_error_for_invalid_field(self):
        """Should raise ValueError if field name does not exist on model."""
        with pytest.raises(ValueError, match="does not have a field named 'nonexistent'"):
            EnumFilter(FilterTestModel, "nonexistent", FilterStatusEnum)

    def test_filter_logic_returns_none_when_value_is_none(self):
        """Should return None when search value is None."""
        filter_criteria = EnumFilter(FilterTestModel, "status", FilterStatusEnum)
        assert filter_criteria._filter_logic(None) is None

    def test_filter_logic_returns_enum_value_equality_expression(self):
        """Should return correct equality expression matching the enum's underlying value."""
        filter_criteria = EnumFilter(FilterTestModel, "status", FilterStatusEnum)
        expr = filter_criteria._filter_logic(FilterStatusEnum.ACTIVE)

        expected = FilterTestModel.status == FilterStatusEnum.ACTIVE.value
        assert expr is not None
        assert expr.compare(expected)
