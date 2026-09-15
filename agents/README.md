# agents/

Agent-neutral assets for `app-common`.

- `skills/`: consumer skills for applications built with `app-common`, installed with [APM](https://github.com/microsoft/apm).
- `apm.yml`: makes `agents/` an APM skill bundle whose skills are `skills/*`.
- `dev-skills/`: contributor skills for changing `app-common` itself. Not deployed.
- `onboard/`: one-time onboarding guide read directly from GitHub. Not deployed.

## Structure

```
agents/
├── README.md                  # This file
├── apm.yml                    # APM skill bundle metadata (consumers use path: agents)
├── link-skills.sh             # Links this checkout's skills into its own agent directories
├── onboard/SKILL.md           # One-time onboarding guide for new projects
├── skills/                    # Consumer skills (1:1 with packages for lean context)
│   ├── app-backend-core/      # app-layer-base + app-error (FastAPI foundation)
│   ├── app-local-dev/         # app-tools dev link/unlink/status (local package linking)
│   ├── app-testing/           # app-testing-base (FastAPI test foundation & assertions)
│   ├── app-file-storage/      # AWS S3 / MinIO / Local FS object storage
│   ├── app-vector-store/      # Qdrant vector database + LangChain embeddings
│   ├── app-http-client/       # Pooled singleton httpx client (async & sync)
│   ├── app-ai-catalog/        # LiteLLM YAML catalog & model routing
│   ├── app-mcp/               # MCP tool registry, scopes, and error boundary
│   ├── app-prebuilt-user/     # User authentication, JWT, OAuth2 form login
│   ├── app-prebuilt-outbox/   # Transactional Outbox pattern & event relay
│   └── app-svelte-ui/         # Svelte 5 Runes, SvelteKit, Tailwind, openapi-fetch
└── dev-skills/                # Contributor skills (for modifying app-common repo itself)
    └── app-common-contributor/# Package isolation, multi-db test harness, release rules
```

## Using the Skills in Another Project

Install APM once (`uv tool install apm-cli`), then list the skills that match the installed packages,
pinned to the same release tag as the packages in `pyproject.toml`:

```yaml
# apm.yml
name: my-app
version: 0.1.0
targets: [claude, codex]
dependencies:
  apm:
    - git: mjkimR/app-common
      path: agents
      ref: <release-tag>
      skills: [app-backend-core, app-testing, app-local-dev]
```

```bash
apm install
```

APM copies the skills into `.claude/skills/` (Claude Code) and `.agents/skills/` (Codex, Antigravity,
Cursor, Gemini) and pins them in `apm.lock.yaml`. Commit `apm.yml`, `apm.lock.yaml`, and the copies;
ignore `apm_modules/`. Never edit the copies: `apm audit --ci` reports them as drift.

To move to a newer release, change `ref` in `apm.yml` together with every app-common ref in
`pyproject.toml`, then run `uv lock` and `apm install`.

| Installed package | Skill |
| --- | --- |
| `app-layer-base`, `app-error` | `app-backend-core` |
| `app-testing-base` | `app-testing` |
| `app-tools` | `app-local-dev` |
| `app-file-storage`, `app-vector-store`, `app-http-client`, `app-ai-catalog`, `app-mcp` | same name |
| `app-prebuilt-user`, `app-prebuilt-outbox` | same name |
| `@app-common/ui-base` | `app-svelte-ui` |

## Adding a Skill

Create `agents/skills/<name>/SKILL.md` whose `name:` frontmatter equals the directory name. `agents/apm.yml`
already covers it; consumers add the name to their `skills:` list. Release tags (`vX.Y.Z`) version the
skills together with the packages.

## Working on `app-common`

```bash
# Link consumer skills plus contributor dev-skills into .agents/skills
just link-skills --dev

# Or for Claude Code (.claude/skills)
./agents/link-skills.sh --dev claude
```

Links point at the sources, so edits take effect immediately.

## Remote AI Onboarding (No Installation Needed)

To bootstrap a new FastAPI project from scratch using an AI coding assistant (Antigravity, Claude Code, Cursor, Codex), simply prompt your agent with the GitHub link to the onboarding guide:

> *"Please onboard app-common into this project using this guide: https://github.com/mjkimR/app-common/blob/main/agents/onboard/SKILL.md"*

The agent will read the guide directly from GitHub, interview you about required technologies (database, storage, auth, outbox), install only the necessary packages, and install the matching agent skills with APM.

## Skill Categories

1. **Foundational Core (`app-backend-core`)**:
   Core 4-layer architecture (`Router → UseCase → Service → Repository → Model/Schema`), service hooks, `app-tools create-code feature` scaffolding, and `app-error` structured advisories.

2. **Testing Foundation (`app-testing`)**:
   Pytest base classes (`UnitTest`, `IntegrationTest`, `E2ETest`), DI resolution (`resolve_dependency`), deterministic test seeders, and response assertions.

3. **Atomic Adapters (`app-file-storage`, `app-vector-store`, `app-http-client`, `app-ai-catalog`)**:
   Individual skills matching their respective packages. Projects only load the adapter skills they actually use.

4. **Prebuilt Domains (`app-prebuilt-user`, `app-prebuilt-outbox`)**:
   Ready-to-mount business components: user auth & JWT (`app-prebuilt-user`) and guaranteed event delivery (`app-prebuilt-outbox`).

5. **MCP Transport (`app-mcp`)**:
   Protocol-neutral MCP tool registry, trusted caller context, scope enforcement, and `AppError` translation.

6. **Frontend UI (`app-svelte-ui`)**:
   Agent-First Svelte 5 Runes, SvelteKit layout and AppShell, shadcn atomic primitives, Tailwind tokens, and type-safe `openapi-fetch` client bindings.

7. **Local Development Linking (`app-local-dev`)**:
   Seamlessly link installed `app-common` packages in consumer repositories to a local clone of `app-common` using `app-tools dev` (`link`, `unlink`, `status`) without touching `pyproject.toml` or `package.json`.

8. **Contributor Dev-Skill (`app-common-contributor`)**:
   Only linked when `--dev` is specified. Not published. Contains repo-internal conventions, multi-database test rules (SQLite vs PostgreSQL vs Docker MinIO), and package maintenance guidelines.
