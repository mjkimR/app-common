#!/usr/bin/env bash
# Link app-common's agent-neutral skills into this checkout's agent skill directory.
#   agents/skills/      consumer skills, also published to other projects through apm.yml -> always linked
#   agents/dev-skills/  contributor skills (for people changing app-common itself)        -> only with --dev
#
#   ./agents/link-skills.sh                 # .agents/skills/ (Codex, Antigravity, Cursor, Gemini)
#   ./agents/link-skills.sh --dev           # consumer + contributor skills
#   ./agents/link-skills.sh claude          # .claude/skills/
#   ./agents/link-skills.sh --dev <dir>     # any directory, relative to the repo root
#
# Consumer projects install skills with APM instead (see agents/README.md).
# Links are relative so the repo can move. Existing real directories are left alone and reported.
# Dangling links into agents/ (a skill that was removed or renamed) are pruned.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

with_dev=false
target_arg=""
for a in "$@"; do
  case "$a" in
    --dev) with_dev=true ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) target_arg="$a" ;;
  esac
done
case "${target_arg:-agents}" in
  agents|antigravity|codex) target=".agents/skills" ;;
  claude) target=".claude/skills" ;;
  *) target="$target_arg" ;;
esac

mkdir -p "$root/$target"
depth="$(printf '%s' "$target" | awk -F/ '{print NF}')"
up=""; for ((i = 0; i < depth; i++)); do up="../$up"; done

sources=(skills)
$with_dev && sources+=(dev-skills)

for src in "${sources[@]}"; do
  for skill in "$root"/agents/$src/*/; do
    [ -f "$skill/SKILL.md" ] || continue
    name="$(basename "$skill")"
    link="$root/$target/$name"
    if [ -L "$link" ]; then
      ln -sfn "${up}agents/$src/$name" "$link"
      echo "relinked  $target/$name"
    elif [ -e "$link" ]; then
      echo "skipped   $target/$name exists and is not a link"
    else
      ln -s "${up}agents/$src/$name" "$link"
      echo "linked    $target/$name"
    fi
  done
done

# Prune links into this repo's skill sources whose SKILL.md no longer exists.
for link in "$root/$target"/*; do
  [ -L "$link" ] || continue
  case "$(readlink "$link")" in *agents/skills/*|*agents/dev-skills/*) ;; *) continue ;; esac
  if [ ! -f "$link/SKILL.md" ]; then
    rm "$link"
    echo "pruned    $target/$(basename "$link")"
  fi
done
