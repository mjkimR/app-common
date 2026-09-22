# Unified authentication

Install `app-prebuilt-auth` from `packages/prebuilt/app-prebuilt-auth` at a published app-common Git SHA. All auth capabilities and their dependencies are included by default; no installation extras are needed. Runtime settings enable the required features. Google login defaults to disabled.

```python
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_prebuilt_auth import install_auth

set_exception_handler(app)
install_auth(app)  # Mounts user, Google and machine-key routes under /api/v1.
```

Pass `user_settings`, `google_settings`, or `api_key_settings` to configure a specific app instance, or keep environment-backed defaults. Explicit user settings also scope the password-login throttle to that app. The host retains its DB/lifespan, business authorization and UI. Call `UserService.ensure_first_user` during startup, validate enabled provider settings, and close the shared HTTP client on shutdown.

Importing this package registers the complete ORM metadata: users, external identities, access events, Google login flows, machines and API keys. Apply all tables through the host migration workflow, including tables for disabled features. Imports never create tables or connect to the DB.

Modules:

- `app_prebuilt_auth.user`: [accounts, sessions, approval](../user/index.md), [settings](../user/setup.md).
- `app_prebuilt_auth.google`: [Google OIDC](../user/google-auth.md).
- `app_prebuilt_auth.api_key`: [machine credentials](../api-key/index.md).
- `app_prebuilt_auth.models`: all six ORM models.
- `create_auth_router()`: composition alternative for a host-owned parent router.

Migration from the old packages: replace the three dependency/source entries with `app-prebuilt-auth`; change import prefixes `app_prebuilt_user` → `app_prebuilt_auth.user`, `app_prebuilt_google_auth` → `app_prebuilt_auth.google`, and `app_prebuilt_api_key` → `app_prebuilt_auth.api_key`. Update tests and dependency overrides too. Table names, routes, tokens and environment variables are preserved. Add missing tables if the host previously installed only part of the auth stack. Never load both generations' models in the same process. Pin the host's related app-common sources and APM skill to the same published commit.
