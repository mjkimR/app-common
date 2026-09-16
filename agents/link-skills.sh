#!/usr/bin/env bash
# Install the app-common consumer entry point and optional contributor skill.
# Usage: link-skills.sh [--dev] [--copy] [--target DIR] [antigravity|claude|codex]
# --copy creates a portable offline bundle. Default links to this checkout.
# --auto, --all, and former consumer skill names remain accepted for migration.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
with_dev=false
copy=false
dest=".agents/skills"
legacy=(app-backend-core app-testing app-file-storage app-vector-store app-http-client app-ai-catalog app-mcp app-prebuilt-user app-prebuilt-outbox app-svelte-ui app-local-dev app-package-update)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev|app-common-contributor) with_dev=true; shift ;;
    --copy) copy=true; shift ;;
    --auto|--all|app-common) shift ;;
    --target|-t) dest="${2:?--target requires a directory}"; shift 2 ;;
    antigravity) dest=".agents/skills"; shift ;;
    claude) dest=".claude/skills"; shift ;;
    codex) dest=".codex/skills"; shift ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    app-*)
      found=false
      for name in "${legacy[@]}"; do [[ "$1" == "$name" ]] && found=true; done
      if ! $found; then echo "Unknown skill: $1" >&2; exit 2; fi
      shift ;;
    /*|./*|../*|~*) dest="$1"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
dest="${dest/#\~/$HOME}"
mkdir -p "$dest"
dest="$(cd "$dest" && pwd)"
backup=""
archive() {
  local entry="$1"
  [[ -e "$entry" || -L "$entry" ]] || return 0
  if [[ -z "$backup" ]]; then
    mkdir -p "$(dirname "$dest")/skill-backups"
    backup="$(mktemp -d "$(dirname "$dest")/skill-backups/app-common.XXXXXX")"
  fi
  mv "$entry" "$backup/$(basename "$entry")"
  echo "Preserved previous skill: $backup/$(basename "$entry")"
}
install_skill() {
  local name="$1" source="$2" link="$dest/$1"
  # Resolve the canonical package-owned data before copying or linking.
  source="$(cd "$source" && pwd -P)"
  if [[ "$link" -ef "$source" ]] && ! $copy; then
    echo "Already linked: $name"
    return
  fi
  if [[ "$dest" == "$source" || "$dest" == "$source/"* || "$link" == "$source" ]]; then
    echo "Refusing to install over source: $source" >&2
    exit 2
  fi
  archive "$link"
  if $copy; then
    mkdir -p "$link"
    cp -RL "$source/." "$link/"
  else
    ln -s "$source" "$link"
  fi
  echo "Installed: $name -> $link"
}
install_skill app-common "$repo_root/agents/skills/app-common"
if $with_dev; then
  install_skill app-common-contributor "$repo_root/agents/dev-skills/app-common-contributor"
fi
# Preserve legacy directories, including local edits, outside the discovery directory.
for name in "${legacy[@]}"; do archive "$dest/$name"; done
echo "Done. Guide selection now happens through app-tools guide or the skill's references."
