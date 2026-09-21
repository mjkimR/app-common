#!/usr/bin/env bash
# Shared helpers for module resolution.
# Source this file from scripts or justfile recipes: source ./scripts/_lib.sh

AVAILABLE_MODULES="all app-error app-prebuilt-user app-prebuilt-api-key app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-vector-store app-http-client app-ai-catalog app-mcp"

resolve_module() {
    case "$1" in
        app-error|error|errors) echo "app-error" ;;
        app-prebuilt-api-key|prebuilt-api-key|api-key) echo "app-prebuilt-api-key" ;;
        app-prebuilt-user|prebuilt-user|user) echo "app-prebuilt-user" ;;
        app-prebuilt-outbox|prebuilt-outbox|outbox) echo "app-prebuilt-outbox" ;;
        app-prebuilt-search|prebuilt-search|search) echo "app-prebuilt-search" ;;
        app-tools|tools|cli) echo "app-tools" ;;
        app-layer-base|layer-base|layer) echo "app-layer-base" ;;
        app-testing-base|testing-base|testing) echo "app-testing-base" ;;
        app-file-storage|file-storage|storage) echo "app-file-storage" ;;
        app-vector-store|vector-store|vector) echo "app-vector-store" ;;
        app-http-client|http-client|http) echo "app-http-client" ;;
        app-ai-catalog|ai-catalog|ai) echo "app-ai-catalog" ;;
        app-mcp|mcp) echo "app-mcp" ;;
        all) echo "all" ;;
        *) echo "$1" ;;
    esac
}

resolve_module_path() {
    case "$1" in
        app-error) echo "packages/base/app-error" ;;
        app-prebuilt-api-key) echo "packages/prebuilt/app-prebuilt-api-key" ;;
        app-prebuilt-user) echo "packages/prebuilt/app-prebuilt-user" ;;
        app-prebuilt-outbox) echo "packages/prebuilt/app-prebuilt-outbox" ;;
        app-prebuilt-search) echo "packages/prebuilt/app-prebuilt-search" ;;
        app-tools) echo "tools/app-tools" ;;
        app-layer-base) echo "packages/base/app-layer-base" ;;
        app-testing-base) echo "packages/base/app-testing-base" ;;
        app-file-storage) echo "packages/adapters/app-file-storage" ;;
        app-vector-store) echo "packages/adapters/app-vector-store" ;;
        app-http-client) echo "packages/adapters/app-http-client" ;;
        app-ai-catalog) echo "packages/adapters/app-ai-catalog" ;;
        app-mcp) echo "packages/transports/app-mcp" ;;
        *) echo "$1" ;;
    esac
}

should_run() {
    [ "$1" = "all" ] || [ "$1" = "$2" ]
}

validate_module() {
    case "$1" in
        all|app-error|app-prebuilt-user|app-prebuilt-api-key|app-prebuilt-outbox|app-prebuilt-search|app-tools|app-layer-base|app-testing-base|app-file-storage|app-vector-store|app-http-client|app-ai-catalog|app-mcp) ;;
        *)
            echo "Unknown module: $1" >&2
            echo "Available modules: $AVAILABLE_MODULES" >&2
            return 1
            ;;
    esac
}
