from app_prebuilt_user.api.v1.users import router
from app_prebuilt_user.schemas import UserRead


def _find_route(path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise AssertionError(f"Route {method} {path} not found")


def test_read_user_returns_single_user_not_paginated():
    """Regression: GET /users/{user_id} must serialize a single UserRead, not a PaginatedList."""
    route = _find_route("/users/{user_id}", "GET")
    assert route.response_model is UserRead


def test_update_user_response_model_is_user_read():
    route = _find_route("/users/{user_id}", "PUT")
    assert route.response_model is UserRead
