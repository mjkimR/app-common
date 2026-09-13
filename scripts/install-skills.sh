#!/usr/bin/env bash
set -e

# Installs and syncs agent skills for app-common.
# Works both inside the app-common repository and remotely in downstream consumer projects via curl:
#   curl -sSL https://raw.githubusercontent.com/mjkimR/app-common/vX.Y.Z/scripts/install-skills.sh | bash -s -- --auto --ref=vX.Y.Z

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
PROJECT_ROOT=""
[ -n "$SCRIPT_DIR" ] && PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd || echo "")"

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
auto_detect=false
target_agent="antigravity"
custom_target=""
ref="main"
selected_skills=()

for arg in "$@"; do
    case "$arg" in
        --dev) with_dev=true ;;
        --auto) auto_detect=true ;;
        --with-tools|-t) with_tools=true ;;
        --ref=*) ref="${arg#--ref=}" ;;
        --global|-g) target_agent="global" ;;
        antigravity|claude|codex) target_agent="$arg" ;;
        app-*) selected_skills+=("$arg") ;;
        /*|./*|../*|~*) custom_target="$arg" ;;
    esac
done

echo -e "\n${BOLD}Syncing Agent Skills...${NC}\n"

# Check if running locally inside app-common repo
if [ -n "$PROJECT_ROOT" ] && [ -f "$PROJECT_ROOT/agents/link-skills.sh" ]; then
    log_info "Detected local app-common repository. Linking skills..."
    link_args=()
    $with_dev && link_args+=(--dev)
    $auto_detect && link_args+=(--auto)
    [ -n "$custom_target" ] && link_args+=(--target "$custom_target")
    [ ${#selected_skills[@]} -gt 0 ] && link_args+=("${selected_skills[@]}")
    
    if [ "$target_agent" = "global" ]; then
        "$PROJECT_ROOT/agents/link-skills.sh" "${link_args[@]}" --target "$HOME/.gemini/config/skills"
        "$PROJECT_ROOT/agents/link-skills.sh" "${link_args[@]}" --target "$HOME/.claude/skills"
        "$PROJECT_ROOT/agents/link-skills.sh" "${link_args[@]}" --target "$HOME/.codex/skills"
    else
        "$PROJECT_ROOT/agents/link-skills.sh" "${link_args[@]}" "$target_agent"
    fi
else
    # Remote execution in a consumer repository (e.g. via curl)
    log_info "Running in consumer repository. Fetching skills from GitHub..."

    TMP_DIR="$(mktemp -d)"
    trap 'rm -rf "$TMP_DIR"' EXIT

    git clone --depth 1 --branch "$ref" -q https://github.com/mjkimR/app-common.git "$TMP_DIR/app-common"

    # Resolve target directory
    if [ -n "$custom_target" ]; then
        dest_dir="$custom_target"
    elif [ "$target_agent" = "global" ]; then
        dest_dir="$HOME/.gemini/config/skills"
    else
        case "$target_agent" in
            antigravity) dest_dir=".agents/skills" ;;
            claude)      dest_dir=".claude/skills" ;;
            codex)       dest_dir=".codex/skills" ;;
        esac
    fi

    mkdir -p "$dest_dir"

    # Determine skills to install
    skills_to_install=()
    if [ ${#selected_skills[@]} -gt 0 ]; then
        skills_to_install=("${selected_skills[@]}")
    elif $auto_detect || [ -f "pyproject.toml" ]; then
        manifest="pyproject.toml"
        [ ! -f "$manifest" ] && [ -f "uv.lock" ] && manifest="uv.lock"
        if [ -f "$manifest" ]; then
            log_info "Auto-detecting installed dependencies from $manifest..."
            grep -qE "app-layer-base|app-error" "$manifest" 2>/dev/null && skills_to_install+=(app-backend-core)
            if grep -q "app-tools" "$manifest" 2>/dev/null; then
                skills_to_install+=(app-local-dev app-package-update)
            fi
            grep -q "app-file-storage" "$manifest" 2>/dev/null && skills_to_install+=(app-file-storage)
            grep -q "app-vector-store" "$manifest" 2>/dev/null && skills_to_install+=(app-vector-store)
            grep -q "app-http-client" "$manifest" 2>/dev/null && skills_to_install+=(app-http-client)
            grep -q "app-ai-catalog" "$manifest" 2>/dev/null && skills_to_install+=(app-ai-catalog)
            grep -q "app-mcp" "$manifest" 2>/dev/null && skills_to_install+=(app-mcp)
            grep -q "app-prebuilt-user" "$manifest" 2>/dev/null && skills_to_install+=(app-prebuilt-user)
            grep -q "app-prebuilt-outbox" "$manifest" 2>/dev/null && skills_to_install+=(app-prebuilt-outbox)
            grep -q "app-testing-base" "$manifest" 2>/dev/null && skills_to_install+=(app-testing)

            # Detect frontend/Svelte UI project
            if [ -f "package.json" ] || [ -d "web" ] || [ -f "web/package.json" ]; then
                skills_to_install+=(app-svelte-ui)
            fi
        fi
    fi

    # Fallback to all consumer skills if none detected
    if [ ${#skills_to_install[@]} -eq 0 ]; then
        for s in "$TMP_DIR"/app-common/agents/skills/*/; do
            [ -d "$s" ] && skills_to_install+=("$(basename "$s")")
        done
    fi

    for skill in "${skills_to_install[@]}"; do
        src="$TMP_DIR/app-common/agents/skills/$skill"
        if [ -d "$src" ]; then
            rm -rf "$dest_dir/$skill"
            cp -r "$src" "$dest_dir/$skill"
            log_success "Installed skill: $skill -> $dest_dir/$skill"
        fi
    done
fi

# Optional: Install app-tools CLI globally via uv tool if requested
if $with_tools; then
    echo -e "\n${BOLD}Installing tools/app-tools via uv tool...${NC}\n"
    if command -v uv >/dev/null 2>&1; then
        uv tool install --force "git+https://github.com/mjkimR/app-common.git#subdirectory=tools/app-tools"
        log_success "app-tools installed as global tool"
    else
        log_warn "uv command not found. Skipping tool installation."
    fi
fi

echo -e "\n${GREEN}${BOLD}Done! All target skills synchronized.${NC}\n"
