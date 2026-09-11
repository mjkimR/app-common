#!/usr/bin/env bash
# Link agent-neutral skills in agents/ into an agent's project or global skill directory.
#   agents/skills/      consumer skills (for developers building apps with app-common) -> always linked
#   agents/dev-skills/  contributor skills (for people developing app-common itself)   -> only with --dev
#
# Usage:
#   ./agents/link-skills.sh                 # Default: Antigravity (.agents/skills)
#   ./agents/link-skills.sh --dev           # Antigravity (.agents/skills) with dev skills
#   ./agents/link-skills.sh claude          # Claude Code (.claude/skills)
#   ./agents/link-skills.sh --dev claude    # Claude Code with dev skills
#   ./agents/link-skills.sh codex           # Codex (.codex/skills)
#   ./agents/link-skills.sh --dev <dir>     # Any directory (relative or absolute)
#
# Relative links are used for in-repo directories so the repository can move.
# Absolute links are used when pointing outside the repo (e.g. ~/.gemini/config/skills).
# Existing non-symlink directories are preserved and reported.
# Dangling symlinks pointing to removed/renamed skills in agents/ are pruned.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

with_dev=false
target_arg=""

for a in "$@"; do
  case "$a" in
    --dev) with_dev=true ;;
    -h|--help)
      sed -n '2,17p' "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      if [ -z "$target_arg" ]; then
        target_arg="$a"
      fi
      ;;
  esac
done

case "${target_arg:-antigravity}" in
  antigravity) target=".agents/skills" ;;
  claude)      target=".claude/skills" ;;
  codex)       target=".codex/skills" ;;
  *)           target="$target_arg" ;;
esac

# Resolve target destination
if [[ "$target" = /* ]]; then
  dest_dir="$target"
  is_external=true
else
  dest_dir="$root/$target"
  is_external=false
fi

mkdir -p "$dest_dir"

sources=(skills)
$with_dev && sources+=(dev-skills)

echo "Linking skills to $dest_dir (sources: ${sources[*]})"

for src in "${sources[@]}"; do
  src_dir="$root/agents/$src"
  [ -d "$src_dir" ] || continue

  for skill in "$src_dir"/*/; do
    [ -d "$skill" ] || continue
    name="$(basename "$skill")"
    link="$dest_dir/$name"

    if $is_external; then
      target_link="$skill"
    else
      # Compute relative path from target directory to skill directory
      depth="$(printf '%s' "$target" | awk -F/ '{print NF}')"
      up=""
      for ((i = 0; i < depth; i++)); do up="../$up"; done
      target_link="${up}agents/$src/$name"
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
