#!/usr/bin/env bash
set -e

# Installs and syncs agent skills to local agent configuration directories
# (~/.gemini/config/skills, ~/.claude/skills, ~/.codex/skills) based on meta.yaml.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$PROJECT_ROOT/skills"

# Terminal formatting
BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
NC="\033[0m"

log_info() { echo -e "  [INFO] $*"; }
log_success() { echo -e "${GREEN}  [SUCCESS] $*${NC}"; }
log_warn() { echo -e "${YELLOW}  [WARN] $*${NC}"; }

has_target() {
    local meta_file="$1"
    local target_name="$2"

    [ -f "$meta_file" ] || return 1

    awk -v target="$target_name" '
        BEGIN { in_targets = 0; found = 0 }
        /^[[:space:]]*targets:[[:space:]]*$/ { in_targets = 1; next }
        /^[[:space:]]*[a-zA-Z0-9_]+:[[:space:]]*$/ { in_targets = 0 }
        in_targets && $0 ~ "^[[:space:]]*-[[:space:]]*" target "([[:space:]]*#.*)?$" {
            found = 1
            exit
        }
        END { exit !found }
    ' "$meta_file"
}

link_skill() {
    local src="$1" dest="$2" label="$3"
    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
        local backup="${dest}.bak"
        if [ -e "$backup" ]; then
            log_warn "$dest is a real directory and $backup already exists; skipping $label."
            return 1
        fi
        mv "$dest" "$backup"
        log_warn "Pre-existing $dest moved to $backup"
    fi
    mkdir -p "$(dirname "$dest")"
    ln -sfn "$src" "$dest"
    log_success "Linked to $label: $dest"
}

echo -e "\n${BOLD}Installing / Syncing Agent Skills from $SKILLS_DIR${NC}\n"

ANTIGRAVITY_SKILLS_DIR="$HOME/.gemini/config/skills"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
CODEX_SKILLS_DIR="$HOME/.codex/skills"

skill_count=0
for skill_path in "$SKILLS_DIR"/*/; do
    [ -d "$skill_path" ] || continue
    clean_skill_path="${skill_path%/}"
    skill_name=$(basename "$clean_skill_path")
    meta_file="${clean_skill_path}/meta.yaml"

    [ -f "$meta_file" ] || continue
    skill_count=$((skill_count + 1))

    log_info "Processing skill: ${BOLD}${skill_name}${NC}"

    if has_target "$meta_file" "antigravity"; then
        link_skill "$clean_skill_path" "$ANTIGRAVITY_SKILLS_DIR/$skill_name" "Antigravity"
    fi

    if has_target "$meta_file" "claude"; then
        link_skill "$clean_skill_path" "$CLAUDE_SKILLS_DIR/$skill_name" "Claude Code"
    fi

    if has_target "$meta_file" "codex"; then
        link_skill "$clean_skill_path" "$CODEX_SKILLS_DIR/$skill_name" "Codex"
    fi
done

if [ "$skill_count" -eq 0 ]; then
    log_warn "No skills with meta.yaml found in $SKILLS_DIR"
fi

# Optional: Install app-tools CLI globally via uv tool if requested
if [ "$1" = "--with-tools" ] || [ "$1" = "-t" ]; then
    echo -e "\n${BOLD}Installing tools/app-tools via uv tool...${NC}\n"
    if command -v uv >/dev/null 2>&1; then
        uv tool install --force --editable "$PROJECT_ROOT/tools/app-tools"
        log_success "app-tools installed as an editable tool"
    else
        log_warn "uv command not found. Skipping tool installation."
    fi
fi

echo -e "\n${GREEN}${BOLD}Done! All target skills synchronized.${NC}\n"
