# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install/update all package symlinks
python3 dotfiles.py              # interactive TUI
python3 dotfiles.py --dry-run    # preview only
```

## Architecture

GNU Stow-based dotfiles managed by `dotfiles.py` (TUI). Each top-level directory is a stow package containing a `target.stowy` file that declares where its contents should be symlinked.

### Package → Target Mapping

| Package | Stow Target |
|---------|------------|
| `zshrc` | `$HOME` (dot-zshrc, dot-zshrc.alias) |
| `zsh-plugins` | `$HOME/.config/zsh-plugins` |
| `neovim` | `$HOME/.config` (kickstart.nvim fork submodule) |
| `tmux` | `$HOME/.config/tmux` |
| `ghostty` | `$HOME/.config/ghostty` |
| `alacritty` | `$HOME/.config/alacritty` |
| `wezterm` | `$HOME/.config/wezterm` |
| `opencode` | `$HOME/.config` |
| `skills` | `$HOME/.config/opencode/skills` (via `STOWY_DIR=skills/superpowers`, `STOWY_PACKAGE=skills`) |
| `agents` | `$HOME/.config/opencode/agents` (via `STOWY_DIR=skills/superpowers`, `STOWY_PACKAGE=agents`) |
| `starship` | `$HOME/.config` |
| `fd` | `$HOME/.config/fd` |
| `iTerm2` | `$HOME/.config` |
| `xcode-themes` | `$HOME/Library/Developer/Xcode/UserData` |

### How stowy Works

`dotfiles.py` is the primary tool. `stowy.sh` is legacy and no longer used.

1. Scans for top-level directories containing `target.stowy`
2. Parses `target.stowy` to read `STOWY_TARGET=<path>` and optional `STOWY_DIR` / `STOWY_PACKAGE` overrides
3. Creates target directory if missing
4. Runs `stow -d <stow_dir> -t <target> -v <package> --dotfiles --ignore=^target\.stowy$ --ignore=\.DS_Store`

The `--dotfiles` flag means files prefixed with `dot-` become dotfiles at the target (e.g., `dot-zshrc` → `.zshrc`).

#### STOWY_DIR and STOWY_PACKAGE overrides

When a package's content lives inside a nested subdirectory (e.g., a submodule), set `STOWY_DIR` and `STOWY_PACKAGE` in `target.stowy` to redirect stow's `-d` flag and package name. Multiple entries are supported — each `STOWY_TARGET` starts a new block:

```bash
STOWY_TARGET=$HOME/.config/opencode/skills
STOWY_DIR=skills/superpowers
STOWY_PACKAGE=skills

STOWY_TARGET=$HOME/.config/opencode/agents
STOWY_DIR=skills/superpowers
STOWY_PACKAGE=agents
```

Each block produces a separate package in the TUI. Both `STOWY_DIR` and `STOWY_PACKAGE` default to the dotfiles root and the top-level directory name respectively when omitted.

### Submodules

Several packages contain git submodules (see `.gitmodules`):
- `neovim/nvim` — kickstart.nvim fork (`https://github.com/ronnyf/kickstart.nvim.git`)
- `skills/superpowers` — superpowers skills (`https://github.com/ronnyf/superpowers.git`), stowed to `~/.config/opencode/skills/`
- `tmux/plugins/tpm`, `tmux/plugins/tmux` (dracula), `tmux/plugins/tmuxifier`, `tmux/plugins/vim-tmux-navigator`
- `zsh-plugins/fzf-tab`, `zsh-plugins/zsh-autosuggestions`, `zsh-plugins/zsh-syntax-highlighting`

## Shell Environment

`zshrc/dot-zshrc` detects work vs. home via a `$HOME/.iamatwork` flag file:
- **Work mode**: device compute aliases (dc, dcs, dcmake-*), AWS blobby
- **Home mode**: ESP32/IDF development aliases (idfenv, ib, ic, etc.)

Aliases are defined in `zshrc/dot-zshrc.alias`, sourced conditionally.

## Naming Conventions

- Config files: snake_case with appropriate extensions (`.lua`, `.zsh`, `.conf`, `.toml`)
- Stow payload files: `dot-` prefix (e.g., `dot-zshrc`, `dot-p10k.zsh`)

## Important Notes

- Changes here affect the user's live environment once stowed
- `neovim/nvim` is a submodule pointing to a personal kickstart.nvim fork — do not restructure it
- Submodule directories (tmux/plugins, zsh-plugins) are managed upstream; edit only top-level config files
