# app-local-dev

Modifying `app-common` packages locally from downstream consumer repositories using `app-tools dev`.

When developing in a downstream consumer project and needing to modify `app-common` packages (`app-layer-base`, `app-error`, adapters, UI, etc.) simultaneously, follow this workflow.

> [!IMPORTANT]
> **Never edit `pyproject.toml` or `package.json` to point to local file paths.**
> Hardcoding local paths causes dirty git diffs and risks accidental commits that break CI or remote deployments.

---

## 1. Quick Workflow

### Step 1: Link Local Source
Run inside the consumer repository root:

```bash
uv run app-tools dev link
# Or explicitly specify target path:
uv run app-tools dev link --target-path ../app-common
```

- **Exploration range**: Automatically discovers `app-common` at `-1 to +1 depth` (same level `../app-common`, sibling folders `../*/`, child `./app-common`, grandparent `../../app-common`).
- **Backup**: Automatically renames installed directories in `.venv/lib/python*/site-packages/` and `node_modules/` to `*.bak`.
- **Symlink**: Creates symlinks to the local `app-common` source directories (`src/<pkg>` or `packages/ui/<pkg>`).
- **UV Lock Protection**: Preserves `.dist-info` metadata so `uv run` will not trigger an automatic re-sync or overwrite your symlinks.

### Step 2: Develop and Test
1. Make your code changes in your local `app-common` repository clone.
2. Run downstream application tests to verify the behavior immediately.
3. For multi-database testing (PostgreSQL row-locking, MinIO/Docker contracts) and package contribution standards, refer to the `agents/dev-skills/app-common-contributor/SKILL.md` in the local app-common checkout (when available).

### Step 3: Unlink and Restore
Once changes are verified and committed/pushed to `app-common`, **always restore the consumer repository**:

```bash
uv run app-tools dev unlink
```

### Step 4: Verify Clean State
Confirm that all packages have returned to `NORMAL` (no dangling symlinks or orphaned `.bak` directories):

```bash
uv run app-tools dev status
```

---

## 2. Command Reference

| Command | Options | Description |
|---|---|---|
| `uv run app-tools dev link` | `--target-path`, `--dry-run` | Back up installed packages and create symlinks to local `app-common` source. |
| `uv run app-tools dev unlink` | `--dry-run` | Remove symlinks and restore original `*.bak` packages. |
| `uv run app-tools dev status` | `--target-path` | Inspect linking status (`LINKED`, `NORMAL`, `ORPHAN_BAK`, `NOT INSTALLED`). |

Use `--dry-run` with `link` or `unlink` to preview file system changes without applying them.
