from collections.abc import Callable

from sqlalchemy.sql import ColumnElement

# Type alias for the ordering logic function: takes a boolean (desc) and returns a SQLAlchemy expression.
OrderByLogicFunc = Callable[[bool], ColumnElement]


class OrderByCriteria:
    """Container for individual ordering logic."""

    def __init__(self, alias: str, func: OrderByLogicFunc, description: str | None = None):
        self.alias = alias
        self.func = func
        self.description = description

    def __call__(self, desc: bool) -> ColumnElement:
        return self.func(desc)

    def __repr__(self) -> str:
        return f"<OrderByCriteria(alias='{self.alias}')>"


def order_by_for(
    alias: str | None = None, description: str | None = None
) -> Callable[[OrderByLogicFunc], OrderByCriteria]:
    """Decorator to create an OrderByCriteria instance from a sorting logic function.

    Args:
        alias (Optional[str]): The query parameter alias. Defaults to the function name if None.
        description (Optional[str]): Description for OpenAPI docs. Defaults to the function's docstring if None.

    Returns:
        Callable[[OrderByLogicFunc], OrderByCriteria]: The decorated function as an OrderByCriteria instance.

    Example:
        ```python
        from app_layer_base.base.deps.ordering.base import order_by_for
        from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
        from fastapi import FastAPI, Depends
        from typing import Annotated

        # 1. Define order logic functions using the decorator.
        #    - Alias defaults to the function name (e.g. "name", "created_at").
        #    - Description defaults to the function's docstring.
        @order_by_for()
        def name(desc: bool):
            \"\"\"Sort by name\"\"\"
            return User.name.desc() if desc else User.name.asc()

        @order_by_for()
        def created_at(desc: bool):
            \"\"\"Sort by creation time\"\"\"
            return User.created_at.desc() if desc else User.created_at.asc()

        # 2. Combine individual sort criteria into a single dependency
        ordering_dep = create_order_by_dependency(
            name, created_at, default_order="-created_at"
        )

        # 3. Use in a FastAPI route
        app = FastAPI()

        @app.get("/users")
        async def list_users(order_by: Annotated[list, Depends(ordering_dep)]):
            # order_by will be a list of SQLAlchemy ordering expressions
            # e.g., [User.created_at.desc()]
            # query = select(User).order_by(*order_by)
            return {"order_by": [str(o) for o in order_by]}
        ```
    """

    def decorator(func: OrderByLogicFunc) -> OrderByCriteria:
        _alias = alias if alias is not None else func.__name__
        _description = description
        if _description is None and func.__doc__:
            _description = func.__doc__.strip()

        return OrderByCriteria(alias=_alias, func=func, description=_description)

    return decorator
