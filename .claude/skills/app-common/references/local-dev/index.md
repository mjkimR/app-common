# app-local-dev

Modifying `app-common` packages locally from downstream consumer repositories using `devkit app dev`.

When developing in a downstream consumer project and needing to modify `app-common` packages (`app-layer-base`, adapters, UI, etc.) simultaneously, follow this workflow.

> [!IMPORTANT]
> **Never edit `pyproject.toml` or `package.json` to point to local file paths.**
> Hardcoding local paths causes dirty git diffs and risks accidental commits that break CI or remote deployments.

---

## 1. Quick Workflow

### Step 1: Link Local Source
Run inside the consumer repository root:

```bash
uv run devkit app dev link
# Or explicitly specify target path:
uv run devkit app dev link --target-path ../app-common
```

- **Exploration range**: Automatically discovers `app-common` at `-1 to +1 depth` (same level `../app-common`, sibling folders `../*/`, child `./app-common`, grandparent `../../app-common`).
- **Backup**: Automatically renames installed directories in `.venv/lib/python*/site-packages/` and `node_modules/` to `*.bak`.
- **Symlink**: Creates symlinks to the local `app-common` source directories (`src/<pkg>` or `packages/ui/<pkg>`).
- **UV Lock Protection**: Preserves `.dist-info` metadata so `uv run` will not trigger an automatic re-sync or overwrite your symlinks.
- **Bundle source**: linking `app_tools` makes the checkout's app-common skill and rules the ones devkit deploys. The command warns (`APP_DEV_BUNDLE_SOURCE_CHANGED`); run `uv run devkit sync` to deploy them, and again after `unlink`. Do not commit the `.devkit/installation.json` such a sync writes.

### Step 2: Develop and Test
1. Make your code changes in your local `app-common` repository clone.
2. Run downstream application tests to verify the behavior immediately.
3. For multi-database testing (PostgreSQL row-locking, MinIO/Docker contracts) and package contribution standards, use the `app-common-contributor` skill that devkit deploys inside the app-common checkout.

### Step 3: Unlink and Restore
Once changes are verified and committed/pushed to `app-common`, **always restore the consumer repository**:

```bash
uv run devkit app dev unlink
```

### Step 4: Verify Clean State
Confirm that every package is `installed` again (no symlinks left and no `.bak` directories; the command exits 1 otherwise):

```bash
uv run devkit app dev status
```

---

## 2. Command Reference

| Command | Options | Description |
|---|---|---|
| `uv run devkit app dev link` | `--target-path`, `--dry-run` | Back up installed packages and create symlinks to local `app-common` source. |
| `uv run devkit app dev unlink` | `--dry-run` | Remove symlinks and restore original `*.bak` packages. |
| `uv run devkit app dev status` | `--target-path` | Inspect linking status (`linked`, `installed`, `anomaly`, `orphan-backup`, `not-installed`). |

Use `--dry-run` with `link` or `unlink` to preview file system changes without applying them.
