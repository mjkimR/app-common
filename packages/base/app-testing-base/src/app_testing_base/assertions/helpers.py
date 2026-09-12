"""Custom assertion helpers designed for clear, AI-actionable error messages."""

from typing import Any

from httpx import Response
from loguru import logger


def assert_status_code(response: Response, expected: int) -> None:
    """Assert HTTP response status code with detailed error payload context."""
    if 400 <= expected < 600:
        logger.info(f"[Expected Error] Status {expected} is expected for this test scenario")

    if response.status_code != expected:
        body = response.text[:1000]
        raise AssertionError(
            f"Expected status {expected}, got {response.status_code}.\n"
            f"Request: {response.request.method} {response.request.url}\n"
            f"Response Body: {body}"
        )


def assert_json_contains(response: Response, expected: dict[str, Any]) -> None:
    """Assert that response JSON contains expected key-value pairs."""
    try:
        data = response.json()
    except Exception as e:
        raise AssertionError(f"Response is not valid JSON: {response.text[:500]}") from e

    if not isinstance(data, dict):
        raise AssertionError(f"Expected JSON object (dict), got {type(data).__name__}: {data}")

    for key, value in expected.items():
        if key not in data:
            raise AssertionError(
                f"Key '{key}' not found in response JSON.\n"
                f"Expected: {key}={value!r}\n"
                f"Available keys: {list(data.keys())}\n"
                f"Actual data: {data}"
            )
        actual = data[key]
        if actual != value:
            raise AssertionError(
                f"Mismatch for key '{key}'.\nExpected: {value!r}\nActual:   {actual!r}\nFull data: {data}"
            )


def assert_paginated_response(
    response: Response,
    min_items: int = 0,
    items_key: str = "items",
    total_key: str = "total_count",
) -> None:
    """Assert that response is a valid paginated response structure."""
    assert_status_code(response, 200)
    data = response.json()
    assert items_key in data, f"Response missing '{items_key}' field: {data}"
    assert total_key in data, f"Response missing '{total_key}' field: {data}"
    assert isinstance(data[items_key], list), f"'{items_key}' should be a list, got {type(data[items_key])}"
    assert len(data[items_key]) >= min_items, (
        f"Expected at least {min_items} items in '{items_key}', got {len(data[items_key])}"
    )


def assert_error_response(
    response: Response,
    status_code: int,
    error_type: str | None = None,
) -> None:
    """Assert that response is an error response with appropriate detail/error payload."""
    assert_status_code(response, status_code)
    data = response.json()
    has_error = "detail" in data or "error" in data or "message" in data
    assert has_error, f"Error response missing 'detail', 'error', or 'message' field: {data}"

    if error_type:
        actual_type = data.get("error_type") or data.get("type")
        assert actual_type == error_type, f"Expected error_type {error_type!r}, got {actual_type!r} in {data}"


def assert_model_fields(obj: Any, expected: dict[str, Any]) -> None:
    """Assert that a model object (Pydantic model, SQLAlchemy model, or dict) has expected field values."""
    for key, value in expected.items():
        if isinstance(obj, dict):
            assert key in obj, f"Key '{key}' not in dict"
            actual = obj[key]
        else:
            assert hasattr(obj, key), f"Attribute '{key}' not found on {type(obj).__name__}"
            actual = getattr(obj, key)
        assert actual == value, f"Field '{key}' mismatch. Expected: {value!r}, got: {actual!r}"
