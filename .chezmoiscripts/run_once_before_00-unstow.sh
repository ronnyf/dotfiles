#!/usr/bin/env bash
# One-time migration: remove stow-created symlinks before chezmoi deploys real files.
# Safe to run on any OS — only unlinks paths that are actual symlinks.

_try_unlink() {
  [[ -L "$1" ]] && unlink "$1" && echo "Unlinked: $1"
}

# zshrc
_try_unlink "$HOME/.zshrc"
_try_unlink "$HOME/.zshrc.alias"

# ~/.config/* symlinks
_try_unlink "$HOME/.config/ghostty/config"
_try_unlink "$HOME/.config/alacritty/alacritty.toml"
_try_unlink "$HOME/.config/wezterm/wezterm.lua"
_try_unlink "$HOME/.config/starship.toml"
_try_unlink "$HOME/.config/fd/ignore"
_try_unlink "$HOME/.config/tmux/tmux.conf"

# opencode config files
for _f in opencode.json package.json package-lock.json tui.json oh-my-opencode-slim.json; do
  _try_unlink "$HOME/.config/opencode/$_f"
done

# opencode skills/agents/commands symlinks
_try_unlink "$HOME/.config/opencode/skills"
_try_unlink "$HOME/.config/opencode/agents"
_try_unlink "$HOME/.config/opencode/commands"

# tmux plugin directories (stow --no-folding creates per-dir symlinks)
for _plugin in tpm tmux tmuxifier vim-tmux-navigator; do
  _try_unlink "$HOME/.config/tmux/plugins/$_plugin"
done

# zsh-plugin directories
for _plugin in fzf-tab zsh-autosuggestions zsh-syntax-highlighting; do
  _try_unlink "$HOME/.config/zsh-plugins/$_plugin"
done
rmdir "$HOME/.config/zsh-plugins" 2>/dev/null || true

# iTerm2 colour schemes
for _f in "$HOME/.config/iTerm2/"*.itermcolors; do
  _try_unlink "$_f"
done

# Xcode themes
_try_unlink "$HOME/Library/Developer/Xcode/UserData/FontAndColorThemes/Batman.xccolortheme"

# neovim (symlink to submodule)
_try_unlink "$HOME/.config/nvim"

echo "Unstow complete."
