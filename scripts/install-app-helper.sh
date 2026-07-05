#!/usr/bin/env bash
# Install app-helper globally in editable mode using uv tool
set -e

# Get the directory of the script and resolve the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Installing app-helper globally in editable mode..."
uv tool install --editable "$PROJECT_ROOT/app-helper" --force
