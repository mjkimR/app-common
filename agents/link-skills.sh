#!/usr/bin/env bash
# Link agent-neutral skills in agents/ into an agent's project or global skill directory.
#
# Skills:
#   agents/skills/      atomic consumer skills (app-backend-core, app-file-storage, ...)
#   agents/dev-skills/  contributor skills (for people developing app-common itself)
#
# Usage:
#   ./agents/link-skills.sh                 # Default: link all consumer skills to .agents/skills
#   ./agents/link-skills.sh --auto          # Auto-detect installed app-* packages from pyproject.toml
#   ./agents/link-skills.sh --dev           # Include contributor dev-skills
#   ./agents/link-skills.sh <skill...>      # Link only specified skills (e.g. app-backend-core app-file-storage)
#   ./agents/link-skills.sh claude          # Target Claude Code (.claude/skills)
#   ./agents/link-skills.sh codex           # Target Codex (.codex/skills)
#   ./agents/link-skills.sh --target <dir>  # Custom target directory (e.g. ~/.gemini/config/skills)
#
# In consumer projects:
#   <path-to-app-common>/agents/link-skills.sh --auto
#   reads the consumer's pyproject.toml and links only the installed adapter/prebuilt skills!

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

with_dev=false
auto_detect=false
target_agent="antigravity"
custom_target=""
selected_skills=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev)
      with_dev=true
      shift
      ;;
    --auto)
      auto_detect=true
      shift
      ;;
    --all)
      shift
      ;;
    --target|-t)
      custom_target="$2"
      shift 2
      ;;
    antigravity|claude|codex)
      target_agent="$1"
      shift
      ;;
    -h|--help)
      sed -n '2,19p' "$0" | sed 's/^# //'
      exit 0
      ;;
    app-*)
      selected_skills+=("$1")
      shift
      ;;
    /*|./*|../*|~*)
      custom_target="$1"
      shift
      ;;
    *)
      # Check if argument matches a skill name directly
      if [ -d "$repo_root/agents/skills/$1" ] || [ -d "$repo_root/agents/dev-skills/$1" ]; then
        selected_skills+=("$1")
      elif [ -z "$custom_target" ]; then
        custom_target="$1"
      fi
      shift
      ;;
  esac
done

# Resolve target destination path
if [ -n "$custom_target" ]; then
  dest="$custom_target"
else
  case "$target_agent" in
    antigravity) dest=".agents/skills" ;;
    claude)      dest=".claude/skills" ;;
    codex)       dest=".codex/skills" ;;
  esac
fi

# Expand home directory if ~ is used
dest="${dest/#\~/$HOME}"

if [[ "$dest" = /* ]]; then
  dest_dir="$dest"
  is_external=true
else
  dest_dir="$(pwd)/$dest"
  is_external=false
fi

mkdir -p "$dest_dir"

# Determine which skills to link
skills_to_link=()

if [ ${#selected_skills[@]} -gt 0 ]; then
  # User specified explicit skills
  skills_to_link=("${selected_skills[@]}")
elif $auto_detect; then
  # Auto-detect from pyproject.toml or uv.lock in current working directory
  manifest=""
  if [ -f "pyproject.toml" ]; then
    manifest="pyproject.toml"
  elif [ -f "uv.lock" ]; then
    manifest="uv.lock"
  fi

  if [ -n "$manifest" ]; then
    echo "Auto-detecting dependencies from $manifest..."
    # Always include core if any base package is present or as default
    if grep -qE "app-layer-base|app-tools|app-error" "$manifest" 2>/dev/null || [ "$PWD" = "$repo_root" ]; then
      skills_to_link+=(app-backend-core)
    fi
    grep -q "app-file-storage" "$manifest" 2>/dev/null && skills_to_link+=(app-file-storage)
    grep -q "app-vector-store" "$manifest" 2>/dev/null && skills_to_link+=(app-vector-store)
    grep -q "app-http-client" "$manifest" 2>/dev/null && skills_to_link+=(app-http-client)
    grep -q "app-ai-catalog" "$manifest" 2>/dev/null && skills_to_link+=(app-ai-catalog)
    grep -q "app-prebuilt-user" "$manifest" 2>/dev/null && skills_to_link+=(app-prebuilt-user)
    grep -q "app-prebuilt-outbox" "$manifest" 2>/dev/null && skills_to_link+=(app-prebuilt-outbox)

    # If nothing matched in app-common root, default to all
    if [ ${#skills_to_link[@]} -eq 0 ] && [ "$PWD" = "$repo_root" ]; then
      for s in "$repo_root"/agents/skills/*/; do
        [ -d "$s" ] && skills_to_link+=("$(basename "$s")")
      done
    fi
  else
    echo "No pyproject.toml or uv.lock found in current directory; defaulting to all skills."
    for s in "$repo_root"/agents/skills/*/; do
      [ -d "$s" ] && skills_to_link+=("$(basename "$s")")
    done
  fi
else
  # Default: all consumer skills
  for s in "$repo_root"/agents/skills/*/; do
    [ -d "$s" ] && skills_to_link+=("$(basename "$s")")
  done
fi

if $with_dev; then
  for s in "$repo_root"/agents/dev-skills/*/; do
    [ -d "$s" ] && skills_to_link+=("$(basename "$s")")
  done
fi

echo "Linking ${#skills_to_link[@]} skills to $dest_dir:"

for name in "${skills_to_link[@]}"; do
  # Locate skill source
  if [ -d "$repo_root/agents/skills/$name" ]; then
    src_path="$repo_root/agents/skills/$name"
  elif [ -d "$repo_root/agents/dev-skills/$name" ]; then
    src_path="$repo_root/agents/dev-skills/$name"
  else
    echo "  warning : skill '$name' not found under agents/skills/ or agents/dev-skills/"
    continue
  fi

  link="$dest_dir/$name"

  if [ "$PWD" = "$repo_root" ] && ! $is_external; then
    # In repo root: compute relative path
    depth="$(printf '%s' "$dest" | awk -F/ '{print NF}')"
    up=""
    for ((i = 0; i < depth; i++)); do up="../$up"; done
    sub="skills"
    [ -d "$repo_root/agents/dev-skills/$name" ] && sub="dev-skills"
    target_link="${up}agents/$sub/$name"
  else
    # External project or absolute target: use absolute link to app-common skill source
    target_link="$src_path"
  fi

  if [ -L "$link" ]; then
    ln -sfn "$target_link" "$link"
    echo "  relinked: $name -> $target_link"
  elif [ -e "$link" ]; then
    echo "  skipped : $name (exists and is not a symlink)"
  else
    ln -s "$target_link" "$link"
    echo "  linked  : $name -> $target_link"
  fi
done

# Prune dangling symlinks pointing into agents/
for link in "$dest_dir"/*; do
  [ -L "$link" ] || continue
  link_target="$(readlink "$link")" || true
  case "$link_target" in
    *agents/*)
      if [ ! -e "$link" ]; then
        rm "$link"
        echo "  pruned  : $(basename "$link") (broken link)"
      fi
      ;;
    *) ;;
  esac
done

echo "Done."
