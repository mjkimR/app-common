# Machine API keys

Use `app-prebuilt-api-key` for machine identity and key lifecycle. Mount
`api_keys_router` under `/api/v1`, register the `Machine`/`MachineKey` models with
host migrations, and supply a scope allowlist through `get_machine_scopes`.

`APP_API_KEY_ROOT_KEY` enables deployment-owned management authentication through
`X-Root-API-Key`. It is optional, never stored in the DB, and never a workload
credential. Rotation/removal requires updating deployment settings and restarting.

`get_machine_principal` checks database-backed `X-API-Key` credentials. The host
checks scopes and human/machine boundaries. Override `require_key_admin` only to
add authenticated human administrators; never authorize ordinary machines there.
Override `get_api_key_session_maker` for an application-owned engine. Authentication
must close its read transaction before the application's transaction starts.

Issue secrets once, store only hashes, and never log issuance response bodies.
Deployments find/create a stable machine, save an issued key in the caller's secret
store, and reuse it across redeployments. Rotate by issuing a replacement, switching
callers, and explicitly revoking the old key. Do not resurrect revoked keys during
startup or retry issuance as though it were idempotent.
