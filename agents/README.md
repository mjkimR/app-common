# Agent guidance

Consumers install one `app-common` skill. Contributors additionally use
`app-common-contributor`. Package-specific instructions remain separate reference
files, loaded only when needed. The onboarding guide under `onboard/` is a one-time
bootstrap procedure, not another installed skill.

The canonical consumer bundle is `agents/skills/app-common/`. app-tools'
`src/app_tools/guide_data` links to it; wheel and sdist builds include ordinary
files. Edit the canonical files only. `catalog.json` records topics, package
applicability, and document version. Bump the manifest and catalog versions with
the package release.

## Install with Microsoft APM

`agents/apm.yml` exposes the `skills/` collection without `.apm/`. Contributor
skills and onboarding are excluded. In a consumer's `apm.yml`:

```yaml
name: my-app
version: 0.1.0
targets: [claude, codex]
dependencies:
  apm:
    - git: mjkimR/app-common
      path: agents
      ref: <full-commit-sha>
      skills: [app-common]
```

Install APM with `uv tool install apm-cli==0.30.0`, then run `apm install`.
Use a pushed commit containing this layout; old refs containing the directory
symlink are not compatible. Keep consumer manifests pinned to Git commits so
standalone and cloud agent checkouts do not require sibling repositories. Push
producer changes before updating the consumer ref; never commit a local path
as a consumer dependency. Private repositories require Git credentials.

Track `apm.yml`, `apm.lock.yaml`, and the copies in `.agents/skills/app-common/`
and `.claude/skills/app-common/`. Ignore `apm_modules/`. Use `apm install --frozen`
for reproduction and `apm audit --ci` to check integrity. Never edit installed
copies. A Git ref update requires `apm install --refresh` and a reviewed lockfile.

## Package updates and contributors

`app-tools update` updates Python package dependencies only. Update the skill ref
in the consumer's APM manifest separately and use the APM workflow above. The
legacy installers, `just link-skills`, and the update command's `--no-skills` and
`--skills-target` options have been removed. Existing callers should drop those
options and replace installer calls with APM provisioning.

For work inside app-common, read `agents/dev-skills/app-common-contributor/SKILL.md`
directly alongside `AGENTS.md`. This repository-only guidance is excluded from the
consumer collection and does not need a custom installer. Existing local links
and prior migration backups are not removed by this change.

## Read

```bash
app-tools guide
app-tools guide list --all
app-tools guide show backend/hooks
app-tools guide --project ./backend show storage/setup
app-tools guide --source ../app-common show backend/hooks
```

The default list uses declared dependencies and the selected project's `.venv`
metadata. Lock entries are reported separately and do not activate guides by
themselves. Optional dependencies and dependency groups are declarations, not a
claim that those extras are installed. Explicit `show` works for uninstalled
packages, allowing agents to read setup instructions before adding a dependency.

If app-tools is unavailable, read `skills/app-common/SKILL.md` and its relative
references directly. See [offline operation and follow-up work](../docs/guide-offline-review.md).
