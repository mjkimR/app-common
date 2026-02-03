# App Tools

Personal app development helper tools and utilities.

## Installation

To add this tool to your project, install it via `uv` from the GitHub repository:

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-tools"
```

## Usage

Run the `app-tools` command to access various utilities.

```bash
app-tools [COMMAND]
```

### Features

#### Create Code (`create-code`)

Generate boilerplate code for new application features.

**Command:**
```bash
app-tools create-code feature --name <FeatureName> [--plural <plural_name>]
```

**Options:**
- `--name`: Name of the feature in CamelCase (e.g., `Article`, `User`).
- `--plural`: (Optional) Plural name in snake_case (e.g., `articles`). If omitted, it will be auto-generated.

**Example:**
Start a new feature module for managing articles:
```bash
app-tools create-code feature --name Article
```

---
*More commands will be added as the project evolves.*