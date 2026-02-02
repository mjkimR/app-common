from typing import Callable, Optional

from sqlalchemy.sql import ColumnElement

# Type alias for the ordering logic function: takes a boolean (desc) and returns a SQLAlchemy expression.
OrderByLogicFunc = Callable[[bool], ColumnElement]


class OrderByCriteria:
    """Container for individual ordering logic."""

    def __init__(self, alias: str, func: OrderByLogicFunc, description: Optional[str] = None):
        self.alias = alias
        self.func = func
        self.description = description

    def __call__(self, desc: bool) -> ColumnElement:
        return self.func(desc)

    def __repr__(self) -> str:
        return f"<OrderByCriteria(alias='{self.alias}')>"


def order_by_for(
    alias: Optional[str] = None, description: Optional[str] = None
) -> Callable[[OrderByLogicFunc], OrderByCriteria]:
    """Decorator to create an OrderByCriteria instance from a sorting logic function.

    Args:
        alias (Optional[str]): The query parameter alias. Defaults to the function name if None.
        description (Optional[str]): Description for OpenAPI docs. Defaults to the function's docstring if None.

    Returns:
        Callable[[OrderByLogicFunc], OrderByCriteria]: The decorated function as an OrderByCriteria instance.
    """

    def decorator(func: OrderByLogicFunc) -> OrderByCriteria:
        _alias = alias if alias is not None else func.__name__
        _description = description
        if _description is None and func.__doc__:
            _description = func.__doc__.strip()

        return OrderByCriteria(alias=_alias, func=func, description=_description)

    return decorator
