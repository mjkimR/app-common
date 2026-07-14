# App Helper

General-purpose developer helper tools and utilities. This package is completely independent of the rest of `app-common` and can be used in any environment.

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

Every command reads git diffs with `uv.lock` excluded — lock file churn is huge and adds no signal to an AI prompt.

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
app-helper prompt review [--language English] [--staged | --last]
```

The diff defaults to `HEAD` (all tracked changes). Use `--staged` for staged changes only, or `--last`
to review the previous commit (`HEAD~1..HEAD`). The two flags are mutually exclusive.

#### Diff File (`copy-diff`)

Write the diff to a temp file and put **the file itself** on the clipboard, so it can be pasted as an
attachment into a chat UI rather than as a wall of text:

```bash
app-helper copy-diff [FILENAME] [--no-add]
```

Runs `git add .` first so untracked files show up in the diff; pass `--no-add` to use only what is
already staged. `FILENAME` is optional and gets a `.txt` suffix if it has no extension — otherwise the
file is named after a hash of the diff (`diff-<hash>.txt`).

The file-object clipboard is macOS-only (it goes through `osascript`). On other platforms the diff file
is still written and its path is printed.
