# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install/update all package symlinks
./stowy.sh

# Install/update a single package
./stowy.sh <package-name>

# Import unmanaged ~/.config directories into dotfiles
python3 import.py              # interactive
python3 import.py --dry-run    # preview only
python3 import.py --yes        # auto-accept all
```

## Architecture

GNU Stow-based dotfiles with a custom `stowy.sh` wrapper. Each top-level directory is a stow package containing a `target.stowy` file that declares where its contents should be symlinked.

### Package → Target Mapping

| Package | Stow Target |
|---------|------------|
| `zshrc` | `$HOME` (dot-zshrc, dot-zshrc.alias) |
| `zsh` | `$HOME/.config/zsh` |
| `zsh_custom` | `$HOME/.config/zsh_custom` |
| `omz` | `$HOME/.config` (oh-my-zsh submodule) |
| `omz_plugins` | `$HOME/.config/zsh_custom/plugins` |
| `omz_themes` | `$HOME/.config/zsh_custom/themes` |
| `nvim` | `$HOME/.config` (NvChad fork submodule) |
| `tmux` | `$HOME/.config/tmux` |
| `ghostty` | `$HOME/.config/ghostty` |
| `alacritty` | `$HOME/.config/alacritty` |
| `wezterm` | `$HOME/.config/wezterm` |
| `opencode` | `$HOME/.config` |
| `fd` | `$HOME/.config/fd` |
| `iTerm2` | `$HOME/.config` |
| `xcode-themes` | `$HOME/Library/Developer/Xcode/UserData` |

### How stowy.sh Works

1. Scans for directories containing `target.stowy`
2. Sources `target.stowy` to read `STOWY_TARGET=<path>`
3. Creates target directory if missing
4. Runs `stow -t <target> -v <package> --dotfiles --ignore=^target\.stowy$ --ignore=\.DS_Store`

The `--dotfiles` flag means files prefixed with `dot-` become dotfiles at the target (e.g., `dot-zshrc` → `.zshrc`).

### Submodules

Several packages contain git submodules (see `.gitmodules`):
- `omz/oh-my-zsh` — Oh My Zsh framework
- `omz_plugins/zsh-autosuggestions`, `omz_plugins/zsh-syntax-highlighting`
- `omz_themes/powerlevel10k`
- `tmux/plugins/tpm`, `tmux/plugins/tmux` (dracula), `tmux/plugins/tmuxifier`, `tmux/plugins/vim-tmux-navigator`
- `nvim/nvim` — personal NvChad fork (`git@github.com:ronnyf/NvChad.git`, branch: current)

### import.py

Python script that scans `~/.config` for directories that have a matching package in the dotfiles repo (i.e., a `target.stowy` exists) but aren't yet symlinked. Offers interactive import with skip/replace/merge and conflict resolution.

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
- `nvim/nvim` is a submodule pointing to a personal NvChad fork — do not restructure it
- Submodule directories (omz, omz_plugins, omz_themes, tmux/plugins) are managed upstream; edit only top-level config files
