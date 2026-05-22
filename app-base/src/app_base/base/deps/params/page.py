from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query


@dataclass(frozen=True, slots=True, kw_only=True)
class PaginationParams:
    offset: int = 0
    limit: int | None = 100


def pagination_params(
    offset: int = Query(default=0, description="offset for pagination"),
    limit: int = Query(default=100, le=200, description="limit for pagination"),
) -> PaginationParams:
    return PaginationParams(offset=offset, limit=limit)


PaginationParam = Annotated[PaginationParams, Depends(pagination_params)]
