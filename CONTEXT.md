---
metadata:
  reference-process: v1.5.0
---

# CONTEXT

Glossary for the dotfiles repo. Implementation-free — this is a glossary only.

---

## Terms

**stow package**
A top-level directory in the dotfiles repo that contains a `target.stowy` file declaring one or more symlink targets. The unit of deployment in the old stow-based system.

**config-file package**
A stow package whose payload consists entirely of user-authored configuration files (no git submodules). Examples: `zshrc`, `ghostty`, `alacritty`, `wezterm`, `starship`, `fd`, `opencode`.

**submodule package**
A stow package whose payload is or contains a git submodule pointing to an external repo. Examples: `neovim` (kickstart.nvim fork), `skills/superpowers`, `skills/agentic`, `tmux/plugins/*`, `zsh-plugins/*`.

**plugin manager**
A tool that auto-installs upstream plugin code at runtime, without the plugin code being tracked in the dotfiles repo. TPM manages tmux plugins; a zsh plugin manager (e.g. antidote) manages zsh plugins; lazy.nvim manages neovim plugins.

**canonical skills location**
`~/.agents/skills/` — the single source of truth for agent skill files, per the Agent Skills spec. Agent tools that use a different path (Claude Code at `~/.claude/skills`, OpenCode at `~/.config/opencode/skills`) get symlinks pointing here.

**chezmoi source dir**
The git repository that chezmoi manages. Configured to be the existing `~/.dotfiles` repo (not the default `~/.local/share/chezmoi`). chezmoi reads this dir to apply files to the home directory.

**run_once_ script**
A chezmoi script that executes exactly once per machine (tracked by a hash of the script's contents). Used for cloning external repos (neovim, superpowers, agentic).

**OS guard**
A condition at the top of a chezmoi script that detects the current operating system (`darwin` for macOS, `linux` for Linux) and exits early when the script does not apply to that platform. macOS-specific scripts (Homebrew, macOS defaults, xcode-themes) carry Darwin guards; Linux-specific scripts (pacman/yay) carry Linux guards.

**run_onchange_ script**
A chezmoi script that re-executes whenever its content (or an embedded hash) changes. Used for Homebrew bundle installs (re-runs when `Brewfile` changes), pacman/yay installs (re-runs when the package list changes), and macOS defaults.
