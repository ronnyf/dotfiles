---
version: 1.1.0
spec: docs/specs/2026-06-24-chezmoi-migration-spec.md
spec-version: 1.5.0
metadata:
  reference-process: v1.5.0
---

# Chezmoi Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the `~/.dotfiles` repo from GNU stow + dotfiles.py to chezmoi, enabling
single-command multi-machine sync and bootstrapping.

**Architecture:** Chezmoi is layered on top of the existing `~/.dotfiles` git repo
(configured as the chezmoi source dir). Config files are restructured into chezmoi's
`dot_` prefix layout, OS-guarded bootstrap scripts are added under `.chezmoiscripts/`,
and external repos (neovim fork, superpowers, agentic, TPM) are bootstrapped by a
`run_once_` script rather than managed as git submodules.

**Tech Stack:** chezmoi, bash, Go templates, antidote (zsh plugin manager), TPM (tmux).

## Global Constraints

- chezmoi source dir: `~/.dotfiles` (not the default `~/.local/share/chezmoi`)
- Bootstrap: `brew install chezmoi && git clone <remote> ~/.dotfiles && chezmoi apply`
- All `.chezmoiscripts/` scripts live **flat** in that directory — no subdirs
- OS guards: `[[ "$(uname -s)" == "Darwin" ]] || exit 0` / `"Linux"`
- `run_once_before_install-external-repos.sh` uses `$HOME` (no `.tmpl` suffix)
- Antidote path: loop `/opt/homebrew` then `/usr/local` (no subprocess fork)
- Skill name collision: agentic wins over superpowers (loop order)
- Every task ends with a commit

---

## File Map

**Created:**
- `.chezmoi.toml.tmpl`
- `.chezmoiignore`
- `.chezmoiscripts/run_once_before_00-unstow.sh`
- `.chezmoiscripts/run_once_before_install-external-repos.sh`
- `.chezmoiscripts/run_onchange_before_install-homebrew-bundle.sh.tmpl`
- `.chezmoiscripts/run_onchange_after_set-macos-defaults.sh`
- `.chezmoiscripts/run_onchange_after_disable-macos-animations.sh`
- `.chezmoiscripts/run_onchange_after_init-macos-machine.sh.tmpl`
- `.chezmoiscripts/run_onchange_before_install-packages.sh.tmpl`
- `.chezmoiscripts/run_onchange_after_sync-agent-skills.sh`
- `Brewfile`
- `packages.txt`
- `dot_zshrc` (renamed from `zshrc/dot-zshrc`)
- `dot_zshrc.alias` (renamed + modified)
- `dot_zsh_plugins.txt`
- `dot_config/ghostty/config`
- `dot_config/alacritty/alacritty.toml`
- `dot_config/wezterm/wezterm.lua`
- `dot_config/starship.toml`
- `dot_config/fd/ignore`
- `dot_config/tmux/tmux.conf` (renamed + modified)
- `dot_config/opencode/opencode.json`
- `dot_config/opencode/package.json`
- `dot_config/opencode/tui.json`
- `dot_config/opencode/oh-my-opencode-slim.json`
- `dot_config/iTerm2/` (5 colour scheme files)
- `Library/Developer/Xcode/UserData/FontAndColorThemes/Batman.xccolortheme`
- `dot_claude/symlink_skills.tmpl`
- `dot_config/opencode/symlink_skills.tmpl`
- `dot_config/opencode/symlink_agents.tmpl`
- `dot_config/opencode/symlink_commands.tmpl`

**Deleted (Task 10):**
- `dotfiles.py`, `import.py`, `test_dotfiles.py`, `__pycache__/`
- All `target.stowy` files
- `skills/` directory
- All plugin submodule directories + `.gitmodules` entries

**Modified:**
- `AGENTS.md`
- `dot_zshrc` (antidote block)
- `dot_zshrc.alias` (two new aliases)
- `dot_config/tmux/tmux.conf` (TPM path)

---

### Task 1: Chezmoi initialization

**Files:**
- Create: `.chezmoi.toml.tmpl`
- Create: `.chezmoiignore`

**Interfaces:**
- Produces: chezmoi config template (read by chezmoi on first `apply`); ignore list
  used by every subsequent task

- [ ] **Step 1: Create `.chezmoi.toml.tmpl`**

```
{{- $machineName := promptStringOnce . "machineName" "Machine name" .chezmoi.hostname -}}
sourceDir = "{{ .chezmoi.homeDir }}/.dotfiles"

[data]
    machineName = {{ $machineName | quote }}
```

- [ ] **Step 2: Create `.chezmoiignore`**

```
README.md
AGENTS.md
CONTEXT.md
docs/
Brewfile
packages.txt
dotfiles.py
import.py
test_dotfiles.py
__pycache__/
*.pyc
.gitmodules
# opencode artefacts not tracked by chezmoi
dot_config/opencode/opencode.json.bak
dot_config/opencode/package-lock.json
dot_config/opencode/node_modules
dot_config/opencode/agents
dot_config/opencode/commands
dot_config/opencode/skills
# machine-local shell extras
.zshrc.work
.zshrc.home
.zshrc.claude
{{- if ne .chezmoi.os "darwin" }}
Library/**
.config/iTerm2/**
{{- end }}
```

