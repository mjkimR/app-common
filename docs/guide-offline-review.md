# Unified guidance: offline operation

One consumer `app-common` skill with independently readable topics, shipped inside the
app-tools wheel as the `app-common` devkit bundle. The contributor skill is the separate,
repository-only `app-common-dev` bundle. APM is no longer used: the skill version follows
the app-tools commit the project pins, so packages and guidance cannot drift apart.

## Offline operation

| Environment | Guidance availability | Preparation / limitation |
|---|---|---|
| Checkout with committed projections, no Python | Read `.agents/skills/app-common/` or `.claude/skills/app-common/` directly | The consumer commits the projected skill; no CLI is needed |
| Existing uv environment with app-tools | `uv run --no-sync --offline devkit app guide list` / `guide show <topic>` | The environment must already contain app-tools and devkit; an empty uv cache cannot supply missing packages |
| Fresh clone without committed projections | `uv sync`, then `uv run devkit sync` | Both need the packages; prepare them before isolation |
| app-common checkout available | Read the sources under `tools/app-tools/src/app_tools/bundle/skills/app-common/` | No installer is needed for direct file access |
| `devkit app update` | Needs network (git ls-remote, the app-common manifest, uv) | Run before isolation |
| Package setup or service-backed tests | Depends on the task | Downloaded dependencies, browser binaries, Docker images, S3/Qdrant/LLM services must be provisioned or reachable separately |

The guide reader uses only local manifests, lock entries, distribution metadata, and
bundled Markdown. It never invokes uv, imports optional application packages, executes
a subprocess, or fetches documentation; a test blocks sockets and subprocesses while it
reads. The skill has no devkit constitution or instructions, so `devkit sync` deploys
`SKILL.md` unchanged: reading it never requires running devkit.

## Ownership

| Responsibility | Owner |
|---|---|
| Skill deployment to Claude Code, Codex and Antigravity, removal, drift and ownership checks | devkit (`devkit sync`, receipt in `.devkit/installation.json`) |
| Skill and architecture-rule version selection | The app-tools commit the consumer pins (`devkit app update`) |
| Skill entry point, topic documents, applicability catalog, rules | app-common (`tools/app-tools/src/app_tools/bundle/`) |
| Read-only project inspection and selecting/reading relevant guides | `devkit app guide` |
| Python/Node dependencies | uv and npm |
