# app-package-update

Use this skill when a downstream project needs a newer released version of `app-common`, rather than local source linking.

Run from the consumer project's root:

```bash
uv run app-tools update
```

This resolves the latest GitHub release, updates every `git+https://github.com/mjkimR/app-common.git@...#subdirectory=...` dependency in `pyproject.toml`, refreshes `uv.lock`, synchronizes `.venv`.

Use `--dry-run` to inspect the selected latest release and affected dependency count. Use `--no-sync` only when the lockfile should change now but installation must happen later.

For local, unpublished app-common changes, use `app-tools dev link` instead; it does not change dependency refs.

Manage skills separately through APM: update the app-common skill ref in the consumer's `apm.yml` and run `apm install --refresh`, then review the lockfile. Package updates do not install or alter skills.
