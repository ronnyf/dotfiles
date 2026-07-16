# dotfiles

Personal dotfiles managed by [chezmoi](https://chezmoi.io).  
Source lives at `~/.dotfiles`; chezmoi deploys real files to `$HOME` (no symlinks).

---

## First-time setup

### macOS (work or home)

```bash
# 1. Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install chezmoi
brew install chezmoi

# 3. Clone this repo and apply
git clone git@github.com:ronnyf/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles
```

On first apply chezmoi will ask: **Machine name?** — enter something short like `work-mbp`, `home-air`, or `mini`. This sets the hostname via `scutil`.

After apply, open a new tmux session and press **`Ctrl-S I`** (prefix + I) once to let TPM install the tmux plugins.

### CachyOS / Arch Linux (home)

```bash
# chezmoi and git are usually pre-installed on CachyOS; if not:
sudo pacman -S chezmoi git

git clone git@github.com:ronnyf/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles
```

> **If SSH isn't set up yet on a fresh machine:** the clone script will print a warning and skip cloning the external repos (neovim, superpowers, agentic). Set up your SSH key, then run `chezmoi-clone-repos` to finish.

---

## Work vs. home mode

The shell detects which context you're in via a flag file:

```bash
# Switch to work mode
touch ~/.iamatwork

# Switch to home mode
rm ~/.iamatwork
```

| Mode | What you get |
|---|---|
| Work (`~/.iamatwork` exists) | `dc`, `dcs`, `dcmake-*` device compute aliases; AWS blobby |
| Home (no flag) | ESP32/IDF aliases (`idfenv`, `ib`, `ic`, etc.) |

Machine-local extras can go in `~/.zshrc.work` or `~/.zshrc.home` — these are sourced automatically but not tracked in this repo.

---

## Day-to-day

### Edit a config file

```bash
# Edit in the source dir and apply in one step
chezmoi edit --apply ~/.zshrc

# Or edit the live file, then pull the change back into the source
chezmoi add ~/.zshrc
```

### Sync to other machines

```bash
# On the machine where you made changes
chezmoi cd
git add -A
git commit -m "update dotfiles"
git push
exit

# On every other machine
chezmoi update --verbose
```

`chezmoi update` = `git pull` + `chezmoi apply` in one command.

### Add a new file to tracking

```bash
chezmoi add ~/.config/sometool/config
```

chezmoi copies the file into `~/.dotfiles` with the correct `dot_` prefix and nesting.

### Preview what an apply would change

```bash
chezmoi diff
```

---

## Packages

### macOS — Brewfile

`Brewfile` at the repo root lists all Homebrew formulae. Edit it, then run:

```bash
chezmoi apply   # re-runs brew bundle automatically when Brewfile changes
```

Or check manually:

```bash
brew bundle check --no-upgrade --file "$(chezmoi source-path)/Brewfile"
brew bundle install --no-upgrade --file "$(chezmoi source-path)/Brewfile"
```

### CachyOS / Arch — packages.txt

`packages.txt` at the repo root lists pacman/paru packages. Edit it, then run:

```bash
chezmoi apply   # re-runs paru automatically when packages.txt changes
```

---

## Agent skills

Skills from the `superpowers` and `agentic` repos live at `~/.agents/skills/`.  
Both Claude Code (`~/.claude/skills`) and OpenCode (`~/.config/opencode/skills`) symlink there.

### Update skills

```bash
cd ~/.agents/repos/agentic && git pull && sync-skills
cd ~/.agents/repos/superpowers && git pull && sync-skills
```

`sync-skills` re-creates the per-skill symlinks in `~/.agents/skills/` after any repo update.

---

## Scripts reference

All scripts in `.chezmoiscripts/` run automatically on `chezmoi apply` when triggered.

| Script | Trigger | What it does |
|---|---|---|
| `run_once_before_00-unstow.sh` | Once, first apply | Removes old stow symlinks (migration only) |
| `run_once_before_install-external-repos.sh` | Once per machine | Clones neovim fork, TPM, superpowers, agentic |
| `run_onchange_before_install-homebrew-bundle.sh.tmpl` | Brewfile changes | `brew bundle install` |
| `run_onchange_before_install-packages.sh.tmpl` | packages.txt changes | `paru -S` (Linux only) |
| `run_onchange_after_set-macos-defaults.sh` | Script changes | Keyboard, Finder, Dock, screenshot defaults |
| `run_onchange_after_disable-macos-animations.sh` | Script changes | Disables macOS UI animations |
| `run_onchange_after_init-macos-machine.sh.tmpl` | Script changes | Sets hostname from machine name |
| `run_onchange_after_sync-agent-skills.sh` | Script changes | Creates `~/.agents/` skill symlinks |

---

## Useful aliases

```bash
sync-skills           # Re-sync ~/.agents/ symlinks after git pull in a skills repo
chezmoi-clone-repos   # Manually clone external repos (when SSH was unavailable at bootstrap)
```

---

## Troubleshooting

**`chezmoi apply` can't find sourceDir**  
Run with explicit flag: `chezmoi apply --source ~/.dotfiles`

**Skills are missing or stale**  
Run `chezmoi-clone-repos` (repos never cloned) or `sync-skills` (repos exist, symlinks stale).

**tmux plugins not installed**  
Open tmux and press `Ctrl-S I` once to trigger TPM.

**tmuxifier not found on shell start**  
Normal before TPM installs plugins. Open tmux, press `prefix + I` once; subsequent shells find it.

**macOS defaults scripts re-run unexpectedly**  
They fire when their own content changes. If you edited one, that's why.
