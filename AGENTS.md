# AGENTS.md

Guidance for Claude Code and other agents working in this repository.

## Commands

```bash
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
```

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

```bash
# macOS
brew install chezmoi
git clone https://github.com/ronnyf/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles

# Linux (CachyOS/Arch)
sudo pacman -S chezmoi git
git clone https://github.com/ronnyf/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles
```

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

```bash
# On this machine after editing
chezmoi cd
git add -A && git commit -m "update dotfiles" && git push
exit

# On other machines
chezmoi update --verbose
```
