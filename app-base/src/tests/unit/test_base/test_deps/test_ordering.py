"""Unit app_tests for app_base.base.deps.ordering module."""

from unittest.mock import MagicMock

from app_base.base.deps.ordering.base import OrderByCriteria, order_by_for

# =============================================================================
# Tests for OrderByCriteria
# =============================================================================


class TestOrderByCriteria:
    """Tests for OrderByCriteria class."""

    def test_init_with_required_params(self):
        """Should initialize with alias and func."""
        func = MagicMock(return_value="order_expression")
        criteria = OrderByCriteria(alias="created_at", func=func)

        assert criteria.alias == "created_at"
        assert criteria.func == func

    def test_init_with_description(self):
        """Should accept optional description."""
        func = MagicMock()
        criteria = OrderByCriteria(alias="created_at", func=func, description="Order by creation date")

        assert criteria.description == "Order by creation date"

    def test_call_invokes_func_with_desc_true(self):
        """Should invoke func with desc=True."""
        func = MagicMock(return_value="desc_expression")
        criteria = OrderByCriteria(alias="created_at", func=func)

        result = criteria(desc=True)

        func.assert_called_once_with(True)
        assert result == "desc_expression"  # type: ignore

    def test_call_invokes_func_with_desc_false(self):
        """Should invoke func with desc=False."""
        func = MagicMock(return_value="asc_expression")
        criteria = OrderByCriteria(alias="created_at", func=func)

        result = criteria(desc=False)

        func.assert_called_once_with(False)
        assert result == "asc_expression"  # type: ignore

    def test_repr(self):
        """Should return readable repr."""
        func = MagicMock()
        criteria = OrderByCriteria(alias="created_at", func=func)

        repr_str = repr(criteria)

        assert "OrderByCriteria" in repr_str
        assert "created_at" in repr_str


# =============================================================================
# Tests for order_by_for decorator
# =============================================================================


class TestOrderByForDecorator:
    """Tests for order_by_for decorator."""

    def test_decorator_creates_order_by_criteria(self):
        """Should create OrderByCriteria from decorated function."""

        @order_by_for(alias="created_at")
        def order_by_created_at(desc: bool):
            return MagicMock(name="created_at_order")

        assert isinstance(order_by_created_at, OrderByCriteria)
        assert order_by_created_at.alias == "created_at"

    def test_decorator_uses_function_name_as_default_alias(self):
        """Should use function name as alias when not provided."""

        @order_by_for()
        def order_by_updated_at(desc: bool):
            return MagicMock()

        assert order_by_updated_at.alias == "order_by_updated_at"

    def test_decorator_uses_docstring_as_default_description(self):
        """Should use function docstring as description when not provided."""

        @order_by_for(alias="name")
        def order_by_name(desc: bool):
            """Order by name field."""
            return MagicMock()

        assert order_by_name.description == "Order by name field."

    def test_decorator_with_explicit_description(self):
        """Should use explicit description over docstring."""

        @order_by_for(alias="name", description="Custom description")
        def order_by_name(desc: bool):
            """This docstring should be ignored."""
            return MagicMock()

        assert order_by_name.description == "Custom description"

    def test_decorated_function_is_callable(self):
        """Decorated function should be callable via OrderByCriteria."""

        @order_by_for(alias="created_at")  # type: ignore
        def order_by_created_at(desc: bool):
            if desc:
                return "created_at_desc"
            return "created_at_asc"

        assert order_by_created_at(desc=True) == "created_at_desc"  # type: ignore
        assert order_by_created_at(desc=False) == "created_at_asc"  # type: ignore

    def test_decorator_with_none_alias(self):
        """Should handle None alias by using function name."""

        @order_by_for(alias=None)
        def my_order_func(desc: bool):
            return MagicMock()

        assert my_order_func.alias == "my_order_func"


class TestOrderByCriteriaIntegration:
    """Integration app_tests for order_by functionality."""

    def test_multiple_order_by_criteria(self):
        """Should support multiple order criteria."""

        @order_by_for(alias="created_at", description="Order by creation date")  # type: ignore
        def by_created(desc: bool):
            return f"created_at {'DESC' if desc else 'ASC'}"

        @order_by_for(alias="updated_at", description="Order by update date")  # type: ignore
        def by_updated(desc: bool):
            return f"updated_at {'DESC' if desc else 'ASC'}"

        @order_by_for(alias="name", description="Order by name")  # type: ignore
        def by_name(desc: bool):
            return f"name {'DESC' if desc else 'ASC'}"

        criteria_list = [by_created, by_updated, by_name]

        assert len(criteria_list) == 3
        assert all(isinstance(c, OrderByCriteria) for c in criteria_list)

        # Test each can be called
        assert by_created(desc=True) == "created_at DESC"  # type: ignore
        assert by_updated(desc=False) == "updated_at ASC"  # type: ignore
        assert by_name(desc=True) == "name DESC"  # type: ignore
