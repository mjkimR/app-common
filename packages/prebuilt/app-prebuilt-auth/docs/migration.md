# Migrating to the unified authentication prebuilt

This is a breaking packaging/import change. The old distributions are removed from this source revision; they are not compatibility packages or dependencies of the new distribution. Applications pinned to previously published Git commits continue to use those commits until deliberately upgraded.

## Dependency and import mapping

Replace `app-prebuilt-user`, `app-prebuilt-google-auth` and `app-prebuilt-api-key` in the host dependencies and Git source entries with **one** `app-prebuilt-auth` entry pointing to `packages/prebuilt/app-prebuilt-auth` at a published commit containing this consolidation. Keep the supporting app-common packages on the same SHA and regenerate the lockfile. No `[core]` or `[google]` extras are needed.

| Previous import prefix | Unified import prefix |
| --- | --- |
| `app_prebuilt_user` | `app_prebuilt_auth.user` |
| `app_prebuilt_google_auth` | `app_prebuilt_auth.google` |
| `app_prebuilt_api_key` | `app_prebuilt_auth.api_key` |

Replace prefixes in application imports, tests, dependency overrides, mock/patch targets, and Alembic environment imports. Settings class names and environment variable names remain unchanged. Do not install/import both generations in one process: they represent the same SQLAlchemy tables.

You can keep existing individual router composition after updating imports, or replace the three mounts with:

```python
from app_prebuilt_auth import install_auth

install_auth(app)  # /api/v1 by default; reads normal environment-backed settings.
```

When using nested routers, `create_auth_router()` returns the same complete API. Existing application-owned dependency overrides still apply after registration. If passing `user_settings`, `install_auth` also creates a per-application login throttle using those settings. Custom lockout policies can override `get_login_throttle` afterwards.

## Database compatibility

Table names, column definitions, foreign keys, indexes, token formats, API routes and environment names are preserved. Moving the Python modules does not itself require a database migration when all six tables already exist.

A consumer that previously installed only the user or API-key package must add the remaining tables from the complete metadata. A consumer older than the approval revision must also add `users.approval_status`, `users.auth_version`, and the audit table. Inspect the migration diff; no existing table should be dropped or recreated due to this rename.

Importing the new package registers the complete schema even with Google disabled. It does not apply DDL. Continue to use the application's migration history rather than `create_all` on an existing production database.

## AutoHub adoption

AutoHub currently remains on its published separate-package SHA. After this consolidation is published:

1. Replace its three auth dependencies/source entries and the Python import prefixes above; update Python/APM pins together.
2. Update the user/settings, Google/provider, and machine-key dependency override imports in `app/main.py`, `app/auth.py`, tests and migration helpers.
3. Replace the three auth mounts in `app/router.py` with `v1_open_router.include_router(create_auth_router())`, or retain individual mounts.
4. Keep AutoHub's approval-required policy, bootstrap lifespan and scheduler scope overrides. The full-schema migration already prepared for the separate packages remains applicable.
5. Rebuild the generated API schema and run lint, type/build checks, backend/UI tests and PostgreSQL auth/migration tests from the published lock, without source links.

Publish and adopt explicitly; never insert a placeholder or an unpublished SHA into a consumer manifest. The unified package can be reviewed and verified independently before changing a currently working consumer.
