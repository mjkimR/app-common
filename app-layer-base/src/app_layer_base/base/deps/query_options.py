import inspect
from collections.abc import Callable, Mapping
from typing import Any

from fastapi import Depends

from app_layer_base.base.deps.params.page import PaginationParams, pagination_params
from app_layer_base.base.repos.query_options import ListQueryOptions


def _get_pagination_value(pagination: Any, field_name: str) -> Any:
    if isinstance(pagination, Mapping):
        return pagination[field_name]
    return getattr(pagination, field_name)


def create_list_query_options_dependency(
    filters_dependency: Callable[..., Any] | None = None,
    order_by_dependency: Callable[..., Any] | None = None,
    pagination_dependency: Callable[..., Any] | None = pagination_params,
) -> Callable[..., ListQueryOptions]:
    """Create a FastAPI dependency that builds repository list query options.

    This factory combines pagination, filtering, and ordering dependencies into
    a single dependency that returns `ListQueryOptions`. Each dependency is
    optional, so endpoints can opt into only the query concerns they support.

    Args:
        filters_dependency: Optional FastAPI dependency that returns SQLAlchemy
            filter conditions for the `where` option. When omitted, `where`
            defaults to an empty tuple.
        order_by_dependency: Optional FastAPI dependency that returns SQLAlchemy
            ordering clauses for the `order_by` option. When omitted,
            `order_by` defaults to an empty tuple.
        pagination_dependency: Optional FastAPI dependency that returns an
            object or mapping with `offset` and `limit`. Defaults to the
            standard offset/limit pagination dependency. Pass `None` to disable
            pagination injection and use `ListQueryOptions` defaults.

    Returns:
        A FastAPI dependency callable suitable for `Depends(...)`.

    Example:
        ```python
        from typing import Annotated
        from fastapi import FastAPI, Depends, APIRouter
        from app_layer_base.base.deps.query_options import create_list_query_options_dependency
        from app_layer_base.base.repos.query_options import ListQueryOptions

        # Assuming combined_filters and ordering_dep are defined using:
        # - create_combined_filter_dependency(...)
        # - create_order_by_dependency(...)

        list_query_options_dep = create_list_query_options_dependency(
            filters_dependency=combined_filters,
            order_by_dependency=ordering_dep,
        )

        app = FastAPI()
        router = APIRouter()

        @router.get("/items")
        async def list_items(
            query_options: Annotated[ListQueryOptions, Depends(list_query_options_dep)],
        ):
            # query_options contains:
            # - query_options.offset (default: 0)
            # - query_options.limit (default: 20)
            # - query_options.where (tuple of filter expressions)
            # - query_options.order_by (tuple of ordering expressions)
            return {
                "offset": query_options.offset,
                "limit": query_options.limit,
                "where": [str(w) for w in query_options.where],
                "order_by": [str(o) for o in query_options.order_by],
            }
        ```
    """

    def dependency(**params: Any) -> ListQueryOptions:
        pagination = params.get("pagination")
        filters = params.get("filters", ())
        order_by = params.get("order_by", ())

        if pagination is None:
            return ListQueryOptions(where=filters, order_by=order_by)

        return ListQueryOptions(
            offset=_get_pagination_value(pagination, "offset"),
            limit=_get_pagination_value(pagination, "limit"),
            where=filters,
            order_by=order_by,
        )

    dependency_parameters = []
    if pagination_dependency is not None:
        dependency_parameters.append(
            inspect.Parameter(
                "pagination",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=Depends(pagination_dependency),
                annotation=PaginationParams,
            )
        )
    if filters_dependency is not None:
        dependency_parameters.append(
            inspect.Parameter(
                "filters",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=Depends(filters_dependency),
                annotation=list,
            )
        )
    if order_by_dependency is not None:
        dependency_parameters.append(
            inspect.Parameter(
                "order_by",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=Depends(order_by_dependency),
                annotation=list,
            )
        )

    dependency.__signature__ = inspect.Signature(parameters=dependency_parameters)
    dependency.__annotations__ = {p.name: p.annotation for p in dependency_parameters}

    return dependency
