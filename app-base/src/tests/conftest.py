"""
Main conftest.py for test configuration and shared fixtures.

This is the root configuration file for pytest. It provides:
- Pytest options and hooks
- Logging configuration
- Imports of all fixtures from the fixtures package

Test Structure:
    tests/
    ├── conftest.py          <- You are here
    ├── fixtures/            <- Reusable fixtures (db, auth, clients)
    ├── utils/               <- Test utilities and helpers
    ├── unit/                <- Unit app_tests (with mocks)
    └── integration/         <- Integration app_tests (real DB)
"""

import logging

import pytest

# Configure logging - reduce noise from SQLAlchemy
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# =============================================================================
# Pytest Hooks & Options
# =============================================================================


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--db-type",
        action="store",
        default="sqlite",
        help="Select database type for tests (sqlite, postgres)",
    )


@pytest.fixture(scope="session")
def db_type(request):
    """Fixture to determine the database type for app_tests."""
    return request.config.getoption("--db-type")


# =============================================================================
# Import Fixtures
# =============================================================================

# Test db fixtures
from tests.fixtures.db import *
