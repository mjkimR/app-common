#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_lib.sh"

DB_TYPE=${1:?Usage: run-tests.sh <db_type> <module> [paths...]}
MODULE=$(resolve_module "${2:-app-base}")
shift 2 || true
PATHS=("$@")

validate_module "$MODULE"

DEFAULT_PYTEST_OPTIONS="-q --tb=short --disable-warnings --no-header"
PYTEST_OPTIONS="${PYTEST_OPTIONS:-$DEFAULT_PYTEST_OPTIONS}"
PROGRESS_LINE_FILTER='^[\.sFxFw]*\s+\[.*\]$'

run_pytest() {
    local module=$1
    shift

    local path
    path=$(resolve_module_path "$module")

    local updated_paths=()
    if [ "$#" -eq 0 ]; then
        updated_paths=("src")
    else
        local item
        for item in "$@"; do
            if [[ "$item" == "$path/"* ]]; then
                updated_paths+=("${item#"$path"/}")
            elif [[ "$item" == "$path" ]]; then
                updated_paths+=(".")
            else
                updated_paths+=("$item")
            fi
        done
    fi

    local tmp
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' RETURN

    local status=0
    if [ "$module" = "app-base" ]; then
        uv run --directory "$path" pytest $PYTEST_OPTIONS --db-type "$DB_TYPE" "${updated_paths[@]}" >"$tmp" 2>&1 || status=$?
    else
        uv run --directory "$path" pytest $PYTEST_OPTIONS "${updated_paths[@]}" >"$tmp" 2>&1 || status=$?
    fi

    grep -vE "$PROGRESS_LINE_FILTER" "$tmp" || true
    if [ "$module" = "app-tools" ] && [ "$status" -eq 5 ]; then
        echo "No app-tools tests collected."
        status=0
    fi
    return "$status"
}

status=0
if should_run "$MODULE" "app-base"; then
    echo "Testing app-base..."
    if [ "${#PATHS[@]}" -eq 0 ]; then
        run_pytest "app-base" || status=$?
    else
        run_pytest "app-base" "${PATHS[@]}" || status=$?
    fi
fi

if should_run "$MODULE" "app-tools"; then
    echo "Testing app-tools..."
    if [ "${#PATHS[@]}" -eq 0 ]; then
        run_pytest "app-tools" || status=$?
    else
        run_pytest "app-tools" "${PATHS[@]}" || status=$?
    fi
fi

exit "$status"
