# app-prebuilt-auth

A single, fully installed authentication prebuilt: users, local password login, Google OIDC, sessions, account approval, administrator access controls, audit history, external identities and machine API keys. Feature modules live inside one Python distribution and share one release. No installation extras are required.

## Install and register

Install from a published app-common Git commit at `packages/prebuilt/app-prebuilt-auth`. Pin the transitive app-common packages (`app-layer-base`, `app-error`, `app-http-client`) to the same commit in the host's `tool.uv.sources`. FastAPI, password hashing, JWT cryptography and form parsing are included in the default dependencies.

```python
from fastapi import FastAPI
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_prebuilt_auth import install_auth
from app_prebuilt_auth.user.config import AuthSettings

app = FastAPI()
set_exception_handler(app)
settings = AuthSettings(**{})  # Environment-backed, including required signing/bootstrap secrets.
install_auth(app, user_settings=settings)
```

`install_auth` mounts all routes at `/api/v1` and accepts optional `user_settings`, `google_settings`, and `api_key_settings`. Omitted settings use their normal environment-backed dependencies. `create_auth_router()` is available for hosts composing nested routers themselves. Existing dependency overrides for DB ownership, human machine-key administrators, machine scopes and login lockout remain available.

The package includes all capabilities; settings control activation. Google login defaults to disabled (`GOOGLE_AUTH_ENABLED=false`). API-key management rejects access without a configured root key or a host-provided administrator dependency. External registration requires administrator approval by default; set `REGISTRATION_REQUIRE_APPROVAL=false` only when the host intentionally allows immediate admission. Local login continues to require valid signing/bootstrap settings.

## Complete schema

Importing `app_prebuilt_auth` (including any submodule) registers all seven tables on the shared SQLAlchemy metadata, even when Google login is disabled:

- `users`
- `user_external_identities`
- `user_access_events`
- `google_login_flows`
- `browser_sessions`
- `api_key_machines`
- `api_keys`

The host applies these tables using Alembic or its existing migration system. Installation and imports never connect to a DB or call `create_all`. Empty tables for unused features are intentional. See [migration](docs/migration.md) when adopting this package from the former separate packages.

## Ownership

| Inside the prebuilt | Host application |
| --- | --- |
| Shared account, approval and token validation | Require approval or use immediate registration |
| Google protocol and browser handoff | OAuth credentials and same-origin callback/frontend URLs |
| Machine identities and key lifecycle | Business scopes and authorization of protected endpoints |
| Complete ORM schema and access audit | Applying schema migrations and retention policy |
| Ready-to-mount auth API | Login/admin UI and lifecycle composition |

The host installs the shared exception handlers (shown above), or equivalent custom handlers for the auth exceptions. The host still creates the bootstrap account with `UserService.ensure_first_user(session)` in its startup transaction, validates enabled provider settings, and closes the shared HTTP client at shutdown. `install_auth` deliberately does not own application lifespan or migrate a live database.

## Modules and guides

- [`app_prebuilt_auth.user`](docs/user.md): local login, accounts, sessions, approval and administrator protection.
- [`app_prebuilt_auth.google`](docs/google.md): optional Google OIDC login using the same account/session rules.
- [`app_prebuilt_auth.api_key`](docs/api_key.md): machine principals, root management and key rotation/revocation.
- [`app_prebuilt_auth.models`](src/app_prebuilt_auth/models.py): all auth ORM models in one import.

This package is not an OAuth authorization server for remote MCP clients. Google login is an upstream identity provider; MCP client consent/scopes/resource tokens remain a separate capability.

## Persistent browser sessions

Use `POST /api/v1/auth/browser/login` with the password form for browser login.
It returns only an access token and sets an opaque refresh credential in an HttpOnly,
SameSite=Lax cookie. Keep the access token in memory. On page load and on an expired
access token, call `POST /api/v1/auth/browser/refresh` with no body and
`credentials: 'include'`. Google exchange opts into the same cookie transport with
`X-Browser-Session: 1`; pending/unapproved accounts never receive a session cookie.
The existing `/users/login/` and `/users/login/refresh` token APIs remain available
for CLI clients.

Every browser session endpoint requires `X-Browser-Session: 1` and an exact `Origin`
match. By default this is the request origin; explicitly configure
`BROWSER_AUTH_ALLOWED_ORIGINS` (a JSON array) for a separate, trusted frontend and
configure credentialed CORS with exact origins in the host. Same-origin hosting,
including a Vite proxy during development, needs no extra origin configuration.
Cookies are Secure except on plain-HTTP loopback hosts. `BROWSER_AUTH_COOKIE_SECURE`
can override this; production must use HTTPS. Hosts may override
`get_browser_auth_settings` to choose distinct cookie names. Cookies are host-only
and default to path `/api/v1/auth`.

Apply the `browser_sessions` migration before deploying. The DB holds only hashes
of random 256-bit refresh credentials, with the user's account version, password
fingerprint and expiration. The refresh handle is stable within a browser session,
so concurrent tabs do not invalidate each other's refresh credentials. Renewal
atomically extends the DB expiry and cookie lifetime by `REFRESH_TOKEN_EXPIRE_DAYS`
(default 14); account suspension, version changes and password changes prevent
renewal. Expired records are pruned on subsequent browser logins.

`POST /api/v1/auth/browser/logout` deletes the server record and expires the cookie.
A concurrent or replayed refresh cannot recreate that record. Clients should report
logout success only after this request succeeds, clear their in-memory access token,
and notify other tabs. Already-issued access tokens retain their short lifetime;
logout revokes this browser's ability to renew, not other devices' sessions.
