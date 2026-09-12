"""Unit tests for assertion helpers."""

import pytest
from app_testing_base.assertions import (
    assert_error_response,
    assert_json_contains,
    assert_model_fields,
    assert_paginated_response,
    assert_status_code,
)
from httpx import Request, Response
from pydantic import BaseModel


def _make_response(status_code: int, json_data: dict | list | None = None, text: str = "") -> Response:
    import json

    content = json.dumps(json_data).encode("utf-8") if json_data is not None else text.encode("utf-8")
    req = Request("GET", "http://testserver/api/items")
    return Response(status_code=status_code, content=content, request=req)


class SampleModel(BaseModel):
    id: int
    name: str
    active: bool


def test_assert_status_code():
    res = _make_response(200)
    assert_status_code(res, 200)

    with pytest.raises(AssertionError, match="Expected status 201, got 200"):
        assert_status_code(res, 201)


def test_assert_json_contains():
    res = _make_response(200, {"id": 1, "name": "item", "nested": {"key": "val"}})
    assert_json_contains(res, {"id": 1, "name": "item"})

    with pytest.raises(AssertionError, match="Key 'missing' not found in response JSON"):
        assert_json_contains(res, {"missing": True})

    with pytest.raises(AssertionError, match="Mismatch for key 'name'"):
        assert_json_contains(res, {"name": "wrong"})


def test_assert_paginated_response():
    res = _make_response(200, {"items": [1, 2, 3], "total_count": 3})
    assert_paginated_response(res, min_items=2)

    with pytest.raises(AssertionError, match="Expected at least 5 items"):
        assert_paginated_response(res, min_items=5)


def test_assert_error_response():
    res = _make_response(400, {"detail": "Bad request", "error_type": "ValidationError"})
    assert_error_response(res, 400, error_type="ValidationError")

    with pytest.raises(AssertionError, match="Expected error_type 'NotFound'"):
        assert_error_response(res, 400, error_type="NotFound")


def test_assert_model_fields():
    model = SampleModel(id=1, name="test", active=True)
    assert_model_fields(model, {"id": 1, "name": "test"})

    with pytest.raises(AssertionError, match="Field 'name' mismatch"):
        assert_model_fields(model, {"name": "other"})

    dictionary = {"id": 1, "name": "dict_test"}
    assert_model_fields(dictionary, {"id": 1, "name": "dict_test"})
