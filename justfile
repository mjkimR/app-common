# Print available commands
default:
    @just --list

# Initialize project modules (all, app-base, or app-tools)
init module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    if [ "$target" = "all" ]; then
        echo "Initializing workspace..."
        uv sync
    else
        echo "Initializing $target..."
        uv sync --package "$target"
    fi

    just hooks-install

# Initialize project modules with all optional dependencies
init-dev module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    if [ "$target" = "all" ]; then
        echo "Initializing workspace with extras..."
        uv sync --all-extras
    else
        echo "Initializing $target with extras..."
        uv sync --package "$target" --all-extras
    fi

    just hooks-install

# Run ruff format and lint for a specific module (all, app-base, or app-tools)
lint module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    if should_run "$target" "app-base"; then
        path=$(resolve_module_path "app-base")
        echo "Linting app-base ($path)..."
        uv run ruff format "$path"
        uv run ruff check --fix "$path"
    fi

    if should_run "$target" "app-tools"; then
        path=$(resolve_module_path "app-tools")
        echo "Linting app-tools ($path)..."
        uv run ruff format "$path"
        uv run ruff check --fix "$path"
    fi

# Run pyright static type checking for a specific module (all, app-base, or app-tools)
check module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    if should_run "$target" "app-base"; then
        path=$(resolve_module_path "app-base")
        echo "Type checking app-base ($path)..."
        uv run pyright "$path/src"
    fi

    if should_run "$target" "app-tools"; then
        path=$(resolve_module_path "app-tools")
        echo "Type checking app-tools ($path)..."
        uv run pyright "$path/src"
    fi

# Run ruff format and lint checks without modifying files
lint-check module="all":
    #!/usr/bin/env bash
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    if should_run "$target" "app-base"; then
        path=$(resolve_module_path "app-base")
        echo "Checking lint for app-base ($path)..."
        uv run ruff format --check "$path"
        uv run ruff check "$path"
    fi

    if should_run "$target" "app-tools"; then
        path=$(resolve_module_path "app-tools")
        echo "Checking lint for app-tools ($path)..."
        uv run ruff format --check "$path"
        uv run ruff check "$path"
    fi

# Install pre-commit hooks
hooks-install:
    uv run pre-commit install

# Run pre-commit hooks against all files
hooks-run:
    uv run pre-commit run --all-files

# Run tests with SQLite (default)
test +paths="":
    @bash ./scripts/run-tests.sh sqlite app-base {{ paths }}

# Run tests with PostgreSQL
test-pg +paths="":
    @bash ./scripts/run-tests.sh postgres app-base {{ paths }}
