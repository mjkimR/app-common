from typing import Annotated

import pytest
from app_base.base.deps.filters.combine import create_combined_filter_dependency
from app_base.base.deps.filters.decorators import filter_for
from app_base.base.deps.ordering.base import order_by_for
from app_base.base.deps.ordering.combine import create_order_by_dependency
from fastapi import APIRouter, Depends, FastAPI
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
def order_by_name(desc: bool):
    return dummy_name_col.desc() if desc else dummy_name_col.asc()


@order_by_for(alias="created_at")
def order_by_created_at(desc: bool):
    return dummy_created_at_col.desc() if desc else dummy_created_at_col.asc()


ordering_dep = create_order_by_dependency(order_by_name, order_by_created_at, default_order="-created_at")

# FastAPI App
app = FastAPI()
router = APIRouter()


@router.get("/items")
async def list_items(
    filters: Annotated[list, Depends(combined_filters)], order_by: Annotated[list, Depends(ordering_dep)]
):
    return {"filters": filters, "order_by": order_by}


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
