#!/usr/bin/env bash
# Shared helpers for module resolution.
# Source this file from scripts or justfile recipes: source ./scripts/_lib.sh

AVAILABLE_MODULES="all app-prebuilt-user app-prebuilt-outbox app-tools app-helper app-layer-base app-file-storage app-vector-store app-http-client app-ai-catalog"

resolve_module() {
    case "$1" in
        app-prebuilt-user|prebuilt-user|user) echo "app-prebuilt-user" ;;
        app-prebuilt-outbox|prebuilt-outbox|outbox) echo "app-prebuilt-outbox" ;;
        app-tools|tools|cli) echo "app-tools" ;;
        app-helper|helper|helpers) echo "app-helper" ;;
        app-layer-base|layer-base|layer) echo "app-layer-base" ;;
        app-file-storage|file-storage|storage) echo "app-file-storage" ;;
        app-vector-store|vector-store|vector) echo "app-vector-store" ;;
        app-http-client|http-client|http) echo "app-http-client" ;;
        app-ai-catalog|ai-catalog|ai) echo "app-ai-catalog" ;;
        all) echo "all" ;;
        *) echo "$1" ;;
    esac
}

resolve_module_path() {
    case "$1" in
        app-prebuilt-user) echo "app-prebuilt-user" ;;
        app-prebuilt-outbox) echo "app-prebuilt-outbox" ;;
        app-tools) echo "app-tools" ;;
        app-helper) echo "app-helper" ;;
        app-layer-base) echo "app-layer-base" ;;
        app-file-storage) echo "app-file-storage" ;;
        app-vector-store) echo "app-vector-store" ;;
        app-http-client) echo "app-http-client" ;;
        app-ai-catalog) echo "app-ai-catalog" ;;
        *) echo "$1" ;;
    esac
}

should_run() {
    [ "$1" = "all" ] || [ "$1" = "$2" ]
}

validate_module() {
    case "$1" in
        all|app-prebuilt-user|app-prebuilt-outbox|app-tools|app-helper|app-layer-base|app-file-storage|app-vector-store|app-http-client|app-ai-catalog) ;;
        *)
            echo "Unknown module: $1" >&2
            echo "Available modules: $AVAILABLE_MODULES" >&2
            return 1
            ;;
    esac
}
