from app_prebuilt_auth.user.config.auth import AuthSettings


def auth_settings(**overrides) -> AuthSettings:
    values = {
        "FIRST_USER_EMAIL": "admin@example.com",
        "FIRST_USER_PASSWORD": "test-password",
        "SECRET_KEY": "test-signing-key",
    }
    return AuthSettings(**(values | overrides))


def test_external_registration_requires_approval_by_default() -> None:
    assert auth_settings().REGISTRATION_REQUIRE_APPROVAL is True


def test_external_registration_can_explicitly_skip_approval() -> None:
    assert auth_settings(REGISTRATION_REQUIRE_APPROVAL=False).REGISTRATION_REQUIRE_APPROVAL is False
