#!/usr/bin/env bash
set -e

[[ -d "$HOME/.agents/repos/superpowers" && -d "$HOME/.agents/repos/agentic" ]] \
  || { echo "WARNING: repos not cloned yet. Run: chezmoi-clone-repos then sync-skills"; exit 0; }

# Consumer clones are pinned to nothing, so they drift silently. agentic sat 24 commits behind
# for ~5 weeks, shipping a dev-discipline missing rule R3.4 and hiding 9 skills. Warn loudly.
# Submodules matter too: 9 agentic skills are symlinks into third-party/, dangling when uninit.
for repo in superpowers agentic; do
  d="$HOME/.agents/repos/$repo"
  git -C "$d" fetch --quiet origin 2>/dev/null || continue
  behind=$(git -C "$d" rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
  [[ "$behind" -gt 0 ]] \
    && echo "WARNING: $repo is $behind commits behind origin/main — run: git -C $d pull --ff-only"
  if [[ -f "$d/.gitmodules" ]] && git -C "$d" submodule status 2>/dev/null | grep -q '^-'; then
    echo "WARNING: $repo has uninitialized submodules — run: git -C $d submodule update --init --recursive"
  fi
done

shopt -s nullglob
mkdir -p "$HOME/.agents/skills" "$HOME/.agents/agents" "$HOME/.agents/commands"

# skills: superpowers first, agentic second — agentic wins on name collision (intentional)
for repo in superpowers agentic; do
  for dir in "$HOME/.agents/repos/$repo/skills/"/*/; do
    name=$(basename "${dir%/}")
    [[ -d "$HOME/.agents/skills/$name" && ! -L "$HOME/.agents/skills/$name" ]] \
      && { echo "ERROR: real dir at $HOME/.agents/skills/$name"; exit 1; }
    ln -sfn "${dir%/}" "$HOME/.agents/skills/$name"
  done
done

# agentic agents
[[ -d "$HOME/.agents/repos/agentic/agents" ]] \
  || { echo "WARN: agentic/agents dir missing"; }
for f in "$HOME/.agents/repos/agentic/agents/"*.md; do
  ln -sfn "$f" "$HOME/.agents/agents/$(basename "$f")"
done

# agentic commands
[[ -d "$HOME/.agents/repos/agentic/commands" ]] \
  || { echo "WARN: agentic/commands dir missing"; }
for f in "$HOME/.agents/repos/agentic/commands/"*.md; do
  ln -sfn "$f" "$HOME/.agents/commands/$(basename "$f")"
done

_synced=("$HOME/.agents/skills"/*/)
echo "Agent skills synced: ${#_synced[@]} skills"
