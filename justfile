# Print available commands
default:
    @just --list

# There is deliberately no per-package variant: `uv sync --package` would strip the other
# workspace members (and the bundles they ship) from the shared environment.
# `devkit sync --locked` restores the ignored managed copies from the committed receipt and never rewrites
# committed files: it fails (RECEIPT_STALE) when a bundle source changed without `just sync-agents`.
# Initialize the whole workspace in the shared .venv and restore the deployed devkit bundles
init:
    uv sync --no-active
    uv run --no-active --no-sync devkit sync --locked

# Initialize the whole workspace with all optional dependencies
init-dev:
    uv sync --no-active --all-extras
    uv run --no-active --no-sync devkit sync --locked

# Format and fix with Ruff, redeploy the devkit bundles, then run the devkit rules (architecture included)
lint module="all":
    #!/usr/bin/env bash
    set -e
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    paths=()
    for m in app-prebuilt-auth app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-document-store app-vector-store app-http-client app-ai-catalog app-mcp; do
        if should_run "$target" "$m"; then
            path=$(resolve_module_path "$m")
            if [ -d "$path" ]; then
                echo "Linting $m ($path)..."
                uv run --no-active --no-sync ruff format "$path"
                uv run --no-active --no-sync ruff check --fix "$path"
                paths+=("$path")
            fi
        fi
    done

    # Ruff also formats code blocks in the bundles' Markdown sources: redeploy before the rules load them.
    uv run --no-active --no-sync devkit sync >/dev/null
    if [ "$target" = "all" ]; then
        uv run --no-active --no-sync devkit rules check
    else
        uv run --no-active --no-sync devkit rules check "${paths[@]}"
    fi

# Run pyright static type checking for a module (default: all)
check module="all":
    #!/usr/bin/env bash
    set -e
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    for m in app-prebuilt-auth app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-document-store app-vector-store app-http-client app-ai-catalog app-mcp; do
        if should_run "$target" "$m"; then
            path=$(resolve_module_path "$m")
            if [ -d "$path" ]; then
                echo "Type checking $m ($path)..."
                uv run --no-active --no-sync pyright "$path/src"
            fi
        fi
    done

# Check formatting, Ruff lint, the deployed bundles and the devkit rules (architecture included) without modifying files
lint-check module="all":
    #!/usr/bin/env bash
    set -e
    source ./scripts/_lib.sh
    target=$(resolve_module "{{ module }}")
    validate_module "$target"

    paths=()
    for m in app-prebuilt-auth app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-document-store app-vector-store app-http-client app-ai-catalog app-mcp; do
        if should_run "$target" "$m"; then
            path=$(resolve_module_path "$m")
            if [ -d "$path" ]; then
                echo "Checking lint for $m ($path)..."
                uv run --no-active --no-sync ruff format --check "$path"
                uv run --no-active --no-sync ruff check "$path"
                paths+=("$path")
            fi
        fi
    done

    # Fails when a bundle source changed without `just sync-agents`.
    if ! uv run --no-active --no-sync devkit sync --check >/dev/null; then
        echo "Bundle sources changed without a sync: run 'just sync-agents' and commit the result." >&2
        exit 1
    fi
    if [ "$target" = "all" ]; then
        uv run --no-active --no-sync devkit rules check
    else
        uv run --no-active --no-sync devkit rules check "${paths[@]}"
    fi

# Run the devkit rules (app-common architecture, Markdown links, ...) on the repository or specific paths
rules-check +paths="":
    uv run --no-active --no-sync devkit rules check {{ paths }}

# Run the tests in each deployed rule's folder (devkit rules test [RULE-ID...] [-- PYTEST-ARGS...])
rules-test *args:
    uv run --no-active --no-sync devkit rules test {{ args }}

# Redeploy the devkit bundles after changing their sources (tools/app-tools/src/app_tools/bundle, tools/app-common-dev)
sync-agents:
    uv run --no-active --no-sync devkit sync

# Run tests with SQLite; container-backed tests are deselected, so no Docker is needed
test +paths="":
    @bash ./scripts/run-tests.sh sqlite all {{ paths }}

# Run isolated unit tests, keeping one pytest process per package
test-unit module="all":
    @TEST_TIER=unit bash ./scripts/run-tests.sh sqlite {{quote(module)}}

# Run local DB, filesystem, subprocess, and vector-store integration tests
test-integration module="all":
    @TEST_TIER=integration bash ./scripts/run-tests.sh sqlite {{quote(module)}}

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
    npm --prefix packages/ui/app-ui-base run lint
    npm --prefix packages/ui/app-ui-base run check

# Verify the shared frontend file-size preset
test-eslint:
    npm run check
    npm test

# Build UI package into dist/
build-ui:
    npm --prefix packages/ui/app-ui-base run build

# Initialize standalone frontend API generation tooling
init-api-codegen:
    npm ci
    npm ci --prefix packages/ui/app-ui-api-codegen

# Lint, type check and test shared tag-based API generation
test-api-codegen:
    npm --prefix packages/ui/app-ui-api-codegen run lint
    npm --prefix packages/ui/app-ui-api-codegen run check
    npm --prefix packages/ui/app-ui-api-codegen test
