#!/usr/bin/env bash
set -e

# SSH pre-check: GitHub exits 1 on success, 255 on connection/auth failure.
# Use if/else to capture exit code without triggering set -e on GitHub's non-zero success.
if ssh -T git@github.com 2>/dev/null; then
  _ssh_exit=0
else
  _ssh_exit=$?
fi
if [[ $_ssh_exit -eq 255 ]]; then
  echo "WARNING: SSH auth unavailable. Set up SSH keys, then run: chezmoi-clone-repos"
  exit 0
fi

mkdir -p "$HOME/.agents/repos" "$HOME/.agents/skills" \
         "$HOME/.agents/agents" "$HOME/.agents/commands" \
         "$HOME/.tmux/plugins"

# neovim config fork (skip if already present)
[[ -d "$HOME/.config/nvim" ]] \
  || git clone git@github.com:ronnyf/kickstart.nvim.git "$HOME/.config/nvim"

# TPM
[[ -d "$HOME/.tmux/plugins/tpm" ]] \
  || git clone git@github.com:tmux-plugins/tpm.git "$HOME/.tmux/plugins/tpm"

# superpowers skills
[[ -d "$HOME/.agents/repos/superpowers" ]] \
  || git clone git@github.com:obra/superpowers.git "$HOME/.agents/repos/superpowers"

# agentic skills
[[ -d "$HOME/.agents/repos/agentic" ]] \
  || git clone git@github.com:ronnyf/agentic.git "$HOME/.agents/repos/agentic"

echo "External repos ready."
