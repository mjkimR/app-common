"""Standard test foundation for FastAPI, SQLAlchemy, and Pytest."""

from app_testing_base.assertions import (
    assert_error_response,
    assert_json_contains,
    assert_model_fields,
    assert_paginated_response,
    assert_status_code,
)
from app_testing_base.cases import E2ETest, IntegrationTest, UnitTest
from app_testing_base.client import AsyncClientWithJson
from app_testing_base.db import clean_db_after_test, refresh_get
from app_testing_base.di import DependencyResolutionError, MockRequest, resolve_dependency
from app_testing_base.utils import (
    days_ago,
    days_later,
    hours_ago,
    hours_later,
    random_email,
    random_int,
    random_string,
    random_uuid,
    utc_now,
)

__all__ = [
    "AsyncClientWithJson",
    "DependencyResolutionError",
    "E2ETest",
    "IntegrationTest",
    "MockRequest",
    "UnitTest",
    "assert_error_response",
    "assert_json_contains",
    "assert_model_fields",
    "assert_paginated_response",
    "assert_status_code",
    "clean_db_after_test",
    "days_ago",
    "days_later",
    "hours_ago",
    "hours_later",
    "random_email",
    "random_int",
    "random_string",
    "random_uuid",
    "refresh_get",
    "resolve_dependency",
    "utc_now",
]
