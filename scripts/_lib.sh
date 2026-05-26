#!/usr/bin/env bash
# Shared helpers for module resolution.
# Source this file from scripts or justfile recipes: source ./scripts/_lib.sh

AVAILABLE_MODULES="all app-base app-tools"

resolve_module() {
    case "$1" in
        app-base|base|backend) echo "app-base" ;;
        app-tools|tools|cli) echo "app-tools" ;;
        all) echo "all" ;;
        *) echo "$1" ;;
    esac
}

resolve_module_path() {
    case "$1" in
        app-base) echo "app-base" ;;
        app-tools) echo "app-tools" ;;
        *) echo "$1" ;;
    esac
}

should_run() {
    [ "$1" = "all" ] || [ "$1" = "$2" ]
}

validate_module() {
    case "$1" in
        all|app-base|app-tools) ;;
        *)
            echo "Unknown module: $1" >&2
            echo "Available modules: $AVAILABLE_MODULES" >&2
            return 1
            ;;
    esac
}
