# App Tools

Personal app development helper tools and utilities.

## Installation

To add this tool to your project, install it via `uv` from the GitHub repository:

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=tools/app-tools" --dev
```

## Usage

Run the `app-tools` command to access various utilities.

```bash
app-tools [COMMAND]
```

### Features

#### Create Code (`create-code`)

Generate boilerplate code for new application features.

**1. Backend Feature (FastAPI Layered Architecture):**
```bash
app-tools create-code feature --name <FeatureName> [--plural <plural_name>] [--prefix <prefix>]
```
- `--name`: Name of the feature in CamelCase (e.g., `Article`, `User`).
- `--plural`: (Optional) Plural name in snake_case (e.g., `articles`). If omitted, it will be auto-generated.
- `--prefix`: (Optional) Directory prefix (defaults to `app/features`).

*Example:*
```bash
app-tools create-code feature --name Article
```

**2. Web Feature (Svelte 5 Runes & shadcn UI):**
```bash
app-tools create-code web-feature --name <FeatureName> [--plural <plural_name>] [--prefix <prefix>]
```
- Generates Svelte 5 state store (`*.svelte.ts`), main view (`*View.svelte`), dialog (`*Dialog.svelte`), and index exports.
- `--prefix`: (Optional) Directory prefix (auto-detects `src/lib/features` or `web/src/lib/features`).

*Example:*
```bash
app-tools create-code web-feature --name Project
```

#### Local Development Linking (`dev`)

Link installed `app-common` packages in downstream projects to a local clone of `app-common` without modifying `pyproject.toml` or `package.json`.

- **Link packages**:
  ```bash
  app-tools dev link
  # Or specify custom path
  app-tools dev link --target-path ../app-common
  ```
- **Check status**:
  ```bash
  app-tools dev status
  ```
- **Unlink & restore original packages**:
  ```bash
  app-tools dev unlink
  ```

---
*More commands will be added as the project evolves.*

## Documentation

For a complete list of commands, usage examples, and details on how code generation works, please refer to the developer guide:

- **[App Backend Core Developer Skill](../../agents/skills/app-backend-core/SKILL.md)**