# agents/

Agent-neutral assets for `app-common`. The source files live in `skills/` (for downstream applications building with `app-common`) and `dev-skills/` (for developers contributing to `app-common` itself). Agent-specific directories (such as `.agents/skills/`, `.claude/skills/`, `.codex/skills/`) are relative symlinks created by `link-skills.sh`.

## Structure

```
agents/
├── README.md                  # This file
├── link-skills.sh             # Symlink manager for local/global agent environments
├── skills/                    # Consumer skills (for developers building apps with app-common)
│   ├── app-backend-core/      # app-layer-base + app-tools + app-error
│   ├── app-adapters/          # app-file-storage + app-vector-store + app-http-client + app-ai-catalog
│   └── app-prebuilt-services/ # app-prebuilt-user + app-prebuilt-outbox
└── dev-skills/                # Contributor skills (for modifying app-common repo itself)
    └── app-common-contributor/# Package isolation, multi-db test harness, release rules
```

## Quick Start

```bash
# Link skills for this repository (Antigravity .agents/skills, includes contributor dev-skills)
./agents/link-skills.sh --dev

# Link for Claude Code (.claude/skills)
./agents/link-skills.sh claude

# Link for Claude Code with dev skills
./agents/link-skills.sh --dev claude

# Link for Codex (.codex/skills)
./agents/link-skills.sh codex

# Link to a custom or global directory
./agents/link-skills.sh --dev ~/.gemini/config/skills
```

Or via `just`:

```bash
just link-skills --dev
```

## Skill Categories

1. **Consumer Skills (`skills/`)**:
   Designed for agents and engineers building applications using `app-common` packages. They are portable and can be linked into any downstream project.
   - **`app-backend-core`**: Core layered architecture (Router → UseCase → Service → Repository → Model/Schema), service hooks, `app-tools create-code feature` scaffolding, and structured error handling (`app-error`).
   - **`app-adapters`**: Standalone adapter integration (S3/Local storage, Qdrant vector store, HTTP client pool, LiteLLM/LangChain catalog), lifespan composition, and decentralized settings.
   - **`app-prebuilt-services`**: Ready-to-mount prebuilt components: user management/JWT auth (`app-prebuilt-user`) and Transactional Outbox pattern (`app-prebuilt-outbox`).

2. **Contributor Dev-Skills (`dev-skills/`)**:
   Only linked when `--dev` is specified. Contains repo-internal conventions, multi-database test rules (SQLite vs PostgreSQL vs Docker MinIO), and package maintenance guidelines.

## Rules
- New skills should be placed in `agents/skills/<name>/SKILL.md` or `agents/dev-skills/<name>/SKILL.md`.
- Always re-run `./agents/link-skills.sh` after adding or renaming skills.
- Dangling symlinks pointing into `agents/` are pruned automatically.
