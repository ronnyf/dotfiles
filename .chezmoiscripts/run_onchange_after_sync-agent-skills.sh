#!/usr/bin/env bash
set -e

[[ -d "$HOME/.agents/repos/superpowers" && -d "$HOME/.agents/repos/agentic" ]] \
  || { echo "WARNING: repos not cloned yet. Run: chezmoi-clone-repos then sync-skills"; exit 0; }

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
