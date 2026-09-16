# Unified guidance: offline operation and follow-up work

The first implementation replaces twelve consumer skill entry points with one
`app-common` skill and 26 independently readable topics. The contributor skill
remains separate. Canonical Markdown and the catalog live inside app-tools and
are also distributed as a self-contained copied skill.

## Offline operation

| Environment | Guidance availability | Preparation / limitation |
|---|---|---|
| Copied consumer skill, no Python or app-tools | Read `SKILL.md` and relative references directly | Copy the complete bundle before isolation; no CLI is needed |
| app-tools and its dependencies already installed | `app-tools guide`, `guide list`, and `guide show` work locally | Use the installed executable; no package import beyond app-tools' own dependencies |
| Existing uv environment | `uv run --no-sync --offline app-tools guide` | The environment must already contain app-tools; an empty uv cache cannot supply missing packages |
| app-common checkout available | Local `agents/link-skills.sh --copy` works without network | Requires Bash and standard filesystem utilities |
| Consumer with only links to a developer's checkout | Links can break when moved to cloud | Use `--copy` and include the resulting files in the cloud checkout/artifact |
| No skill bundle and no installed tool | Guidance is unavailable locally | Provision the skill or tool during image/setup preparation |
| Remote installer / `app-tools update` | Still requires network | GitHub release lookup, clone/download, uv locking/syncing are not offline operations |
| Package setup or service-backed tests | Depends on the task | Downloaded dependencies, browser binaries, Docker images, S3/Qdrant/LLM services must be provisioned or reachable separately |

The guide reader uses only local manifests, lock entries, distribution metadata,
and bundled Markdown. It never invokes uv, imports optional application packages,
executes a subprocess, or fetches documentation. It does not automatically install
anything when no matching dependencies are found.

For a cloud image that already contains app-tools:

```bash
.venv/bin/app-tools guide
.venv/bin/app-tools guide show storage/setup
```

When existing scripts invoke uv internally, `UV_NO_SYNC=true UV_OFFLINE=true`
can keep those invocations within the pre-provisioned environment. These settings
do not create missing packages. During validation, an existing generated-code test
called ordinary `uv run pyright`, which attempted to fetch hatchling; that same
test passed with the environment variables above and the existing environment.

## Validation evidence

- Tested standalone `app-error` routing without backend guidance, uninstalled-package
  setup access, uv workspace exclusions/groups, frontend manifests, invalid
  manifests, and explicit checkout overrides.
- Tested separate declared, locked, and installed state with synthetic project
  metadata; the CLI does not inspect the global app-tools environment as the consumer.
- Blocked socket and subprocess calls during guide reads.
- Tested local copy installation, legacy custom-file backups, repeated installation,
  contributor links, and remote installer routing using a local Git stub with a
  pinned ref. The latter validates installer behavior, not GitHub availability.
- Deleted the original checkout after copying and confirmed references remained readable.
- Built an app-tools wheel and sdist using locally cached build tooling. Checked
  all 28 bundle files (26 topics, entry point, catalog), rebuilt a wheel from the
  extracted sdist, and read guidance from an extracted wheel outside the source
  checkout with socket/subprocess calls blocked.
- All 70 app-tools tests passed with `UV_NO_SYNC=true UV_OFFLINE=true`; Ruff,
  Pyright, shell syntax checks, and skill validation passed.

This is local validation of the offline execution paths, not a deployment test in
an external agent-cloud service. Cloud checkout inclusion, executable permissions,
Python availability, and setup-stage dependencies remain properties of that service.

## Ownership after the planned apm transition

The planned delegation concerns **skill management**, not Python/Node package
management. apm integration is not implemented here, and its concrete commands,
metadata format, and offline guarantees have not been established.

| Responsibility | Intended owner |
|---|---|
| Skill discovery/registry, installation, updates, removal, agent-specific destinations | apm |
| Skill artifact version selection, download/cache, installation provenance and integrity | apm; consume its supported metadata once the interface is established |
| Skill entry point, topic documents, applicability rules, relative references | app-common |
| Read-only project inspection and selecting/reading relevant guides | app-tools guide |
| Comparing available guide provenance with application package metadata | app-tools guide, without fetching or resolving skill versions |
| Python/Node dependencies and existing package update operations | Existing package tooling; unchanged by the skill-management decision |

Keep `agents/link-skills.sh` and `scripts/install-skills.sh` as transitional
installation paths. Do not expand them into a registry, cache, version resolver,
or general-purpose skill manager. Once apm can provision the complete bundle and
consumer workflows have migrated, retire these paths or retain only a thin
compatibility wrapper if callers still need it.

The skill synchronization step in `app-tools update` is a separate delegation
point: replace that step with the established apm integration when available.
Do not move application dependency updates to apm as part of this transition.
The existing `--no-skills` option already lets a caller manage skill provisioning
separately from package updates.

Preserve the manager-independent bundle contract: `SKILL.md`, its relative
references, and `catalog.json` must remain readable together after installation.
The catalog maps topics to package applicability; it is not an installation
lockfile. Keep one canonical document source for the skill artifact and app-tools
package. Avoid adding an apm-specific adapter or manifest before its interface is
known. The guide reader must not invoke apm or install anything during a read.

## Reduced follow-up scope

1. **Offline runtime CI and routing quality: retain.** Test a pre-provisioned bundle
   and installed CLI in Linux with egress disabled, including file-only reading
   without app-tools. Exercise missing-adapter setup, error-only projects, hooks,
   testing, and frontend tasks. Test apm provisioning separately at its integration
   boundary when available; app-common CI need not reproduce a skill manager.
2. **Project selection: expand only for demonstrated consumer needs.** Current
   detection covers root manifests, explicit uv workspace members/exclusions,
   dependency groups/extras, root or `web` npm manifests, and the selected project's
   `.venv`. Shared parent environments, custom virtualenv paths, active extras,
   Node workspace graphs/lockfiles, and Poetry declarations remain unsupported.
   These affect guide relevance, so they remain app-tools concerns, but do not
   justify implementing a general package resolver.
3. **Provenance comparison: defer custom infrastructure.** Keep the existing
   document version, source display, and detectable mismatch warnings. Equal
   versions still do not prove equal Git commits. Use apm-provided artifact
   provenance if its eventual interface exposes it; otherwise report unavailable
   information. Do not build a parallel skill commit resolver, digest registry,
   cache, or automatic version retrieval system in app-tools.
4. **Local development: keep explicit source selection first.** `--source
   <checkout>` already selects local documentation. Defer automatic per-package
   document revision selection and multi-version storage. If active development
   links cause repeated mistakes, first expose their source paths and recommend
   an explicit source override; let the skill manager own managed skill sources.

Priority: offline read/routing validation, then concrete consumer detection gaps.
Skill installation enhancements and automatic multi-version guide management
are removed from the app-common roadmap in favor of the planned apm delegation.
