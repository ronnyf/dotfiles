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
| `opencode` | `$HOME/.config` (stows the `opencode/opencode/` payload — `opencode.json`, `package.json` — into `$HOME/.config/opencode/`) |
| `skills` | Multi-block `target.stowy`; stows the `superpowers` and `agentic` submodules into `$HOME/.config/opencode/{skills,agents,commands}` (see STOWY_DIR section) |
| `starship` | `$HOME/.config` |
| `fd` | `$HOME/.config/fd` |
| `iTerm2` | `$HOME/.config` |
| `xcode-themes` | `$HOME/Library/Developer/Xcode/UserData` |

### How stowy Works

`dotfiles.py` is the **only** supported way to stow. Never invoke `stow` directly, and never hand-create symlinks to emulate a stow result — always run `dotfiles.py`.

1. Scans **every** top-level directory for a `target.stowy` file (so one run processes all packages, and a single `target.stowy` can declare multiple packages)
2. Parses `target.stowy` to read `STOWY_TARGET=<path>` and optional `STOWY_DIR` / `STOWY_PACKAGE` overrides
3. Creates target directory if missing
4. Runs `stow -d <stow_dir> -t <target> -v <package> --dotfiles --no-folding --ignore=^target\.stowy$ --ignore=\.DS_Store`

The `--dotfiles` flag means files prefixed with `dot-` become dotfiles at the target (e.g., `dot-zshrc` → `.zshrc`). `--no-folding` keeps target subdirectories as real directories with per-file symlinks, so multiple packages can merge into the same target dir.

#### STOWY_DIR and STOWY_PACKAGE overrides

When a package's content lives inside a nested subdirectory (e.g., a submodule), set `STOWY_DIR` and `STOWY_PACKAGE` in `target.stowy` to redirect stow's `-d` flag and package name. Multiple entries are supported — each `STOWY_TARGET` starts a new block. The live `skills/target.stowy` merges two submodules into `~/.config/opencode/`:

```bash
STOWY_TARGET=$HOME/.config/opencode/skills    # superpowers skills
STOWY_DIR=skills/superpowers
STOWY_PACKAGE=skills

STOWY_TARGET=$HOME/.config/opencode/skills    # agentic skills (merges into same dir)
STOWY_DIR=skills/agentic
STOWY_PACKAGE=skills

STOWY_TARGET=$HOME/.config/opencode/agents    # agentic agents
STOWY_DIR=skills/agentic
STOWY_PACKAGE=agents

STOWY_TARGET=$HOME/.config/opencode/commands  # agentic commands
STOWY_DIR=skills/agentic
STOWY_PACKAGE=commands
```

Each block produces a separate package in the TUI. Both `STOWY_DIR` and `STOWY_PACKAGE` default to the dotfiles root and the top-level directory name respectively when omitted. Note: agentic — not superpowers — is the source for `agents` and `commands` (superpowers has no `agents` dir).

### Submodules

Several packages contain git submodules (see `.gitmodules`):
- `neovim/nvim` — kickstart.nvim fork (`git@github.com:ronnyf/kickstart.nvim.git`)
- `skills/superpowers` — superpowers skills (`git@github.com:obra/superpowers.git`), stowed to `~/.config/opencode/skills/`
- `skills/agentic` — agentic plugin skills/agents/commands (`git@github.com:ronnyf/agentic.git`), stowed to `~/.config/opencode/{skills,agents,commands}/`
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