- [ ] **Step 3: Verify chezmoi can read the source dir**

```bash
chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | head -20
```

Expected: chezmoi processes the template and shows a plan (may show many changes —
that's fine, real files haven't been moved yet). No fatal errors.

- [ ] **Step 4: Commit**

```bash
git add .chezmoi.toml.tmpl .chezmoiignore
git commit -m "feat: add chezmoi configuration and ignore list"
```

---

### Task 2: Unstow migration script

**Files:**
- Create: `.chezmoiscripts/run_once_before_00-unstow.sh`

**Interfaces:**
- Consumes: existing stow-deployed symlinks at known target paths
- Produces: home directory with stow symlinks removed, ready for chezmoi real-file
  deployment; `~/.config/zsh-plugins/` empty directory removed

- [ ] **Step 1: Create `.chezmoiscripts/` directory**

```bash
mkdir -p .chezmoiscripts
```

- [ ] **Step 2: Create `run_once_before_00-unstow.sh`**

```bash
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
```

- [ ] **Step 3: Make executable**

```bash
chmod +x .chezmoiscripts/run_once_before_00-unstow.sh
```

- [ ] **Step 4: Dry-run verify**

```bash
chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | grep unstow
```

Expected: chezmoi shows `run_once_before_00-unstow.sh` in the plan.

- [ ] **Step 5: Commit**

```bash
git add .chezmoiscripts/run_once_before_00-unstow.sh
git commit -m "feat: add one-time unstow migration script"
```

---

### Task 3: Config file restructuring

**Files:**
- Rename: all config files from stow-package layout to chezmoi flat `dot_` layout
- Each stow package directory is dissolved; files move to the repo root or
  `dot_config/` as appropriate

**Interfaces:**
- Consumes: existing stow-package source files
- Produces: chezmoi-format source tree that `chezmoi apply` can deploy to `$HOME`

- [ ] **Step 1: Create target directory structure**

```bash
mkdir -p dot_config/ghostty dot_config/alacritty dot_config/wezterm
mkdir -p dot_config/fd dot_config/tmux dot_config/opencode
mkdir -p dot_config/iTerm2
mkdir -p Library/Developer/Xcode/UserData/FontAndColorThemes
mkdir -p dot_claude
```

- [ ] **Step 2: Move zshrc files**

```bash
git mv zshrc/dot-zshrc dot_zshrc
git mv zshrc/dot-zshrc.alias dot_zshrc.alias
git rm zshrc/target.stowy
rmdir zshrc
```

- [ ] **Step 3: Move terminal config files**

```bash
git mv ghostty/config dot_config/ghostty/config
git rm ghostty/target.stowy
rmdir ghostty

git mv alacritty/alacritty.toml dot_config/alacritty/alacritty.toml
git rm alacritty/target.stowy
rmdir alacritty

git mv wezterm/wezterm.lua dot_config/wezterm/wezterm.lua
git rm wezterm/target.stowy
rmdir wezterm
```

- [ ] **Step 4: Move starship and fd**

```bash
git mv starship/starship.toml dot_config/starship.toml
git rm starship/target.stowy
rmdir starship

git mv fd/ignore dot_config/fd/ignore
git rm fd/target.stowy
rmdir fd
```

- [ ] **Step 5: Move tmux config (not plugins yet)**

```bash
git mv tmux/tmux.conf dot_config/tmux/tmux.conf
git rm tmux/target.stowy
# Leave tmux/plugins/ for submodule removal in Task 10
```

- [ ] **Step 6: Move opencode config files**

```bash
git mv opencode/opencode/opencode.json dot_config/opencode/opencode.json
git mv opencode/opencode/package.json dot_config/opencode/package.json
git mv opencode/opencode/tui.json dot_config/opencode/tui.json
git mv opencode/opencode/oh-my-opencode-slim.json dot_config/opencode/oh-my-opencode-slim.json
git rm opencode/target.stowy
# opencode.json.bak, package-lock.json, node_modules/ stay until Task 11 cleanup
# No target.stowy exists inside opencode/opencode/ (stowy files only at package root)
```

- [ ] **Step 7: Move iTerm2 colour schemes**

```bash
git mv iTerm2/iTerm2/batman_wwdc.itermcolors dot_config/iTerm2/batman_wwdc.itermcolors
git mv iTerm2/iTerm2/catppuccin-frappe.itermcolors dot_config/iTerm2/catppuccin-frappe.itermcolors
git mv iTerm2/iTerm2/catppuccin-latte.itermcolors dot_config/iTerm2/catppuccin-latte.itermcolors
git mv iTerm2/iTerm2/catppuccin-macchiato.itermcolors dot_config/iTerm2/catppuccin-macchiato.itermcolors
git mv iTerm2/iTerm2/catppuccin-mocha.itermcolors dot_config/iTerm2/catppuccin-mocha.itermcolors
git rm iTerm2/target.stowy
rmdir iTerm2/iTerm2 iTerm2
```

