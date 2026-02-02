from typing import Any, Callable

from app_base.base.deps.filters.base import SimpleFilterCriteriaBase


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
