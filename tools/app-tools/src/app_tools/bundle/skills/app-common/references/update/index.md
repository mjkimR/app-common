# app-package-update

Use this guide when a consumer project moves to another published `app-common` commit,
rather than linking a local checkout.

Run from the consumer project's root:

```bash
uv run devkit app update                 # the head of app-common main
uv run devkit app update --ref <branch, tag or full commit>
```

The command resolves the ref to a full commit and pins every app-common dependency to
it, in both forms: `git+https://github.com/mjkimR/app-common.git@<ref>#subdirectory=...`
requirements and `[tool.uv.sources]` entries (`rev`; a `tag` or `branch` is replaced),
in the root manifest and its uv workspace members. It also sets the `devkit` and
`devkit-advisory` sources to the revision app-common pins at that commit (uv rejects any
other: the app-common packages bring those exact URLs), and adds each to the root `dev`
dependency group when the project does not declare it: a project's source applies only to
its direct dependencies, and a declared `devkit` without one resolves from PyPI, where an
unrelated project owns the name. It then runs `uv lock`, `uv sync` and `uv run devkit sync`, which
redeploys the app-common skill, rules and guidance from the new app-tools.

- `--dry-run` reports the commit, the manifests and the commands without changing anything.
- `--no-sync` stops after `uv lock`.
- A failing `uv lock` restores the manifests; the error names the failed command.

Commit `pyproject.toml`, `uv.lock` and the files `devkit sync` changed
(`.devkit/installation.json`, `AGENTS.md`, `.agents/skills/`, `.claude/skills/`). Other
clones and CI then run `uv sync` and `uv run devkit sync --locked`, which restores the
managed copies from that receipt and never rewrites committed files.

## Leaving APM

A project that installed the skill with APM gets an `APP_APM_SUPERSEDED` warning and no
`devkit sync`. Remove the app-common entry from `apm.yml` (and `apm.yml`,
`apm.lock.yaml` and `apm_modules/` when it was the only one), delete
`.agents/skills/app-common` and `.claude/skills/app-common`, then run `uv run devkit sync`
and `uv run devkit add advisory:python`. The complete one-time migration (pins, code,
tooling) is in the app-common README, "Migrating a project from APM and app-error".

Errors moved from `app_error` to `devkit.advisory`: replace `from app_error import AppError,
Actor, Retry` with `from devkit.advisory import AdvisoryError, Actor, Retry` and rename
`AppError` to `AdvisoryError` (`render_mcp()` is now `render()`).

For local, unpublished app-common changes, use `devkit app dev link` instead; it does not
change dependency refs.
