#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_lib.sh"

DB_TYPE=${1:?Usage: run-tests.sh <db_type> <module> [paths...]}
MODULE=$(resolve_module "${2:-all}")
shift 2 || true
PATHS=("$@")

validate_module "$MODULE"

DEFAULT_PYTEST_OPTIONS="-q --tb=short --disable-warnings --no-header"
PYTEST_OPTIONS="${PYTEST_OPTIONS:-$DEFAULT_PYTEST_OPTIONS}"
PROGRESS_LINE_FILTER='^[\.sFxFw]*\s+\[.*\]$'

# Coverage (opt-in via COVERAGE=1, normally through `just test-cov`).
# Each package is measured from its own directory, so every run writes its own
# data file into COVERAGE_DATA_DIR; they are combined into one report at the end.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COVERAGE="${COVERAGE:-0}"
COVERAGE_DATA_DIR="$REPO_ROOT/.coverage_data"

if [ "$COVERAGE" = "1" ]; then
    mkdir -p "$COVERAGE_DATA_DIR"
    find "$COVERAGE_DATA_DIR" -maxdepth 1 -type f -name '.coverage*' -delete
fi

# Container-backed tests (opt-in via DOCKER=1, normally through `just test-docker`).
# They spin real backends up and cost seconds, so the default run deselects them and
# stays fast and infra-free. CI runs them on every push -- if it did not, tests nobody
# runs would rot. Marked with `docker`; see app-file-storage/tests/integrate/conftest.py.
DOCKER="${DOCKER:-0}"

run_pytest() {
    local module=$1
    shift

    local path
    path=$(resolve_module_path "$module")

    local updated_paths=()
    if [ "$#" -eq 0 ]; then
        if [ -d "$path/src" ]; then
            updated_paths+=("src")
        fi
        if [ -d "$path/tests" ]; then
            updated_paths+=("tests")
        fi
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

    # Empty-array expansion is unsafe under `set -u` on bash 3.2 (macOS default),
    # hence the ${arr[@]+"${arr[@]}"} guard below.
    local cov_args=()
    if [ "$COVERAGE" = "1" ]; then
        cov_args=(--cov=src --cov-config="$REPO_ROOT/pyproject.toml" --cov-report=term-missing)
        export COVERAGE_FILE="$COVERAGE_DATA_DIR/.coverage.$module"
    fi

    # --db-type comes from the app_layer_base.testing.db plugin, so only the packages
    # that enable it accept the flag; passing it elsewhere is a pytest usage error.
    local db_args=()
    case "$module" in
        app-layer-base|app-prebuilt-user|app-prebuilt-outbox) db_args=(--db-type "$DB_TYPE") ;;
    esac

    # Harmless for packages that have no `docker`-marked tests: nothing matches, nothing
    # is deselected.
    local marker_args=()
    if [ "$DOCKER" != "1" ]; then
        marker_args=(-m "not docker")
    fi

    local tmp
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' RETURN

    local status=0
    uv run --directory "$path" pytest $PYTEST_OPTIONS ${db_args[@]+"${db_args[@]}"} ${marker_args[@]+"${marker_args[@]}"} ${cov_args[@]+"${cov_args[@]}"} "${updated_paths[@]}" >"$tmp" 2>&1 || status=$?

    grep -vE "$PROGRESS_LINE_FILTER" "$tmp" || true
    if [ "$status" -eq 5 ]; then
        echo "No tests collected for $module."
        status=0
    fi
    return "$status"
}

status=0
for m in app-prebuilt-user app-prebuilt-outbox app-tools app-helper app-layer-base app-file-storage app-vector-store app-http-client app-ai-catalog; do
    if should_run "$MODULE" "$m"; then
        echo "Testing $m..."
        if [ "${#PATHS[@]}" -eq 0 ]; then
            run_pytest "$m" || status=$?
        else
            run_pytest "$m" "${PATHS[@]}" || status=$?
        fi
    fi
done

if [ "$COVERAGE" = "1" ]; then
    unset COVERAGE_FILE
    combined="$COVERAGE_DATA_DIR/.coverage"

    if ls "$COVERAGE_DATA_DIR"/.coverage.* >/dev/null 2>&1; then
        echo
        echo "Combined coverage:"
        # `coverage combine` consumes the per-package data files it merges.
        COVERAGE_FILE="$combined" uv run --directory "$REPO_ROOT" coverage combine "$COVERAGE_DATA_DIR" >/dev/null

        # A coverage failure must not mask a test failure, so `set -e` is sidestepped here.
        cov_status=0
        COVERAGE_FILE="$combined" uv run --directory "$REPO_ROOT" coverage report || cov_status=$?
        COVERAGE_FILE="$combined" uv run --directory "$REPO_ROOT" coverage html --directory htmlcov >/dev/null || cov_status=$?

        if [ "$cov_status" -ne 0 ] && [ "$status" -eq 0 ]; then
            status=$cov_status
        fi
        echo "HTML report: $REPO_ROOT/htmlcov/index.html"
    else
        echo "No coverage data collected."
    fi
fi

exit "$status"
