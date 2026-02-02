from typing import Annotated, Any

from fastapi import Depends, Query


def pagination_params(
    offset: int = Query(default=0, description="offset for pagination"),
    limit: int = Query(default=100, le=200, description="limit for pagination"),
) -> dict[str, Any]:
    return {"offset": offset, "limit": limit}


PaginationParam = Annotated[dict, Depends(pagination_params)]
