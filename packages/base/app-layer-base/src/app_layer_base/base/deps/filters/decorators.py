from collections.abc import Callable
from typing import Any

from app_layer_base.base.deps.filters.base import SimpleFilterCriteriaBase


def filter_for(
    bound_type: type, alias=None, description=None, **query_params
) -> Callable[[Callable[..., Any]], SimpleFilterCriteriaBase]:
    """
    Decorator to create a SimpleFilterCriteriaBase subclass from a filter logic function.

    Args:
        bound_type (type): The type to bind the query parameter to.
        alias (Optional[str]): The query parameter name. Defaults to the function name if None.
        description (Optional[str]): Description for OpenAPI docs. Defaults to the function's docstring if None.
        **query_params: Additional keyword arguments for FastAPI's Query.

    Example:
        ```python
        from app_layer_base.base.deps.filters.decorators import filter_for
        from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
        from fastapi import FastAPI, Depends
        from typing import Annotated

        # 1. Define filter logic functions using the decorator.
        #    - Parameter alias defaults to the function name (e.g., "name", "age").
        #    - Parameter description is automatically taken from the function's docstring.
        @filter_for(bound_type=str)
        def filter_by_name(value: str | None):
            \"\"\"Filter by user name\"\"\"
            if value:
                return User.name == value
            return None

        @filter_for(bound_type=int)
        def filter_by_age(value: int | None):
            \"\"\"Filter by user age\"\"\"
            if value is not None:
                return User.age == value
            return None

        # 2. Combine individual filters into a single dependency
        combined_filters = create_combined_filter_dependency(filter_by_name, filter_by_age)

        # 3. Use in a FastAPI route
        app = FastAPI()

        @app.get("/users")
        async def list_users(filters: Annotated[list, Depends(combined_filters)]):
            # filters will be a list of SQLAlchemy filter expressions, e.g. [User.name == "Alice", User.age == 30]
            # query = select(User).where(*filters)
            return {"filters": [str(f) for f in filters]}
        ```
    """

    def decorator(func) -> SimpleFilterCriteriaBase:
        _alias = alias if alias is not None else func.__name__
        _description = description
        if _description is None and func.__doc__:
            _description = func.__doc__.strip()

        class _CustomSimpleFilter(SimpleFilterCriteriaBase):
            def __init__(self):
                super().__init__(
                    alias=_alias,
                    description=_description,
                    bound_type=bound_type,
                    **query_params,
                )

            def _filter_logic(self, value):
                return func(value)

        _CustomSimpleFilter.__name__ = func.__name__
        return _CustomSimpleFilter()

    return decorator
