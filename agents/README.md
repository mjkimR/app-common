# Agent guidance

Consumers install one `app-common` skill. Contributors additionally use
`app-common-contributor`. Package-specific instructions remain separate reference
files, loaded only when needed. The onboarding guide under `onboard/` is a one-time
bootstrap procedure, not another installed skill.

The canonical consumer bundle is `tools/app-tools/src/app_tools/guide_data/`.
`agents/skills/app-common` is a relative symlink to that directory, so the wheel,
source distribution, and copied skill share the same documents. Do not maintain a
second copy. `catalog.json` records topics, package applicability, and the document
version; update that version when bumping package versions.

## Install

Skill lifecycle management is planned to move to apm. The scripts below remain
transitional installation paths; their current behavior is unchanged. app-common
owns the guide content and app-tools owns read-only document selection. Do not
add a parallel skill registry, cache, or version resolver here. apm integration
will be specified once its interface is established. This delegation does not
change Python/Node package management. See the
[ownership and reduced roadmap](../docs/guide-offline-review.md#ownership-after-the-planned-apm-transition).

Run from the consumer project, using an existing checkout:

```bash
<checkout>/agents/link-skills.sh --auto
<checkout>/agents/link-skills.sh claude
<checkout>/agents/link-skills.sh --copy
```

`--auto` remains accepted; every consumer receives the same small entry point.
Dependency detection now selects recommended documents at read time. `--copy`
includes the Markdown references as ordinary files without checkout symlinks.
Use it when preparing a cloud checkout or an offline artifact. No Python or network
is needed for this local installation or for reading the copied references.

Inside app-common, use `just link-skills --dev` to include contributor guidance.
`--target <directory>` overrides the destination. Former consumer skill names
remain accepted as aliases for the unified entry point.

On migration, existing legacy skills and replaced copies are moved into
`<agent-directory>/skill-backups/app-common.<unique-id>/`, outside the skills
directory. This preserves local edits for comparison or restoration. Existing
links to the same bundle are left alone. Backups can be removed after reviewing
any local changes.

The remote `scripts/install-skills.sh --ref=<release-tag>` installer clones that
ref and uses the same installer in copy mode. `app-tools update` downloads the
selected release's installer, so a release containing this change migrates to the
unified skill. Both remote installation and updates need network access.

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
