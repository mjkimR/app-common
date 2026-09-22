# Google OIDC login

Google OIDC is included in the default `app-prebuilt-auth` installation.
Call `install_auth(app)` from `app_prebuilt_auth` to mount the complete auth API. Google is disabled by default.
The host owns the approval screen and the local bootstrap superadmin account.

Set `GOOGLE_AUTH_ENABLED`, `GOOGLE_AUTH_CLIENT_ID`, `GOOGLE_AUTH_CLIENT_SECRET`,
`GOOGLE_AUTH_REDIRECT_URI`, and `GOOGLE_AUTH_FRONTEND_URL`. Callback and frontend must use the same
HTTPS origin. For localhost HTTP only, set `GOOGLE_AUTH_COOKIE_SECURE=false` and use the frontend API proxy.
Set shared `AuthSettings.REGISTRATION_REQUIRE_APPROVAL=true` to create pending external users.

Import `app_prebuilt_auth` before Alembic autogeneration; all authentication models are registered: migrate shared user approval/version/audit fields,
`user_external_identities`, and `google_login_flows`. Preserve existing users as approved, version 0.
Retire all old workers before enabling registration. Override the shared user session/transaction dependencies
for host-owned databases. Close `app_http_client.instance.close_http_client` at application shutdown.

Frontend: read `GET /auth/google/options`; navigate to `/start`; handle `?google=complete` by removing
it and POSTing `/exchange` from the configured origin. The HttpOnly cookie holds the one-time handoff;
only approved active users receive app tokens. Pending users sign in again after approval.
Never log callback query strings or tokens. Do not infer account linking or roles from email.
An existing-email collision requires the existing login; explicit linking is not provided.

Google login is not remote MCP OAuth authorization. Add a separate authorization server/token contract
when implementing MCP client login. Do not pass Google ID/access tokens directly to application APIs.
