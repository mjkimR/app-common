# app-prebuilt-google-auth

Optional Google OIDC login for `app-prebuilt-user`. The host retains its local password login and administrator UI. No email whitelist is included.

## Installation and composition

Consume this package, `app-prebuilt-user`, `app-layer-base`, and `app-http-client` from the same **published Git commit**. Configure all transitive workspace packages in the host's `tool.uv.sources`; do not use sibling paths in consumer manifests.

```python
from app_prebuilt_google_auth.api import router as google_auth_router
from app_prebuilt_user.api import v1_users_router

app.include_router(v1_users_router, prefix="/api/v1")
app.include_router(google_auth_router, prefix="/api/v1")
```

Use the shared user settings and DB. `get_user_transaction` and `get_session` remain host-overridable. Import the Google router/models before generating Alembic metadata. Close the shared HTTP client at shutdown with `app_http_client.instance.close_http_client`. Call `get_google_auth_settings()` at startup to validate enabled configuration early.

## Settings

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `GOOGLE_AUTH_ENABLED` | `false` | Enable the login endpoints; options remains public. |
| `GOOGLE_AUTH_CLIENT_ID` | empty | Google Web application OAuth client ID. |
| `GOOGLE_AUTH_CLIENT_SECRET` | empty | Client secret; store in the deployment secret store. |
| `GOOGLE_AUTH_REDIRECT_URI` | empty | Exact registered callback, e.g. `https://hub.example/api/v1/auth/google/callback`. |
| `GOOGLE_AUTH_FRONTEND_URL` | empty | Fixed post-login page, e.g. `https://hub.example/`; no query or fragment. |
| `GOOGLE_AUTH_COOKIE_SECURE` | `true` | Disable only for localhost HTTP development. |
| `GOOGLE_AUTH_COOKIE_PATH` | `/api/v1/auth/google` | Must cover the mounted callback and exchange routes. |
| `REGISTRATION_REQUIRE_APPROVAL` | `false` | Shared `AuthSettings` policy: external registrations start pending when true. |

Callback and frontend must share an origin. For Vite development, use the frontend's `/api` proxy and register a localhost callback on that frontend port. An alternate API mount also requires updating `COOKIE_PATH` and the callback URI.

## Browser protocol

1. `GET /api/v1/auth/google/options` reports `enabled`.
2. Navigate to `GET /api/v1/auth/google/start`. A browser-bound HttpOnly cookie and a DB-backed, ten-minute state protect the authorization code flow; PKCE and nonce bind the provider response.
3. Google redirects to `/callback`. The server verifies the signed ID token (issuer, audience, expiry, nonce, verified email and stable subject). It consumes state atomically and redirects only to the configured frontend with `?google=complete`, `failed`, or `existing_account`.
4. The frontend removes that query parameter and sends `POST /api/v1/auth/google/exchange` from its own origin. A one-minute, single-use HttpOnly cookie is exchanged for `{status, email, tokens}`. Status is `approved`, `pending`, `rejected`, or `suspended`; only approved active users receive a token pair.
5. Pending users wait for approval and sign in with Google again. There is no pending session that grants application API access.

No bearer tokens enter URLs. OAuth state and exchange identifiers are hashed at rest. PKCE verifiers and nonces are short-lived database values. Expired flow rows are removed when a new flow starts. Host access logs must omit/redact callback query strings; do not log authorization codes, cookies, ID tokens, or provider responses.

Google identity is keyed by canonical issuer + `sub`. A matching email **never links** to an existing user, including the reserved bootstrap email. Existing accounts continue to use their current login. Explicit account linking is not implemented; add it only with proof of both identities. Google login does not imply superadmin: new Google accounts always start as ordinary users.

## Schema and rollout

Host-owned migrations must add the shared user schema described in [app-prebuilt-user](../app-prebuilt-user/README.md#approval-and-access-administration) plus:

- `user_external_identities` (shared `app_prebuilt_user.identities.ExternalIdentity`): UUID ID, timestamps, user FK with cascading delete, issuer and subject, unique `(issuer, subject)`.
- `google_login_flows`: hashed key primary key, browser hash, optional nonce/verifier/user FK, indexed expiry.

Use these package models as the schema authority. Migrate before deploying the new code. Retire all old application workers before enabling Google login. Preserve existing users with `approval_status='approved'` and `auth_version=0`. A downgrade removes approval/version enforcement: disable Google login, block unapproved/version-revoked users, and rotate the signing key before restoring old code. AutoHub includes a concrete migration and rollout guide.

## Boundaries

This is an upstream Google login client, not an OAuth authorization server for remote MCP clients. MCP consent, client registration, resource-specific tokens, scopes and revocation need a separate authorization implementation. Project/repository authorization remains the host's responsibility.

Tests use signed synthetic Google ID tokens and real SQLite/PostgreSQL transactions. Live Google console setup and browser login must be verified by the host before deployment.