- [ ] **Step 8: Move Xcode theme**

```bash
git mv xcode-themes/FontAndColorThemes/Batman.xccolortheme \
  Library/Developer/Xcode/UserData/FontAndColorThemes/Batman.xccolortheme
git rm xcode-themes/target.stowy
rmdir xcode-themes/FontAndColorThemes xcode-themes
```

- [ ] **Step 9: Verify chezmoi sees all tracked files**

```bash
chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | grep -E "^(create|modify)" | sort
```

Expected: all config files listed as `create` (since stow symlinks are not yet replaced,
chezmoi sees the current symlinks and would overwrite them — that is the correct state
before first apply).

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: restructure source files to chezmoi dot_ layout"
```

---

### Task 4: macOS bootstrap scripts

**Files:**
- Create: `Brewfile`
- Create: `.chezmoiscripts/run_onchange_before_install-homebrew-bundle.sh.tmpl`
- Create: `.chezmoiscripts/run_onchange_after_set-macos-defaults.sh`
- Create: `.chezmoiscripts/run_onchange_after_disable-macos-animations.sh`
- Create: `.chezmoiscripts/run_onchange_after_init-macos-machine.sh.tmpl`

**Interfaces:**
- Consumes: `Brewfile` (sha256 embedded in brew-bundle script), `machineName` template
  variable (in init script)
- Produces: Homebrew packages installed; macOS system defaults set; hostname set

- [ ] **Step 1: Create `Brewfile`**

```ruby
# Core tools
brew "chezmoi"
brew "antidote"
brew "fzf"
brew "fd"
brew "bat"
brew "ripgrep"
brew "starship"
brew "zoxide"
brew "fnm"
brew "pyenv"
brew "uv"
brew "tmux"
brew "neovim"
brew "git"
brew "openssh"

# Add additional formulae and casks as needed:
# cask "ghostty"
# cask "alacritty"
# cask "wezterm"
```

- [ ] **Step 2: Create brew bundle script**

```bash
cat > .chezmoiscripts/run_onchange_before_install-homebrew-bundle.sh.tmpl << 'SCRIPT'
#!/usr/bin/env bash
# Brewfile checksum: {{ include "Brewfile" | sha256sum }}
[[ "$(uname -s)" == "Darwin" ]] || exit 0
set -e

# Locate Homebrew
if [[ -x /opt/homebrew/bin/brew ]]; then
  brew_bin=/opt/homebrew/bin/brew
elif [[ -x /usr/local/bin/brew ]]; then
  brew_bin=/usr/local/bin/brew
else
  echo "ERROR: Homebrew not found" >&2; exit 1
fi

brewfile="{{ joinPath .chezmoi.sourceDir "Brewfile" }}"
"$brew_bin" bundle check --no-upgrade --file "$brewfile" >/dev/null 2>&1 \
  || "$brew_bin" bundle install --no-upgrade --file "$brewfile"
SCRIPT
chmod +x .chezmoiscripts/run_onchange_before_install-homebrew-bundle.sh.tmpl
```

- [ ] **Step 3: Create macOS defaults script**

This script sets sensible macOS defaults. Customise the `defaults write` calls to match
personal preferences. A minimal starting set:

```bash
cat > .chezmoiscripts/run_onchange_after_set-macos-defaults.sh << 'SCRIPT'
#!/usr/bin/env bash
[[ "$(uname -s)" == "Darwin" ]] || exit 0
set -e

# Keyboard: fast key repeat
defaults write NSGlobalDomain KeyRepeat -int 2
defaults write NSGlobalDomain InitialKeyRepeat -int 15

# Finder: show extensions, path bar, status bar
defaults write com.apple.finder ShowStatusBar -bool true
defaults write com.apple.finder ShowPathbar -bool true
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Dock: auto-hide, remove delay
defaults write com.apple.dock autohide -bool true
defaults write com.apple.dock autohide-delay -float 0

# Screenshots: save to ~/Desktop
defaults write com.apple.screencapture location -string "${HOME}/Desktop"

