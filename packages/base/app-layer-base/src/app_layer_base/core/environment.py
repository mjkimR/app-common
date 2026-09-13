"""Small, dependency-free helpers for making runtime environment decisions."""

from enum import StrEnum


class RuntimeEnvironment(StrEnum):
    """Canonical environment names used by app-common helpers."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


_ALIASES = {
    "dev": RuntimeEnvironment.DEVELOPMENT,
    "local": RuntimeEnvironment.DEVELOPMENT,
    "testing": RuntimeEnvironment.TEST,
    "stage": RuntimeEnvironment.STAGING,
    "prod": RuntimeEnvironment.PRODUCTION,
}


def normalize_environment(value: str) -> str:
    """Normalize a configured environment while preserving unknown deployment names."""
    normalized = value.strip().lower()
    return _ALIASES.get(normalized, normalized)


def is_production_environment(value: str) -> bool:
    """Return whether *value* represents a production deployment."""
    return normalize_environment(value) == RuntimeEnvironment.PRODUCTION


def is_development_environment(value: str) -> bool:
    """Return whether *value* represents a local development deployment."""
    return normalize_environment(value) == RuntimeEnvironment.DEVELOPMENT


def is_test_environment(value: str) -> bool:
    """Return whether *value* represents a test deployment."""
    return normalize_environment(value) == RuntimeEnvironment.TEST
