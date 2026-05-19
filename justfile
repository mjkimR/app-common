default_test_path := "app-base/src"

# Print available commands
default:
    @just --list

# Initialize the project (sync dependencies, install hooks, etc)
init:
    uv sync
    just hooks-install

# Initialize the project with all optional dependencies
init-dev:
    uv sync --all-extras
    just hooks-install

# Run ruff format and lint
lint:
    uv run ruff format
    uv run ruff check --fix

# Run ruff format and lint checks without modifying files
lint-check:
    uv run ruff format --check .
    uv run ruff check .

# Install pre-commit hooks
hooks-install:
    uv run pre-commit install

# Run pre-commit hooks against all files
hooks-run:
    uv run pre-commit run --all-files

# Run tests with specified database type and paths
_run_tests db_type +paths: init-dev
    uv run pytest --db-type {{db_type}} {{paths}}

# Run tests with SQLite (default)
test +paths=default_test_path: init-dev
    @just _run_tests sqlite {{paths}}

# Run tests with PostgreSQL
test-pg +paths=default_test_path: init-dev
    @just _run_tests postgres {{paths}}