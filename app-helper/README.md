# App Helper

General-purpose developer helper tools and utilities. This package is completely independent of `app-base` and can be used in any environment.

## Installation

To add this helper to your project, install it via `uv` from the GitHub repository:

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-helper" --dev
```

Or install it globally / as a tool:

```bash
uv tool install -e ./app-helper
```

## Usage

Run the `app-helper` command to access various utilities.

```bash
app-helper [COMMAND]
```

### Features

#### AI Prompts (`prompt`)

Generate structured prompts for AI code assistants using git changes.

##### Commit Message Prompt
Generate a prompt containing git staged changes and copy it to the clipboard:
```bash
app-helper prompt commit [--language English]
```

##### Code Review Prompt
Generate a prompt containing recent git diffs and copy it to the clipboard:
```bash
app-helper prompt review [--language Korean] [--staged]
```
