# app-prebuilt-api-key

Machine identities and revocable API keys, independent of user accounts and JWTs.
The host provides FastAPI, migrations, and the interpretation of its machine scopes.

## Integration

```python
from app_prebuilt_api_key.api import api_keys_router
from app_prebuilt_api_key.usecases import get_machine_scopes

app.include_router(api_keys_router, prefix="/api/v1")
app.dependency_overrides[get_machine_scopes] = lambda: frozenset({"myapp:dispatch"})
```

Register `Machine` and `MachineKey` from `app_prebuilt_api_key.models` in the host's
migration metadata. Their tables are `api_key_machines` and `api_keys`. Install the
app-layer-base exception handlers, or handle its `CustomException` in the host.

The default session maker comes from app-layer-base. Override
`get_api_key_session_maker` (from `app_prebuilt_api_key.database`) with an async
dependency returning your own `async_sessionmaker` to use an application-owned DB.
Authentication closes its read session before the protected operation starts.

Use `get_machine_principal` from `app_prebuilt_api_key.deps` on protected routes.
It accepts `X-API-Key` and returns `machine_id`, `key_id`, `name`, and `scopes`.
The application must check the required scope; a valid key alone is not permission.
Scope strings outside the application's allowlist cannot be assigned by this API.
Keys do not represent people and must not satisfy human-only approval policies.

## Root credential and management

`APP_API_KEY_ROOT_KEY` is optional. Generate a random deployment secret (for example
with `openssl rand -hex 32`) and inject it from the deployment's secret store.
Configured keys must contain at least 32 characters; length is not a substitute for
random generation. Empty or absent disables root authentication. No key is generated
at startup and no authentication bypass is enabled.

Send the root credential as `X-Root-API-Key` to management routes only. It is never
stored in the DB, returned by the API, or accepted as a machine key. Change/remove
it in deployment settings and restart every instance to rotate/disable it. API key
revocation cannot modify this deployment-owned credential. Settings are cached per
process. Do not put it in a browser or a scheduler's configuration.

The default `require_key_admin` dependency accepts only this root credential. A host
may override it to also accept its authenticated human administrators. Ordinary
machine keys must never grant key management or user-account administration.

| Method | Path under `/api/v1` | Operation |
| --- | --- | --- |
| POST | `/machines` | Register `{name, scopes}`; duplicate names return 409 |
| GET | `/machines` | List identities (`offset`, `limit`, maximum 200) |
| PATCH | `/machines/{id}` | Change scopes or `is_active` |
| POST | `/machines/{id}/keys` | Issue `{label, expires_at?}`; expiry needs a timezone |
| GET | `/machines/{id}/keys` | List key metadata, including revoked keys |
| DELETE | `/machines/{id}/keys/{key_id}` | Revoke permanently; repeated calls are safe |

Issuance returns the secret in `key` exactly once, with `Cache-Control: no-store`.
The DB holds only its SHA-256 hash. Keys contain 32 random bytes plus a public lookup
ID. List/revoke responses contain neither the secret nor its hash. No API retrieves
an existing secret. Expired/revoked keys and inactive machines fail authentication.
Expiry inputs accept any explicit UTC offset; storage and metadata responses use UTC
on both SQLite and PostgreSQL. Metadata timestamps always include their UTC offset.
Re-enabling a machine does not clear key revocations. Authentication is read-only;
this first version does not track last-use timestamps or implement project ACLs.

## Deployment and rotation

1. Run the host's migrations and start the server with the root secret injected.
2. A trusted deployment job uses the management API to find/create its named machine.
3. On initial provisioning, issue a key and save the one-time response in the caller's
   secret store. Do not log request credentials or issuance response bodies.
4. Ordinary redeployment reuses the stored key. A list response cannot recover it.
5. For rotation, issue a replacement for the same machine, save it, switch callers,
   verify them, and explicitly revoke the old key.

The machine ID remains stable across key rotation. Issuance is intentionally not
idempotent: retrying a lost response creates another key, so inspect/revoke orphaned
entries rather than treating a retry as recovery. If saving a new secret fails,
revoke that key. Multiple active keys support a gradual caller rollout. Automatic
rotation and OAuth client-credentials flows are outside this package.