killall Finder Dock 2>/dev/null || true
SCRIPT
chmod +x .chezmoiscripts/run_onchange_after_set-macos-defaults.sh
```

- [ ] **Step 4: Create UI animations script**

```bash
cat > .chezmoiscripts/run_onchange_after_disable-macos-animations.sh << 'SCRIPT'
#!/usr/bin/env bash
[[ "$(uname -s)" == "Darwin" ]] || exit 0
set -e
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
defaults write com.apple.dock expose-animation-duration -float 0.1
defaults write com.apple.dock autohide-time-modifier -float 0
SCRIPT
chmod +x .chezmoiscripts/run_onchange_after_disable-macos-animations.sh
```

- [ ] **Step 5: Create machine init script**

```bash
cat > .chezmoiscripts/run_onchange_after_init-macos-machine.sh.tmpl << 'SCRIPT'
#!/usr/bin/env bash
[[ "$(uname -s)" == "Darwin" ]] || exit 0
set -e
# Set hostname from chezmoi machineName
sudo scutil --set ComputerName {{ .machineName | quote }}
sudo scutil --set HostName {{ .machineName | quote }}
sudo scutil --set LocalHostName {{ .machineName | quote }}
SCRIPT
chmod +x .chezmoiscripts/run_onchange_after_init-macos-machine.sh.tmpl
```

- [ ] **Step 6: Verify scripts are discovered by chezmoi**

```bash
chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | grep "run_onchange"
```

Expected: all four macOS scripts appear in the plan.

- [ ] **Step 7: Commit**

```bash
git add Brewfile .chezmoiscripts/run_onchange_*.sh .chezmoiscripts/run_onchange_*.sh.tmpl
git commit -m "feat: add macOS bootstrap scripts and Brewfile"
```

---

### Task 5: Linux bootstrap scripts

**Files:**
- Create: `packages.txt`
- Create: `.chezmoiscripts/run_onchange_before_install-packages.sh.tmpl`

**Interfaces:**
- Consumes: `packages.txt` (sha256 embedded in script)
- Produces: pacman/yay packages installed on Arch/CachyOS

- [ ] **Step 1: Create `packages.txt`**

```
# Arch/CachyOS package list
chezmoi
antidote
fzf
fd
bat
ripgrep
starship
zoxide
fnm
pyenv
uv
tmux
neovim
git
openssh
```

- [ ] **Step 2: Create pacman/yay install script**

```bash
cat > .chezmoiscripts/run_onchange_before_install-packages.sh.tmpl << 'SCRIPT'
#!/usr/bin/env bash
# packages.txt checksum: {{ include "packages.txt" | sha256sum }}
[[ "$(uname -s)" == "Linux" ]] || exit 0
set -e

if ! command -v yay >/dev/null 2>&1; then
  echo "ERROR: yay not found. On vanilla Arch, install yay from the AUR first:"
  echo "  sudo pacman -S --needed git base-devel"
  echo "  git clone https://aur.archlinux.org/yay.git /tmp/yay && cd /tmp/yay && makepkg -si"
  exit 1
fi

