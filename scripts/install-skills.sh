#!/usr/bin/env bash
set -e

# Installs and syncs agent skills to local/global agent configuration directories
# (~/.gemini/config/skills, ~/.claude/skills, ~/.codex/skills) and local workspace (.agents/skills).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Terminal formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

log_info() { echo -e "  [INFO] $*"; }
log_success() { echo -e "${GREEN}  [SUCCESS] $*${NC}"; }
log_warn() { echo -e "${YELLOW}  [WARN] $*${NC}"; }

with_dev=false
with_tools=false
target_env="local"

for arg in "$@"; do
    case "$arg" in
        --dev) with_dev=true ;;
        --with-tools|-t) with_tools=true ;;
        --global|-g) target_env="global" ;;
    esac
done

dev_flag=""
$with_dev && dev_flag="--dev"

echo -e "\n${BOLD}Syncing Agent Skills...${NC}\n"

if [ "$target_env" = "global" ]; then
    log_info "Linking to global Antigravity config (~/.gemini/config/skills)..."
    "$PROJECT_ROOT/agents/link-skills.sh" $dev_flag "$HOME/.gemini/config/skills"

    log_info "Linking to global Claude Code config (~/.claude/skills)..."
    "$PROJECT_ROOT/agents/link-skills.sh" $dev_flag "$HOME/.claude/skills"

    log_info "Linking to global Codex config (~/.codex/skills)..."
    "$PROJECT_ROOT/agents/link-skills.sh" $dev_flag "$HOME/.codex/skills"
else
    log_info "Linking to local workspace (.agents/skills)..."
    "$PROJECT_ROOT/agents/link-skills.sh" $dev_flag antigravity
fi

# Optional: Install app-tools CLI globally via uv tool if requested
if $with_tools; then
    echo -e "\n${BOLD}Installing tools/app-tools via uv tool...${NC}\n"
    if command -v uv >/dev/null 2>&1; then
        uv tool install --force --editable "$PROJECT_ROOT/tools/app-tools"
        log_success "app-tools installed as an editable tool"
    else
        log_warn "uv command not found. Skipping tool installation."
    fi
fi

echo -e "\n${GREEN}${BOLD}Done! All target skills synchronized.${NC}\n"
