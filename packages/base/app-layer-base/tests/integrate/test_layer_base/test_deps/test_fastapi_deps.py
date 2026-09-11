from typing import Annotated, Any

import pytest
from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.params.page import PaginationParams
from app_layer_base.base.deps.query_options import create_list_query_options_dependency
from app_layer_base.base.repos.query_options import ListQueryOptions
from fastapi import APIRouter, Depends, FastAPI, Query
from fastapi.testclient import TestClient


# Dummy SQLAlchemy ColumnElements for testing
class DummyColumn:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return f"{self.name} == {other}"

    def asc(self):
        return f"{self.name} ASC"

    def desc(self):
        return f"{self.name} DESC"


dummy_name_col = DummyColumn("name")
dummy_age_col = DummyColumn("age")
dummy_created_at_col = DummyColumn("created_at")


# 1. Filters Setup
@filter_for(bound_type=str, alias="name")
def filter_by_name(value: str):
    if value:
        return dummy_name_col == value
    return None


@filter_for(bound_type=int, alias="age")
def filter_by_age(value: int):
    if value is not None:
        return dummy_age_col == value
    return None


combined_filters = create_combined_filter_dependency(filter_by_name, filter_by_age)


# 2. Ordering Setup
@order_by_for(alias="name")
def order_by_name(desc: bool) -> Any:
    return dummy_name_col.desc() if desc else dummy_name_col.asc()


@order_by_for(alias="created_at")
def order_by_created_at(desc: bool) -> Any:
    return dummy_created_at_col.desc() if desc else dummy_created_at_col.asc()


ordering_dep = create_order_by_dependency(order_by_name, order_by_created_at, default_order="-created_at")
list_query_options_dep = create_list_query_options_dependency(combined_filters, ordering_dep)
pagination_only_query_options_dep = create_list_query_options_dependency()
filters_only_query_options_dep = create_list_query_options_dependency(filters_dependency=combined_filters)
order_by_only_query_options_dep = create_list_query_options_dependency(order_by_dependency=ordering_dep)


def nullable_limit_pagination_params(
    offset: int = Query(default=0),
    limit: int | None = Query(default=None),
) -> PaginationParams:
    return PaginationParams(offset=offset, limit=limit)


nullable_limit_query_options_dep = create_list_query_options_dependency(
    pagination_dependency=nullable_limit_pagination_params
)

# FastAPI App
app = FastAPI()
router = APIRouter()


@router.get("/items")
async def list_items(
    filters: Annotated[list, Depends(combined_filters)], order_by: Annotated[list, Depends(ordering_dep)]
):
    return {"filters": filters, "order_by": order_by}


@router.get("/query-options")
async def list_query_options(query_options: Annotated[ListQueryOptions, Depends(list_query_options_dep)]):
    return {
        "offset": query_options.offset,
        "limit": query_options.limit,
        "where": query_options.where,
        "order_by": query_options.order_by,
    }


@router.get("/query-options/pagination-only")
async def list_pagination_only_query_options(
    query_options: Annotated[ListQueryOptions, Depends(pagination_only_query_options_dep)],
):
    return {
        "offset": query_options.offset,
        "limit": query_options.limit,
        "where": query_options.where,
        "order_by": query_options.order_by,
    }


@router.get("/query-options/filters-only")
async def list_filters_only_query_options(
    query_options: Annotated[ListQueryOptions, Depends(filters_only_query_options_dep)],
):
    return {
        "offset": query_options.offset,
        "limit": query_options.limit,
        "where": query_options.where,
        "order_by": query_options.order_by,
    }


@router.get("/query-options/order-by-only")
async def list_order_by_only_query_options(
    query_options: Annotated[ListQueryOptions, Depends(order_by_only_query_options_dep)],
):
    return {
        "offset": query_options.offset,
        "limit": query_options.limit,
        "where": query_options.where,
        "order_by": query_options.order_by,
    }


@router.get("/query-options/nullable-limit")
async def list_nullable_limit_query_options(
    query_options: Annotated[ListQueryOptions, Depends(nullable_limit_query_options_dep)],
):
    return {
        "offset": query_options.offset,
        "limit": query_options.limit,
        "where": query_options.where,
        "order_by": query_options.order_by,
    }


app.include_router(router)


@pytest.fixture
def client():
    return TestClient(app)


async def test_combined_filters_empty(client):
    response = client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["filters"] == []


async def test_combined_filters_with_values(client):
    response = client.get("/items?name=Alice&age=30")
    assert response.status_code == 200
    data = response.json()
    assert "name == Alice" in data["filters"]
    assert "age == 30" in data["filters"]


async def test_ordering_default(client):
    response = client.get("/items")
    assert response.status_code == 200
    data = response.json()
    assert data["order_by"] == ["created_at DESC"]


async def test_ordering_custom(client):
    response = client.get("/items?order_by=name")
    assert response.status_code == 200
    data = response.json()
    assert data["order_by"] == ["name ASC"]


async def test_ordering_multiple_with_desc(client):
    response = client.get("/items?order_by=-name,created_at")
    assert response.status_code == 200
    data = response.json()
    assert data["order_by"] == ["name DESC", "created_at ASC"]


async def test_list_query_options_dependency_combines_params_filters_and_ordering(client):
    response = client.get("/query-options?offset=10&limit=20&name=Alice&order_by=name")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 10
    assert data["limit"] == 20
    assert data["where"] == ["name == Alice"]
    assert data["order_by"] == ["name ASC"]


async def test_list_query_options_dependency_supports_pagination_only(client):
    response = client.get("/query-options/pagination-only?offset=5&limit=15&name=Alice&order_by=name")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 5
    assert data["limit"] == 15
    assert data["where"] == []
    assert data["order_by"] == []


async def test_list_query_options_dependency_supports_filters_only(client):
    response = client.get("/query-options/filters-only?offset=5&limit=15&name=Alice&order_by=name")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 5
    assert data["limit"] == 15
    assert data["where"] == ["name == Alice"]
    assert data["order_by"] == []


async def test_list_query_options_dependency_supports_order_by_only(client):
    response = client.get("/query-options/order-by-only?offset=5&limit=15&name=Alice&order_by=name")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 5
    assert data["limit"] == 15
    assert data["where"] == []
    assert data["order_by"] == ["name ASC"]


async def test_list_query_options_dependency_supports_custom_pagination(client):
    response = client.get("/query-options/nullable-limit?offset=5")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 5
    assert data["limit"] is None
    assert data["where"] == []
    assert data["order_by"] == []
