#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/_lib.sh"

DB_TYPE=${1:?Usage: run-tests.sh <db_type> <module> [paths...]}
MODULE=$(resolve_module "${2:-all}")
shift 2 || true
PATHS=("$@")

validate_module "$MODULE"
TEST_TIER="${TEST_TIER:-all}"
case "$TEST_TIER" in
    all|unit|integration|e2e) ;;
    *) echo "TEST_TIER must be all, unit, integration, or e2e" >&2; exit 2 ;;
esac
if [ "$TEST_TIER" != "all" ] && [ "${#PATHS[@]}" -gt 0 ]; then
    echo "Select a tier or explicit test paths, not both" >&2
    exit 2
fi

DEFAULT_PYTEST_OPTIONS="-q --tb=short --disable-warnings --no-header"
PYTEST_OPTIONS="${PYTEST_OPTIONS:-$DEFAULT_PYTEST_OPTIONS}"

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
# runs would rot. Marked with `docker`; see app-file-storage/tests/integration/conftest.py.
DOCKER="${DOCKER:-0}"

# Independent SQLite packages can run together without sharing imports or DBs.
# Keep container and coverage runs serial; TEST_JOBS=1 also restores serial output.
TEST_JOBS="${TEST_JOBS:-4}"
case "$TEST_JOBS" in
    ''|*[!0-9]*|0) echo "TEST_JOBS must be a positive integer" >&2; exit 2 ;;
esac
if [ "$DB_TYPE" != "sqlite" ] || [ "$DOCKER" != "0" ] || [ "$COVERAGE" != "0" ]; then
    TEST_JOBS=1
fi

run_pytest() {
    local module=$1
    shift

    local path
    path=$(resolve_module_path "$module")

    local updated_paths=()
    if [ "$TEST_TIER" != "all" ]; then
        if [ ! -d "$path/tests/$TEST_TIER" ] || ! find "$path/tests/$TEST_TIER" -name 'test_*.py' -type f -print -quit | grep -q .; then
            echo "No $TEST_TIER tests in $module."
            return 0
        fi
        updated_paths+=("tests/$TEST_TIER")
    elif [ "$#" -eq 0 ]; then
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
        app-layer-base|app-testing-base|app-prebuilt-user|app-prebuilt-google-auth|app-prebuilt-api-key|app-prebuilt-outbox|app-prebuilt-search) db_args=(--db-type "$DB_TYPE") ;;
    esac

    # Harmless for packages that have no `docker`-marked tests: nothing matches, nothing
    # is deselected.
    local marker_args=()
    if [ "$DOCKER" != "1" ]; then
        marker_args=(-m "not docker")
    fi

    # Coverage is an explicit report; keep its table visible instead of summarizing it.
    local output_args=()
    if [ "$COVERAGE" = "1" ]; then
        output_args=(--raw)
    fi

    local status=0
    uv run --no-active --no-sync app-tools run pytest --path "$path" ${output_args[@]+"${output_args[@]}"} -- $PYTEST_OPTIONS ${db_args[@]+"${db_args[@]}"} ${marker_args[@]+"${marker_args[@]}"} ${cov_args[@]+"${cov_args[@]}"} "${updated_paths[@]}" || status=$?

    if [ "$status" -eq 5 ]; then
        echo "No tests collected for $module."
        status=0
    fi
    return "$status"
}

status=0
pids=()
pending_modules=()
test_logs=""
if [ "$TEST_JOBS" -gt 1 ]; then
    test_logs=$(mktemp -d "${TMPDIR:-/tmp}/app-common-tests.XXXXXX")
    trap 'rm -rf -- "$test_logs"' EXIT
fi

wait_batch() {
    local index=0 result=0
    for pid in ${pids[@]+"${pids[@]}"}; do
        result=0
        wait "$pid" || result=$?
        cat "$test_logs/${pending_modules[$index]}.log"
        if [ "$result" -ne 0 ]; then
            status=$result
        fi
        index=$((index + 1))
    done
    pids=()
    pending_modules=()
}

for m in app-error app-prebuilt-user app-prebuilt-google-auth app-prebuilt-api-key app-prebuilt-outbox app-prebuilt-search app-tools app-layer-base app-testing-base app-file-storage app-vector-store app-http-client app-ai-catalog app-mcp; do
    if should_run "$MODULE" "$m"; then
        echo "Testing $m..."
        if [ "$TEST_JOBS" -gt 1 ]; then
            run_pytest "$m" ${PATHS[@]+"${PATHS[@]}"} >"$test_logs/$m.log" 2>&1 &
            pids+=("$!")
            pending_modules+=("$m")
            if [ "${#pids[@]}" -ge "$TEST_JOBS" ]; then
                wait_batch
            fi
        else
            run_pytest "$m" ${PATHS[@]+"${PATHS[@]}"} || status=$?
        fi
    fi
done
wait_batch

if [ "$COVERAGE" = "1" ]; then
    unset COVERAGE_FILE
    combined="$COVERAGE_DATA_DIR/.coverage"

    if ls "$COVERAGE_DATA_DIR"/.coverage.* >/dev/null 2>&1; then
        echo
        echo "Combined coverage:"
        # `coverage combine` consumes the per-package data files it merges.
        COVERAGE_FILE="$combined" uv run --no-active --directory "$REPO_ROOT" coverage combine "$COVERAGE_DATA_DIR" >/dev/null

        # A coverage failure must not mask a test failure, so `set -e` is sidestepped here.
        cov_status=0
        COVERAGE_FILE="$combined" uv run --no-active --directory "$REPO_ROOT" coverage report || cov_status=$?
        COVERAGE_FILE="$combined" uv run --no-active --directory "$REPO_ROOT" coverage html --directory htmlcov >/dev/null || cov_status=$?

        if [ "$cov_status" -ne 0 ] && [ "$status" -eq 0 ]; then
            status=$cov_status
        fi
        echo "HTML report: $REPO_ROOT/htmlcov/index.html"
    else
        echo "No coverage data collected."
    fi
fi

exit "$status"
