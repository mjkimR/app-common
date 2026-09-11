"""Small value generators for tests."""

import uuid


def random_email() -> str:
    """Generate a unique email address for testing."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def random_string(prefix: str = "test") -> str:
    """Generate a unique string for testing."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
