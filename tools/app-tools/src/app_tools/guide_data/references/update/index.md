# app-package-update

Use this skill when a downstream project needs a newer released version of `app-common`, rather than local source linking.

Run from the consumer project's root:

```bash
uv run app-tools update
```

This resolves the latest GitHub release, updates every `git+https://github.com/mjkimR/app-common.git@...#subdirectory=...` dependency in `pyproject.toml`, refreshes `uv.lock`, synchronizes `.venv`, and installs the matching current skills into `.agents/skills`.

Use `--dry-run` to inspect the selected latest release and affected dependency count. Use `--no-sync` only when the lockfile should change now but installation must happen later. Use `--skills-target codex` or `--skills-target claude` when skills belong in that agent's directory.

For local, unpublished app-common changes, use `app-tools dev link` instead; it does not change dependency refs.
