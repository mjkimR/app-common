#!/usr/bin/env bash
# Install the unified consumer skill from a local checkout or a pinned remote ref.
# Use --copy with a local checkout for an offline, portable installation.
set -euo pipefail
with_tools=false
global=false
ref="main"
args=(--all)
for arg in "$@"; do
  case "$arg" in
    --with-tools|-t) with_tools=true ;;
    --ref=*) ref="${arg#--ref=}" ;;
    --global|-g) global=true ;;
    *) args+=("$arg") ;;
  esac
done
repo_root=""
script_path="${BASH_SOURCE[0]:-}"
if [[ -n "$script_path" && -f "$script_path" ]]; then
  candidate="$(cd "$(dirname "$script_path")/.." && pwd)"
  [[ -f "$candidate/agents/link-skills.sh" ]] && repo_root="$candidate"
fi
if [[ -z "$repo_root" ]]; then
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "$temp_dir"' EXIT
  git clone --depth 1 --branch "$ref" -q https://github.com/mjkimR/app-common.git "$temp_dir/app-common"
  repo_root="$temp_dir/app-common"
  args+=(--copy)
fi
if $global; then
  for target in "$HOME/.gemini/config/skills" "$HOME/.claude/skills" "$HOME/.codex/skills"; do
    bash "$repo_root/agents/link-skills.sh" "${args[@]}" --target "$target"
  done
else
  bash "$repo_root/agents/link-skills.sh" "${args[@]}"
fi
if $with_tools; then
  uv tool install --force "git+https://github.com/mjkimR/app-common.git@$ref#subdirectory=tools/app-tools"
fi
