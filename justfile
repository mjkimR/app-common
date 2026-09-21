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
    set -e
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    for m in app-error app-prebuilt-user app-prebuilt-api-key app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-vector-store app-http-client app-ai-catalog app-mcp; do
        if should_run "$target" "$m"; then
            path=$(resolve_module_path "$m")
            if [ -d "$path" ]; then
                echo "Linting $m ($path)..."
                uv run --no-sync app-tools run lint --fix --path "$path"
            fi
        fi
    done

# Run pyright static type checking for a specific module (all, app-base, or app-tools)
check module="all":
    #!/usr/bin/env bash
    set -e
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    for m in app-error app-prebuilt-user app-prebuilt-api-key app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-vector-store app-http-client app-ai-catalog app-mcp; do
        if should_run "$target" "$m"; then
            path=$(resolve_module_path "$m")
            if [ -d "$path" ]; then
                echo "Type checking $m ($path)..."
                uv run --no-sync app-tools run pyright -- "$path/src"
            fi
        fi
    done

# Run ruff format and lint checks without modifying files
lint-check module="all":
    #!/usr/bin/env bash
    set -e
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    for m in app-error app-prebuilt-user app-prebuilt-api-key app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-vector-store app-http-client app-ai-catalog app-mcp; do
        if should_run "$target" "$m"; then
            path=$(resolve_module_path "$m")
            if [ -d "$path" ]; then
                echo "Checking lint for $m ($path)..."
                uv run --no-sync app-tools run lint --path "$path"
            fi
        fi
    done

# Run architectural constraint validation across packages or specific paths
check-arch +paths="":
    uv run app-tools check-arch {{ paths }}

# Install pre-commit hooks
hooks-install:
    uv run pre-commit install

# Run pre-commit hooks against all files
hooks-run:
    uv run pre-commit run --all-files

# Run tests with SQLite; container-backed tests are deselected, so no Docker is needed
test +paths="":
    @bash ./scripts/run-tests.sh sqlite all {{ paths }}

# Run tests with PostgreSQL (needs Docker: testcontainers)
test-pg +paths="":
    @bash ./scripts/run-tests.sh postgres all {{ paths }}

# Also run the container-backed tests, e.g. the S3 contract against a real MinIO (needs Docker)
test-docker +paths="":
    @DOCKER=1 bash ./scripts/run-tests.sh sqlite all {{ paths }}

# Run tests with coverage, printing a per-package and a combined report.
# Includes the container-backed tests (needs Docker): this is an on-demand "what is
# untested?" tool, and silently dropping half the suite would make it under-report.
# Without a Docker daemon those tests skip and the numbers are correspondingly lower.
test-cov module="all":
    @COVERAGE=1 DOCKER=1 bash ./scripts/run-tests.sh sqlite {{ module }}

# Initialize UI package dependencies
init-ui:
    npm ci
    npm install --prefix packages/ui/app-ui-base

# Enforce file-size limits and type check UI package
check-ui:
    uv run --no-sync app-tools run npm --path packages/ui/app-ui-base -- run lint
    uv run --no-sync app-tools run npm --path packages/ui/app-ui-base -- run check

# Verify the shared frontend file-size preset
test-eslint:
    npm run check
    npm test

# Build UI package into dist/
build-ui:
    uv run --no-sync app-tools run npm --path packages/ui/app-ui-base -- run build
