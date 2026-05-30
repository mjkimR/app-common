import pytest
from app_prebuilt_user.schemas import UserCreate
from pydantic import SecretStr, ValidationError


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        UserCreate(
            firstname="Test",
            lastname="User",
            email="test@example.com",
            password=SecretStr("short"),
        )


def test_user_create_accepts_password_with_minimum_length():
    user = UserCreate(
        firstname="Test",
        lastname="User",
        email="test@example.com",
        password=SecretStr("password"),
    )

    assert user.password.get_secret_value() == "password"
