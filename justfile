# Print available commands
default:
    @just --list

# Initialize the project (sync dependencies, install hooks, etc)
init:
    uv sync

init-dev:
    uv sync --all-extras

# Run ruff format and lint
lint:
    uv run ruff format
    uv run ruff check --fix

# Run tests with coverage
test db="sqlite":
    just init-dev
    cd app-base/src && uv run pytest --db-type "{{db}}"