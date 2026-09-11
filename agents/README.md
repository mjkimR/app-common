# agents/

Agent-neutral assets for `app-common`. The source files live in `skills/` (atomic skills for downstream applications building with `app-common`) and `dev-skills/` (for developers contributing to `app-common` itself). Agent-specific directories (such as `.agents/skills/`, `.claude/skills/`, `.codex/skills/`) are symlinks created by `link-skills.sh`.

## Structure

```
agents/
├── README.md                  # This file
├── link-skills.sh             # Symlink manager supporting auto-detection and selective linking
├── skills/                    # Atomic consumer skills (1:1 with packages for lean context)
│   ├── app-backend-core/      # app-layer-base + app-tools + app-error (FastAPI foundation)
│   ├── app-file-storage/      # AWS S3 / MinIO / Local FS object storage
│   ├── app-vector-store/      # Qdrant vector database + LangChain embeddings
│   ├── app-http-client/       # Pooled singleton httpx client (async & sync)
│   ├── app-ai-catalog/        # LiteLLM YAML catalog & model routing
│   ├── app-prebuilt-user/     # User authentication, JWT, OAuth2 form login
│   └── app-prebuilt-outbox/   # Transactional Outbox pattern & event relay
└── dev-skills/                # Contributor skills (for modifying app-common repo itself)
    └── app-common-contributor/# Package isolation, multi-db test harness, release rules
```

## Remote AI Onboarding (No Installation Needed)

To bootstrap a new FastAPI project from scratch using an AI coding assistant (Antigravity, Claude Code, Cursor, Codex), simply prompt your agent with the GitHub link to the onboarding guide:

> *"Please onboard app-common into this project using this guide: https://github.com/mjkimR/app-common/blob/main/agents/onboard/SKILL.md"*

The agent will read the guide directly from GitHub, interview you about required technologies (database, storage, auth, outbox), install only the necessary packages, and download the matching agent skills into your workspace.

## Quick Start

### In Downstream Projects (Consumer Apps)
Use `--auto` to automatically inspect `pyproject.toml` and link **only** the skills corresponding to installed `app-*` packages:

```bash
# Auto-detect installed app-* packages and link to Antigravity (.agents/skills)
<path-to-app-common>/agents/link-skills.sh --auto

# Auto-detect for Claude Code (.claude/skills)
<path-to-app-common>/agents/link-skills.sh --auto claude

# Selectively link specific skills
<path-to-app-common>/agents/link-skills.sh app-backend-core app-file-storage
```

### In `app-common` (Monorepo Development)
```bash
# Link all skills including contributor dev-skills
just link-skills --dev

# Or directly:
./agents/link-skills.sh --dev
```

## Skill Categories

1. **Foundational Core (`app-backend-core`)**:
   Core 4-layer architecture (`Router → UseCase → Service → Repository → Model/Schema`), service hooks, `app-tools create-code feature` scaffolding, and `app-error` structured advisories.

2. **Atomic Adapters (`app-file-storage`, `app-vector-store`, `app-http-client`, `app-ai-catalog`)**:
   Individual skills matching their respective packages. Projects only load the adapter skills they actually use.

3. **Prebuilt Domains (`app-prebuilt-user`, `app-prebuilt-outbox`)**:
   Ready-to-mount business components: user auth & JWT (`app-prebuilt-user`) and guaranteed event delivery (`app-prebuilt-outbox`).

4. **Contributor Dev-Skill (`app-common-contributor`)**:
   Only linked when `--dev` is specified. Contains repo-internal conventions, multi-database test rules (SQLite vs PostgreSQL vs Docker MinIO), and package maintenance guidelines.