pkglist="{{ joinPath .chezmoi.sourceDir "packages.txt" }}"
# Portable loop (bash 3.2 safe — no mapfile/readarray)
pkgs=()
while IFS= read -r line; do
  [[ "$line" =~ ^#|^$ ]] || pkgs+=("$line")
done < "$pkglist"
yay -S --needed --noconfirm "${pkgs[@]}"
SCRIPT
chmod +x .chezmoiscripts/run_onchange_before_install-packages.sh.tmpl
```

- [ ] **Step 3: Verify script is discovered by chezmoi**

```bash
chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | grep install-packages
```

Expected: `run_onchange_before_install-packages.sh.tmpl` appears in plan.

- [ ] **Step 4: Commit**

```bash
git add packages.txt .chezmoiscripts/run_onchange_before_install-packages.sh.tmpl
git commit -m "feat: add Linux bootstrap scripts and packages.txt"
```

---

### Task 6: External repo clone script

**Files:**
- Create: `.chezmoiscripts/run_once_before_install-external-repos.sh`

**Interfaces:**
- Produces: `~/.config/nvim/`, `~/.tmux/plugins/tpm/`, `~/.agents/repos/superpowers/`,
  `~/.agents/repos/agentic/` cloned on first apply (or skipped with warning if SSH
  unavailable)

- [ ] **Step 1: Create the clone script**

```bash
cat > .chezmoiscripts/run_once_before_install-external-repos.sh << 'SCRIPT'
#!/usr/bin/env bash
set -e

# SSH pre-check: GitHub exits 1 on success, 255 on connection/auth failure
ssh -T git@github.com 2>/dev/null; _ssh_exit=$?
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
SCRIPT
chmod +x .chezmoiscripts/run_once_before_install-external-repos.sh
```

- [ ] **Step 2: Verify chezmoi discovers it**

```bash
chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | grep install-external
```

Expected: `run_once_before_install-external-repos.sh` in plan.

- [ ] **Step 3: Commit**

```bash
git add .chezmoiscripts/run_once_before_install-external-repos.sh
git commit -m "feat: add external repo clone script (neovim, TPM, superpowers, agentic)"
```

---

### Task 7: Agent skills fan-out

**Files:**
- Create: `.chezmoiscripts/run_onchange_after_sync-agent-skills.sh`
- Create: `dot_claude/symlink_skills.tmpl`
- Create: `dot_config/opencode/symlink_skills.tmpl`
- Create: `dot_config/opencode/symlink_agents.tmpl`
- Create: `dot_config/opencode/symlink_commands.tmpl`

**Interfaces:**
- Consumes: `~/.agents/repos/superpowers/` and `~/.agents/repos/agentic/` (from Task 6)
- Produces:
  - `~/.agents/skills/<skill-name>` symlinks → repo entries (flat, one per skill)
  - `~/.agents/agents/*.md` symlinks → agentic/agents/
  - `~/.agents/commands/*.md` symlinks → agentic/commands/
  - `~/.claude/skills` → `~/.agents/skills`
  - `~/.config/opencode/skills` → `~/.agents/skills`
  - `~/.config/opencode/agents` → `~/.agents/agents`
  - `~/.config/opencode/commands` → `~/.agents/commands`

- [ ] **Step 1: Create sync script**

```bash
cat > .chezmoiscripts/run_onchange_after_sync-agent-skills.sh << 'SCRIPT'
#!/usr/bin/env bash
set -e

[[ -d "$HOME/.agents/repos/superpowers" && -d "$HOME/.agents/repos/agentic" ]] \
  || { echo "ERROR: repos not cloned. Run: chezmoi-clone-repos"; exit 1; }

shopt -s nullglob
mkdir -p "$HOME/.agents/skills" "$HOME/.agents/agents" "$HOME/.agents/commands"

# superpowers skills (runs first; agentic overrides conflicts)
for dir in "$HOME/.agents/repos/superpowers/skills/"/*/; do
  name=$(basename "${dir%/}")
  [[ -d "$HOME/.agents/skills/$name" && ! -L "$HOME/.agents/skills/$name" ]] \
    && { echo "ERROR: real dir at $HOME/.agents/skills/$name"; exit 1; }
  ln -sfn "${dir%/}" "$HOME/.agents/skills/$name"
done

# agentic skills (wins over superpowers on name collision — intentional)
for dir in "$HOME/.agents/repos/agentic/skills/"/*/; do
  name=$(basename "${dir%/}")
  [[ -d "$HOME/.agents/skills/$name" && ! -L "$HOME/.agents/skills/$name" ]] \
    && { echo "ERROR: real dir at $HOME/.agents/skills/$name"; exit 1; }
  ln -sfn "${dir%/}" "$HOME/.agents/skills/$name"
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

echo "Agent skills synced: $(ls "$HOME/.agents/skills" | wc -l | tr -d ' ') skills"
SCRIPT
chmod +x .chezmoiscripts/run_onchange_after_sync-agent-skills.sh
```

- [ ] **Step 2: Create chezmoi symlinks for agent tools**

```bash
mkdir -p dot_claude

# Claude Code: ~/.claude/skills -> ~/.agents/skills
echo '{{ .chezmoi.homeDir }}/.agents/skills' > dot_claude/symlink_skills.tmpl

# OpenCode: ~/.config/opencode/{skills,agents,commands}
echo '{{ .chezmoi.homeDir }}/.agents/skills' > dot_config/opencode/symlink_skills.tmpl
echo '{{ .chezmoi.homeDir }}/.agents/agents'  > dot_config/opencode/symlink_agents.tmpl
echo '{{ .chezmoi.homeDir }}/.agents/commands' > dot_config/opencode/symlink_commands.tmpl
```

- [ ] **Step 3: Verify symlink sources are correct**

```bash
cat dot_claude/symlink_skills.tmpl
# Expected: {{ .chezmoi.homeDir }}/.agents/skills

chezmoi apply --source ~/.dotfiles --dry-run 2>&1 | grep -E "(skills|agents|commands)"
```

Expected: chezmoi shows symlink creation entries for each of the four paths.

- [ ] **Step 4: Commit**

```bash
git add .chezmoiscripts/run_onchange_after_sync-agent-skills.sh \
        dot_claude/symlink_skills.tmpl \
        dot_config/opencode/symlink_skills.tmpl \
        dot_config/opencode/symlink_agents.tmpl \
        dot_config/opencode/symlink_commands.tmpl
git commit -m "feat: add agent skills fan-out script and tool symlinks"
```

---

### Task 8: Antidote zsh plugin migration

**Files:**
- Modify: `dot_zshrc` (replace three `source` lines + add tmuxifier path update)
- Create: `dot_zsh_plugins.txt`
- Modify: `dot_zshrc.alias` (add two new aliases)

**Interfaces:**
- Consumes: antidote installed at `/opt/homebrew/opt/antidote/…` (macOS) or
  `/usr/share/zsh/plugins/antidote/…` (Linux)
- Produces: zsh autosuggestions, syntax-highlighting, and fzf-tab loaded via antidote;
  `sync-skills` and `chezmoi-clone-repos` aliases available

- [ ] **Step 1: Create `dot_zsh_plugins.txt`**

```
zsh-users/zsh-autosuggestions
zsh-users/zsh-syntax-highlighting
Aloxaf/fzf-tab
```

- [ ] **Step 2: Update `dot_zshrc` — two independent find-and-replace edits**

**Edit A — replace the three plugin source lines with the antidote block.**

Find this exact block (lines 61–63 in the original file):
```zsh
source $HOME/.config/zsh-plugins/fzf-tab/fzf-tab.plugin.zsh
source $HOME/.config/zsh-plugins/zsh-autosuggestions/zsh-autosuggestions.plugin.zsh
source $HOME/.config/zsh-plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
```

Replace with:
```zsh
# Antidote plugin manager
if [[ "$OSTYPE" == "darwin"* ]]; then
    for _ap in /opt/homebrew /usr/local; do
        [[ -f "$_ap/opt/antidote/share/antidote/antidote.zsh" ]] && {
            source "$_ap/opt/antidote/share/antidote/antidote.zsh"; break
        }
    done
else
    [[ -f /usr/share/zsh/plugins/antidote/antidote.zsh ]] \
        && source /usr/share/zsh/plugins/antidote/antidote.zsh
fi
antidote load
```

**Edit B — replace the tmuxifier source line (do this as a separate find-and-replace, not by line number, since Edit A shifts all following line numbers).**

Find this exact line:
```zsh
source <(~/.config/tmux/plugins/tmuxifier/bin/tmuxifier init -)
```

Replace with:
```zsh
source <(~/.tmux/plugins/tmuxifier/bin/tmuxifier init -)
```

- [ ] **Step 3: Add aliases to `dot_zshrc.alias`**

Append to `dot_zshrc.alias`:
```zsh
alias sync-skills='bash ~/.dotfiles/.chezmoiscripts/run_onchange_after_sync-agent-skills.sh'
alias chezmoi-clone-repos='bash ~/.dotfiles/.chezmoiscripts/run_once_before_install-external-repos.sh'
```

- [ ] **Step 4: Verify antidote path exists on this machine**

```bash
ls /opt/homebrew/opt/antidote/share/antidote/antidote.zsh
```

Expected: file exists (confirms antidote is installed via brew).

- [ ] **Step 5: Commit**

```bash
git add dot_zshrc dot_zshrc.alias dot_zsh_plugins.txt
git commit -m "feat: migrate zsh plugins to antidote, add sync-skills alias"
```

---

### Task 9: Tmux config update

**Files:**
- Modify: `dot_config/tmux/tmux.conf` (update TPM `run` line only)

**Interfaces:**
- Consumes: TPM cloned to `~/.tmux/plugins/tpm/` (from Task 6)
- Produces: tmux loads plugins from `~/.tmux/plugins/tpm/tpm`

- [ ] **Step 1: Update `dot_config/tmux/tmux.conf` TPM run line**

Find line 32 of `dot_config/tmux/tmux.conf`:
```tmux
run '$HOME/.config/tmux/plugins/tpm/tpm'
```

Replace with:
```tmux
run '~/.tmux/plugins/tpm/tpm'
```

The `bind r source-file ~/.config/tmux/tmux.conf` reload binding on line 2 remains
unchanged — the config file is still deployed to `~/.config/tmux/tmux.conf` by chezmoi.
Do NOT change the reload binding.

- [ ] **Step 2: Verify the change**

```bash
grep "run '" dot_config/tmux/tmux.conf
```

Expected output:
```
run '~/.tmux/plugins/tpm/tpm'
```

- [ ] **Step 3: Commit**

```bash
git add dot_config/tmux/tmux.conf
git commit -m "feat: update tmux.conf to use TPM default install path"
```

---

### Task 10: End-to-end first apply

**Interfaces:**
- Consumes: all prior tasks (Tasks 1–9 complete)
- Produces: live home directory running under chezmoi management; no stow symlinks remain

This task is the first real apply on an existing machine. It runs the migration scripts
and deploys all tracked files as real copies.

- [ ] **Step 1: Review the full chezmoi diff before applying**

```bash
chezmoi diff --source ~/.dotfiles
```

Review carefully. Expected:
- Removals of stow symlinks (shown as modifications because chezmoi sees a symlink
  where it expects a regular file)
- New files in `~/.agents/`, `~/.claude/skills`, `~/.config/opencode/{skills,agents,commands}`
- The `run_once_before_00-unstow.sh` will run first (removes symlinks), then files deploy

- [ ] **Step 2: Apply with verbose output**

```bash
chezmoi apply --source ~/.dotfiles --verbose
```

Watch for:
- `run_once_before_00-unstow.sh` running and printing `Unlinked: ...` for each symlink
- File deployments completing without errors
- `run_once_before_install-external-repos.sh` running (SSH check, then cloning)
- `run_onchange_after_sync-agent-skills.sh` running and printing skills count

If `run_once_before_install-external-repos.sh` reports SSH unavailable, run
`chezmoi-clone-repos` after SSH keys are configured.

- [ ] **Step 3: Verify deployed files are real files (not symlinks)**

```bash
ls -la ~/.zshrc ~/.config/ghostty/config ~/.config/starship.toml ~/.zsh_plugins.txt ~/.zshrc.alias
```

Expected: regular files (`-rw-r--r--`), not symlinks (`l`).

- [ ] **Step 3b: Verify chezmoi config was written with sourceDir**

```bash
cat ~/.config/chezmoi/chezmoi.toml
```

Expected: file contains `sourceDir = "/Users/<you>/.dotfiles"`. If absent or pointing
to `~/.local/share/chezmoi`, subsequent `chezmoi apply` calls (without `--source`) will
silently target the wrong directory.

- [ ] **Step 4: Verify agent skills**

```bash
ls ~/.agents/skills | head -5
ls -la ~/.claude/skills
ls -la ~/.config/opencode/skills
```

Expected: `~/.claude/skills` and `~/.config/opencode/skills` are symlinks pointing to
`~/.agents/skills`; `~/.agents/skills/` contains skill directories.

- [ ] **Step 5: Open a new shell and verify antidote loads**

```bash
zsh -i -c "which antidote && antidote list"
```

Expected: antidote is found; plugin list shows the three plugins.

- [ ] **Step 6: Verify tmux (if tmux is running)**

```bash
# Start a new tmux session (or in existing session press Ctrl+S then I to install plugins)
ls ~/.tmux/plugins/
```

Expected: `tpm/`, `tmux/` (dracula), `tmuxifier/`, `vim-tmux-navigator/` appear after
TPM installs them on first start.

- [ ] **Step 7: Commit**

```bash
# No source files change in this task — it's a verification task.
# If any corrections were needed in prior tasks, commit those separately.
echo "First apply complete."
```

---

### Task 11: Stow tooling retirement

**Files:**
- Delete: `dotfiles.py`, `import.py`, `test_dotfiles.py`, `__pycache__/`
- Delete: all `target.stowy` files not already removed
- Remove: git submodule entries for all plugin submodules and `skills/`
- Delete: `skills/` directory, `tmux/plugins/`, `zsh-plugins/`, `neovim/nvim`,
  `opencode/opencode/` leftover files
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: verified working chezmoi setup (Task 10)
- Produces: clean repo with only chezmoi artifacts; no stow tooling

- [ ] **Step 1: Remove stow tooling scripts**

```bash
git rm dotfiles.py import.py test_dotfiles.py
git rm -rf __pycache__/
```

- [ ] **Step 2: Remove remaining `target.stowy` files**

```bash
git rm opencode/opencode/target.stowy 2>/dev/null || true
find . -name "target.stowy" -exec git rm {} \; 2>/dev/null || true
```

- [ ] **Step 3: Remove all submodules**

First verify the exact submodule paths declared in `.gitmodules`:
```bash
git config --file .gitmodules --get-regexp path
```

Then for each submodule, the removal sequence is:
```bash
# tmux plugins (verify names match .gitmodules output above)
git submodule deinit tmux/plugins/tpm tmux/plugins/tmux tmux/plugins/tmuxifier tmux/plugins/vim-tmux-navigator
git rm tmux/plugins/tpm tmux/plugins/tmux tmux/plugins/tmuxifier tmux/plugins/vim-tmux-navigator
rm -rf .git/modules/tmux/plugins/tpm .git/modules/tmux/plugins/tmux \
       .git/modules/tmux/plugins/tmuxifier .git/modules/tmux/plugins/vim-tmux-navigator

# neovim
git submodule deinit neovim/nvim
git rm neovim/nvim
rm -rf .git/modules/neovim/nvim

# zsh-plugins
git submodule deinit zsh-plugins/fzf-tab zsh-plugins/zsh-autosuggestions zsh-plugins/zsh-syntax-highlighting
git rm zsh-plugins/fzf-tab zsh-plugins/zsh-autosuggestions zsh-plugins/zsh-syntax-highlighting
rm -rf .git/modules/zsh-plugins

# skills
git submodule deinit skills/agentic skills/superpowers
git rm skills/agentic skills/superpowers
rm -rf .git/modules/skills
```

- [ ] **Step 4: Delete empty package directories**

```bash
rm -rf neovim/ tmux/plugins/ zsh-plugins/ skills/
# Clean up any remaining opencode leftovers (node_modules, bak, lock)
rm -rf opencode/opencode/node_modules opencode/opencode/opencode.json.bak \
       opencode/opencode/package-lock.json opencode/opencode/agents \
       opencode/opencode/commands opencode/opencode/skills
rmdir opencode/opencode opencode 2>/dev/null || true
```

- [ ] **Step 5: Delete remaining empty stow package dirs**

```bash
for d in tmux neovim zsh-plugins; do
  rmdir "$d" 2>/dev/null || true
done
```

- [ ] **Step 6: Update `AGENTS.md`**

Replace the entire content of `AGENTS.md` with the new chezmoi-based documentation:

```markdown
# AGENTS.md

Guidance for Claude Code and other agents working in this repository.

## Commands

\```bash
# Apply dotfiles to $HOME
chezmoi apply

# Pull latest and apply
chezmoi update --verbose

# Preview changes before applying
chezmoi diff

# Edit a tracked file and apply
chezmoi edit --apply ~/.zshrc

# Re-add a file after editing it in-place
chezmoi add ~/.zshrc

# Re-sync agent skills after git pull in a skills repo
sync-skills

# Manually clone external repos (if SSH was unavailable at bootstrap)
chezmoi-clone-repos
\```

## Architecture

Chezmoi-managed dotfiles. Source dir: `~/.dotfiles` (this repo).
Chezmoi copies tracked files to `$HOME` as real files (no symlinks for config).

### Source layout

| Source path | Deployed to | OS |
|---|---|---|
| `dot_zshrc` | `~/.zshrc` | all |
| `dot_zshrc.alias` | `~/.zshrc.alias` | all |
| `dot_zsh_plugins.txt` | `~/.zsh_plugins.txt` | all |
| `dot_config/` | `~/.config/` | all (some entries macOS-only) |
| `Library/` | `~/Library/` | macOS only |
| `dot_claude/symlink_skills.tmpl` | `~/.claude/skills` → `~/.agents/skills` | all |

### Bootstrap (new machine)

\```bash
# macOS
brew install chezmoi
git clone https://github.com/<user>/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles

# Linux (CachyOS/Arch)
sudo pacman -S chezmoi git
git clone https://github.com/<user>/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles
\```

### Scripts (in `.chezmoiscripts/`)

All scripts live flat in `.chezmoiscripts/`; subdirectories are not scanned.

| Script | When | What |
|---|---|---|
| `run_once_before_00-unstow.sh` | Once | Remove stow symlinks (migration) |
| `run_once_before_install-external-repos.sh` | Once | Clone neovim, TPM, superpowers, agentic |
| `run_onchange_before_install-homebrew-bundle.sh.tmpl` | Brewfile changes | `brew bundle install` |
| `run_onchange_before_install-packages.sh.tmpl` | packages.txt changes | `yay -S` |
| `run_onchange_after_sync-agent-skills.sh` | Script changes / manual | Create `~/.agents/` symlinks |
| macOS defaults scripts | Script changes | `defaults write` calls |

### Agent skills

Canonical location: `~/.agents/skills/`. Both Claude Code (`~/.claude/skills`) and
OpenCode (`~/.config/opencode/{skills,agents,commands}`) are symlinked there.

Skills come from two external repos (cloned by `run_once_before_install-external-repos.sh`):
- `~/.agents/repos/superpowers/` — upstream skills
- `~/.agents/repos/agentic/` — personal fork (wins on name collision)

After `git pull` in either repo, run `sync-skills` to update symlinks.

### Day-to-day sync

\```bash
# On this machine after editing
chezmoi cd
git add -A && git commit -m "update dotfiles" && git push
exit

# On other machines
chezmoi update --verbose
\```
```

- [ ] **Step 7: Final verification**

```bash
# No stow artifacts remain
find . -name "target.stowy" | wc -l   # Expected: 0
find . -name "dotfiles.py" | wc -l    # Expected: 0

# chezmoi still works
chezmoi diff --source ~/.dotfiles     # Expected: no changes (clean state)

# git status is clean
git status
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: retire stow tooling, update AGENTS.md for chezmoi workflow"
```

---

## Front-load Refinement Log

Skipped — non-Swift artifact (shell scripts, chezmoi templates, config files).
Per reference-process v1.5.0 §Phase-4, the front-load loop applies to Swift artifacts only.

---

## Per-section Review Log

Three parallel reviewer agents reviewed Tasks 1–3, Tasks 4–7, and Tasks 8–11 against
the spec (2026-06-24). All findings resolved before plan v1.1.0.

| Task group | Reviewer findings | Disposition |
|---|---|---|
| Tasks 1–3 | C: `.chezmoiignore` missing `/**` globs (Library, .config/iTerm2); missing entries (opencode.json.bak, machine-local zshrc variants, opencode subdirs); `sourceDir` must use `{{ .chezmoi.homeDir }}`, not bare tilde; opencode/opencode/ cleanup cross-reference | Fixed in v1.1.0; user approved 2026-06-24 |
| Tasks 4–7 | I: `mapfile` bash 4+ only — replaced with portable `while read` loop (approach choice; no other approach conflicts) | Fixed in v1.1.0; user approved 2026-06-24 |
| Tasks 8–11 | C: zshrc line number drift after 3→10 line replacement — switched to verbatim find-and-replace; AGENTS.md bootstrap missing `--source ~/.dotfiles`; Task 9 description incorrectly said "reload binding" was changing | Fixed in v1.1.0; user approved 2026-06-24 |
| Tasks 8–11 | I: Task 10 missing `chezmoi.toml` and `~/.zsh_plugins.txt` verification steps; submodule name verification step added to Task 11 | Fixed in v1.1.0; user approved 2026-06-24 |

All reviewer findings were unambiguous bug corrections or clear portability fixes.
No author-reviewer design conflicts arose. User confirmed approval of all v1.1.0 changes
on 2026-06-24.
