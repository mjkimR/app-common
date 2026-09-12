"""Lightweight random primitives for collision-free test data generation."""

import random
import string
import uuid


def random_string(length: int = 8, prefix: str = "") -> str:
    """Generate a random alphanumeric string with an optional prefix."""
    chars = string.ascii_lowercase + string.digits
    rand = "".join(random.choices(chars, k=length))
    return f"{prefix}{rand}" if prefix else rand


def random_email(domain: str = "example.com", prefix: str = "test") -> str:
    """Generate a random, valid email address."""
    return f"{prefix}_{random_string(8)}@{domain}"


def random_uuid() -> uuid.UUID:
    """Generate a random UUID4 instance."""
    return uuid.uuid4()


def random_int(min_val: int = 1, max_val: int = 100000) -> int:
    """Generate a random integer within the given range."""
    return random.randint(min_val, max_val)
