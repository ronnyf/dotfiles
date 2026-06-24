---
version: 1.5.0
prd: docs/prd/chezmoi-migration.md
prd-version: 1.1.0
metadata:
  reference-process: v1.5.0
---

# Spec: Migrate dotfiles management from GNU stow to chezmoi

## Architecture Overview

The existing `~/.dotfiles` git repository becomes the chezmoi source directory.
Chezmoi replaces the stow/dotfiles.py machinery: it copies tracked files to their
home-directory targets (not symlinks), runs OS-guarded bootstrap scripts on apply,
and manages symlinks for the agent-skill fan-out.

Three categories of content coexist in the source directory:

1. **Tracked config files** — files prefixed with `dot_` (and nested in `dot_config/`,
   `dot_Library/` etc.) that chezmoi copies directly to `$HOME`. No symlinks.
2. **Bootstrap scripts** — under `.chezmoiscripts/`, prefixed `run_onchange_` (fires
   when the script or its embedded checksum changes) or `run_once_` (fires once per
   machine). Each script opens with an OS guard that exits early on non-target platforms.
3. **Chezmoi-managed symlinks** — `symlink_*.tmpl` source files that chezmoi renders and
   creates as real symlinks at the target path, used exclusively for the agent-skill
   fan-out.

External repos (neovim, superpowers, agentic) are NOT tracked inside chezmoi. They are
cloned by `run_once_` scripts and kept updated by the user via `git pull` in those
directories.

---

## Modules + Responsibilities + Interfaces

### M1 — Chezmoi configuration

**Files:** `.chezmoi.toml.tmpl`, `.chezmoiignore`, `.chezmoiexternal.json` (absent;
external repos handled by scripts, not chezmoi externals — see AD-2)

**Responsibility:** Configure chezmoi to use `~/.dotfiles` as its source dir, record
the machine name once, and exclude non-config files from home-directory deployment.

**Interface:**
- `.chezmoi.toml.tmpl` renders to `~/.config/chezmoi/chezmoi.toml` on first apply.
  Records `machineName` via `promptStringOnce`; sets `sourceDir = "~/.dotfiles"`.
- `.chezmoiignore` excludes: `README.md`, `AGENTS.md`, `CONTEXT.md`, `docs/`,
  `Brewfile`, `packages.txt`, `dotfiles.py`, `import.py`, `test_dotfiles.py`,
  `__pycache__/`. Also OS-conditionally ignores non-macOS content on Linux:
  `Library/**` (Xcode themes — `~/Library/` has no leading dot, source is `Library/` not `dot_Library/`),
  `.config/iTerm2/**`.

**Bootstrap command (new machine):**

`chezmoi init --apply --source <dir> <remote>` does NOT clone the remote to `<dir>` — it
always clones to `~/.local/share/chezmoi` regardless of `--source`. The correct bootstrap
for a custom `sourceDir` is a two-step sequence:

```bash
# macOS
brew install chezmoi
git clone https://github.com/<user>/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles

# Linux (CachyOS/Arch)
sudo pacman -S chezmoi git
git clone https://github.com/<user>/dotfiles.git ~/.dotfiles
chezmoi apply --source ~/.dotfiles
```

On first apply, chezmoi reads `.chezmoi.toml.tmpl`, prompts for `machineName`, and writes
`~/.config/chezmoi/chezmoi.toml` with `sourceDir = "~/.dotfiles"`. Subsequent `chezmoi apply`
and `chezmoi update` commands use that persisted config and do not require `--source`.

---

### M2 — Tracked config files

**Files (source → target):**

| Source path | Home target | OS |
|---|---|---|
| `dot_zshrc` | `~/.zshrc` | all |
| `dot_zshrc.alias` | `~/.zshrc.alias` | all |
| `dot_zsh_plugins.txt` | `~/.zsh_plugins.txt` | all |
| `dot_config/ghostty/config` | `~/.config/ghostty/config` | all |
| `dot_config/alacritty/alacritty.toml` | `~/.config/alacritty/alacritty.toml` | all |
| `dot_config/wezterm/wezterm.lua` | `~/.config/wezterm/wezterm.lua` | all |
| `dot_config/starship.toml` | `~/.config/starship.toml` | all |
| `dot_config/fd/ignore` | `~/.config/fd/ignore` | all |
| `dot_config/tmux/tmux.conf` | `~/.config/tmux/tmux.conf` | all |
| `dot_config/opencode/opencode.json` | `~/.config/opencode/opencode.json` | all |
| `dot_config/opencode/package.json` | `~/.config/opencode/package.json` | all |
| `dot_config/opencode/tui.json` | `~/.config/opencode/tui.json` | all |
| `dot_config/opencode/oh-my-opencode-slim.json` | `~/.config/opencode/oh-my-opencode-slim.json` | all |
| `Library/Developer/Xcode/UserData/FontAndColorThemes/` | `~/Library/Developer/Xcode/UserData/FontAndColorThemes/` | macOS only |
| `dot_config/iTerm2/` | `~/.config/iTerm2/` | macOS only |

The macOS-only rows are excluded on Linux via `.chezmoiignore` OS conditionals.

`dot_zsh_plugins.txt` is a new file (see M5 — Zsh plugin management). It replaces
the `zsh-plugins` stow package.

The `~/.config/opencode/` content intentionally excludes `node_modules/`,
`package-lock.json`, `opencode.json.bak`, `agents/`, `commands/`, and `skills/`
subdirectories — those are either generated artefacts or managed via symlinks (M4).
These paths are listed in `.chezmoiignore`.

**Security note:** `opencode.json` currently contains no API keys (LLM Studio / local
inference config). If cloud provider credentials are ever added, it must be renamed to
`private_dot_config/opencode/opencode.json` (chezmoi `private_` prefix deploys at 0600)
or excluded from tracking entirely. The same rule applies to any config file that gains
credentials — track with `private_` or exclude; never commit secrets.

`~/.zshrc.work`, `~/.zshrc.home`, and `~/.zshrc.claude` are machine-local files
(conditionally sourced by `dot_zshrc`) and are intentionally **not** tracked in chezmoi.
They are excluded from the source dir by listing them in `.chezmoiignore`.

**Source file renaming:** The current repo uses `dot-` (hyphen) prefixes on several
files (e.g. `zshrc/dot-zshrc`). Chezmoi uses `dot_` (underscore). All source files
must be renamed and restructured into the flat chezmoi source layout as part of the
migration (see M8).

---

### M3 — Bootstrap scripts

**Directory:** `.chezmoiscripts/`

All scripts live **directly** in `.chezmoiscripts/` — chezmoi does not recurse into
subdirectories for script discovery. OS targeting is handled by OS guards in the script
body, not by subdirectory organisation. Each script opens with `#!/usr/bin/env bash`
followed immediately by an OS guard:
- macOS-only scripts: `[[ "$(uname -s)" == "Darwin" ]] || exit 0`
- Linux-only scripts: `[[ "$(uname -s)" == "Linux" ]] || exit 0`

#### Migration script (one-time, runs before any chezmoi file deployment)

| Script | Trigger | Responsibility |
|---|---|---|
| `run_once_before_00-unstow.sh` | Runs once per machine | Remove all stow-created symlinks from `$HOME` pointing into `~/.dotfiles/` before chezmoi deploys real files |

This script is critical for existing machines. Chezmoi cannot overwrite a symlink with a
regular file without explicit `--force`. The script walks each known stow target path and
calls `unlink` if the path is a symlink resolving into `~/.dotfiles/`. It must run before
any file deployment; the `_before_` qualifier and `00-` lexicographic prefix guarantee it
runs first among all `run_once_before_` scripts.

Additionally, the script removes empty directories left by stow after symlinks are removed.
In particular, `~/.config/zsh-plugins/` will be left as an empty real directory (stow uses
`--no-folding`, so the directory itself is not a symlink). The script removes it with
`rmdir ~/.config/zsh-plugins 2>/dev/null || true` — the portable idiom for
"remove if empty, ignore if not or absent" (avoids `--ignore-fail-on-non-empty` which
is a GNU extension unavailable on macOS BSD `rmdir`).

#### macOS scripts (OS guard: `[[ "$(uname -s)" == "Darwin" ]] || exit 0`)

| Script | Trigger | Responsibility |
|---|---|---|
| `run_onchange_before_install-homebrew-bundle.sh.tmpl` | Brewfile checksum changes | `brew bundle install --no-upgrade --file <Brewfile>` |
| `run_onchange_after_set-macos-defaults.sh` | Script content changes | `defaults write` calls for macOS system settings |
| `run_onchange_after_disable-macos-animations.sh` | Script content changes | Disable UI animations via `defaults write` |
| `run_onchange_after_init-macos-machine.sh.tmpl` | Script content changes | Set hostname from `machineName` template variable |

The Brewfile lives at the root of the source dir (chezmoiignored, not deployed to `$HOME`).
Its SHA256 is embedded as a comment in the brew-bundle script so that modifying `Brewfile`
re-triggers the script on next `chezmoi apply`.

#### Linux scripts (OS guard: `[[ "$(uname -s)" == "Linux" ]] || exit 0`)

| Script | Trigger | Responsibility |
|---|---|---|
| `run_onchange_before_install-packages.sh.tmpl` | packages.txt checksum changes | `yay -S --needed --noconfirm <package-list>` |

`packages.txt` lives at the root of the source dir (chezmoiignored). Its SHA256 is
embedded in the script via a template comment, mirroring the Brewfile pattern.

**Note on yay availability:** `yay` is pre-installed on CachyOS. On vanilla Arch Linux
it must be bootstrapped from the AUR before this script can run. The script includes a
guard: if `yay` is not present, it prints instructions for building yay from source and
exits non-zero rather than silently skipping.

#### Cross-platform scripts (no OS guard)

| Script | Trigger | Responsibility |
|---|---|---|
| `run_once_before_install-external-repos.sh` | Runs once per machine | Clone neovim fork, superpowers, and agentic to their canonical locations |
| `run_onchange_after_sync-agent-skills.sh` | Script content changes | Create per-skill symlinks in `~/.agents/{skills,agents,commands}/` from the cloned repos |

The `_before_` qualifier on the install script and `_after_` qualifier on the sync
script guarantee that repos are cloned before the fan-out symlinks are created.
`run_onchange_after_sync-agent-skills.sh` also opens with a guard:

```bash
[[ -d "$HOME/.agents/repos/superpowers" && -d "$HOME/.agents/repos/agentic" ]] \
  || { echo "ERROR: external repos not cloned yet. Run chezmoi-clone-repos alias."; exit 1; }
```

**SSH pre-check in the clone script:** `run_once_` scripts are marked complete after
exit 0; a non-zero exit is NOT retried on subsequent applies. The install script verifies
SSH auth availability before attempting `git clone` via SSH, using:

```bash
ssh -T git@github.com 2>/dev/null; _ssh_exit=$?
# GitHub returns exit 1 on successful auth ("Hi username!"), 255 on connection failure
[[ $_ssh_exit -eq 255 ]] && {
  echo "WARNING: SSH auth unavailable. Run 'chezmoi-clone-repos' after configuring SSH keys."
  exit 0  # record as done; recovery via alias
}
```

Exit code 255 indicates connection/auth failure; exit 1 is GitHub's normal success
response. A naive `ssh -T … || fail` always triggers — the script must check for 255.

**Trust model:** the skill repos (`superpowers`, `agentic`) are trusted personal and
upstream sources. Running `git pull` in either repo is equivalent to deploying new code
into the Claude Code and OpenCode skill execution paths. Updates should be deliberate
and reviewed — never automated. This is enforced by design (no auto-pull on
`chezmoi update`); see AD-2.

---

### M4 — Agent skills fan-out

**Canonical location:** `~/.agents/`

```
~/.agents/
├── skills/          ← per-skill symlinks from superpowers/skills/* and agentic/skills/*
├── agents/          ← per-file symlinks from agentic/agents/*
└── commands/        ← per-file symlinks from agentic/commands/*
```

The repos are cloned by `run_once_before_install-external-repos.sh` to:
- `~/.agents/repos/superpowers/` — github.com/obra/superpowers
- `~/.agents/repos/agentic/` — github.com/ronnyf/agentic

The `run_onchange_after_sync-agent-skills.sh` script maintains the flat `~/.agents/` structure by
creating per-entry symlinks. Key implementation requirements:
- `shopt -s nullglob` before any glob to prevent bash expanding an empty directory into a
  literal glob string and creating a `*`-named symlink.
- Strip trailing slash from directory names in both `name` derivation AND the `ln` target:
  use `"${dir%/}"` in the `ln` call, not `"$dir"`, to avoid macOS path resolution issues.
- Guard against existing real directories: if a target path exists as a non-symlink
  directory, exit with an error rather than silently nesting the symlink one level too deep.
- Guard for missing `agents/`/`commands/` source directories: if those subdirs do not exist
  in the cloned repo (e.g. partial clone), print a diagnostic rather than silently skipping.

```bash
shopt -s nullglob
mkdir -p ~/.agents/skills ~/.agents/agents ~/.agents/commands

# per-skill symlinks from both repos
for dir in ~/.agents/repos/superpowers/skills/*/; do
  name=$(basename "${dir%/}")
  [[ -d ~/.agents/skills/$name && ! -L ~/.agents/skills/$name ]] \
    && { echo "ERROR: real dir at ~/.agents/skills/$name"; exit 1; }
  ln -sfn "${dir%/}" ~/.agents/skills/$name
done
for dir in ~/.agents/repos/agentic/skills/*/; do
  name=$(basename "${dir%/}")
  [[ -d ~/.agents/skills/$name && ! -L ~/.agents/skills/$name ]] \
    && { echo "ERROR: real dir at ~/.agents/skills/$name"; exit 1; }
  ln -sfn "${dir%/}" ~/.agents/skills/$name
done

# agentic agents and commands (files, not dirs)
[[ -d ~/.agents/repos/agentic/agents ]] || { echo "WARN: agentic/agents dir missing"; }
for f in ~/.agents/repos/agentic/agents/*.md; do
  ln -sfn "$f" ~/.agents/agents/$(basename "$f")
done
[[ -d ~/.agents/repos/agentic/commands ]] || { echo "WARN: agentic/commands dir missing"; }
for f in ~/.agents/repos/agentic/commands/*.md; do
  ln -sfn "$f" ~/.agents/commands/$(basename "$f")
done
```

**Skill name collision policy:** if both `superpowers` and `agentic` define a skill with
the same directory name, `agentic` wins (its loop runs second). This is intentional —
`agentic` is the user-maintained fork and takes precedence over the upstream `superpowers`
pack. The policy is documented here; implementers should not change loop order.

**Re-running after upstream updates:** Because the sync script is `run_onchange_`, it
only fires automatically when the script's own content changes — not when new skills
are added via `git pull` inside the repos. Two aliases are defined in `dot_zshrc.alias`:

```zsh
alias sync-skills='bash ~/.dotfiles/.chezmoiscripts/run_onchange_after_sync-agent-skills.sh'
alias chezmoi-clone-repos='bash ~/.dotfiles/.chezmoiscripts/run_once_before_install-external-repos.sh'
```

`sync-skills` re-runs the fan-out after `git pull` in either skill repo.
`chezmoi-clone-repos` manually triggers the clone script when the `run_once_` marker
has been recorded but cloning failed (e.g. SSH unavailable at bootstrap time).

**Note on `.tmpl` suffix for the clone script:** the clone script uses `$HOME` shell
variable rather than chezmoi template directives (`{{ .chezmoi.homeDir }}`), so it does
NOT carry the `.tmpl` suffix. This makes it safely invocable via plain `bash` in the
recovery alias. The filename is therefore `run_once_before_install-external-repos.sh`
(no `.tmpl`). Contrast with the Brewfile script, which embeds a live SHA256 checksum
via `{{ include "Brewfile" | sha256sum }}` and legitimately requires `.tmpl`.

Agent tool integrations are chezmoi-managed symlinks:

| Chezmoi source | Target path | Points to |
|---|---|---|
| `dot_claude/symlink_skills.tmpl` | `~/.claude/skills` | `~/.agents/skills` |
| `dot_config/opencode/symlink_skills.tmpl` | `~/.config/opencode/skills` | `~/.agents/skills` |
| `dot_config/opencode/symlink_agents.tmpl` | `~/.config/opencode/agents` | `~/.agents/agents` |
| `dot_config/opencode/symlink_commands.tmpl` | `~/.config/opencode/commands` | `~/.agents/commands` |

Each `.tmpl` file contains `{{ .chezmoi.homeDir }}/.agents/<subdir>` so the path expands
correctly on every machine regardless of username.

---

### M5 — Zsh plugin management

**Replaces:** `zsh-plugins/` stow package and its three submodules.

**Tool:** antidote (installed via Homebrew on macOS, via pacman on Linux).

**Interface:** `~/.zsh_plugins.txt` (tracked in chezmoi as `dot_zsh_plugins.txt`) declares
the plugin list:

```
zsh-users/zsh-autosuggestions
zsh-users/zsh-syntax-highlighting
Aloxaf/fzf-tab
```

`dot_zshrc` replaces the three direct `source` lines (currently pointing at
`~/.config/zsh-plugins/…`) with antidote's static-bundle pattern. The path is
hardcoded rather than evaluated via `$(brew --prefix antidote)` to avoid forking a
subprocess on every shell startup:

```zsh
if [[ "$OSTYPE" == "darwin"* ]]; then
  # Works on both Apple Silicon (/opt/homebrew) and Intel (/usr/local)
  for _antidote_prefix in /opt/homebrew /usr/local; do
    [[ -f "$_antidote_prefix/opt/antidote/share/antidote/antidote.zsh" ]] && {
      source "$_antidote_prefix/opt/antidote/share/antidote/antidote.zsh"; break
    }
  done
else
  [[ -f /usr/share/zsh/plugins/antidote/antidote.zsh ]] \
    && source /usr/share/zsh/plugins/antidote/antidote.zsh
fi
antidote load
```

The macOS block checks `/opt/homebrew` (Apple Silicon) first, then `/usr/local` (Intel),
with no subprocess fork. The Linux path is the standard AUR/pacman install location.

Antidote bundles plugins to `~/.cache/antidote/` on first load and caches thereafter.
The existing `ZSH_AUTOSUGGEST_CLEAR_WIDGETS` configuration and `fzf-tab` zstyle entries
in `dot_zshrc` remain unchanged — they configure the plugins after antidote loads them.

---

### M6 — Tmux plugin management

**Replaces:** `tmux/plugins/` submodules.

**Tool:** TPM (tmux Plugin Manager), bootstrapped by `run_once_before_install-external-repos.sh`
which clones `tmux-plugins/tpm` to `~/.tmux/plugins/tpm`.

**Interface:** `tmux.conf` declares plugins via `set -g @plugin '...'` and contains the
standard TPM auto-install snippet at the bottom:

```tmux
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'dracula/tmux'
set -g @plugin 'jimeh/tmuxifier'
set -g @plugin 'christoomey/vim-tmux-navigator'
run '~/.tmux/plugins/tpm/tpm'
```

The existing `run '$HOME/.config/tmux/plugins/tpm/tpm'` line in `tmux.conf` is updated
to `run '~/.tmux/plugins/tpm/tpm'` to match TPM's default install path.

The `~/.zshrc` `tmuxifier init` source line is updated from
`~/.config/tmux/plugins/tmuxifier` to `~/.tmux/plugins/tmuxifier` to match TPM's
install path.

`TMUXIFIER_LAYOUT_PATH` (set in `dot_zshrc` to `$HOME/.config/tmux/layouts`) is
**unchanged** — it points at a user-managed layouts directory under `~/.config/tmux/`,
not at the plugin install path. The layouts directory is independent of where TPM
installs tmuxifier and must continue to exist at `~/.config/tmux/layouts/`. Any
user-created layout files in the stow-era path must be preserved there.

---

### M7 — Neovim config

**Tool:** chezmoi `run_once_` script (same script as external repos — M3).

`run_once_before_install-external-repos.sh` clones
`git@github.com:ronnyf/kickstart.nvim.git` to `~/.config/nvim/` if that directory does
not already exist. The clone is guarded with `[[ -d "$HOME/.config/nvim" ]] || git clone
...` so the script is idempotent on existing machines that already have a neovim config.
Subsequent updates to the neovim fork are done manually with `git pull` inside
`~/.config/nvim/`. lazy.nvim (neovim's plugin manager) manages neovim plugins; chezmoi
has no role there.

---

### M8 — Stow tooling retirement

On migration completion, the following are deleted:
- `dotfiles.py`, `import.py`, `test_dotfiles.py`, `__pycache__/`
- `target.stowy` files in every package directory
- The `skills/` top-level directory (repos now cloned externally)
- Submodule entries for `skills/agentic`, `skills/superpowers`, `neovim/nvim`,
  `tmux/plugins/*`, `zsh-plugins/*` from `.gitmodules`

**Source file restructuring:** All existing stow-package files are renamed and moved
into the flat chezmoi source layout. Specifically:
- `dot-` (hyphen) prefixes → `dot_` (underscore) prefixes (chezmoi convention)
- Per-package subdirectories collapsed: `zshrc/dot-zshrc` → `dot_zshrc` at repo root,
  `ghostty/config` → `dot_config/ghostty/config`, etc.
- The `opencode/opencode/` payload flattened to `dot_config/opencode/` (excluding
  `node_modules/`, `package-lock.json`, `agents/`, `commands/`, `skills/` subdirs)
- The `iTerm2/iTerm2/` double-nested payload (same pattern as `opencode/opencode/`)
  flattened to `dot_config/iTerm2/` — the *inner* `iTerm2/` directory's contents
  (the `.itermcolors` files) become the chezmoi source, not the outer directory.
- `starship/starship.toml` → `dot_config/starship.toml` (adds `dot_config/` nesting;
  the file itself has no `dot-` prefix in the stow layout)

**Modified existing tracked files (net-new content):**
- `dot_zshrc.alias` — `sync-skills` and `chezmoi-clone-repos` aliases added
- `dot_config/tmux/tmux.conf` — `run` line and `tmuxifier init` source line updated
- `dot_zshrc` — antidote source block replaces three explicit plugin `source` lines

**Net-new source paths added by this migration:**
- `dot_claude/` — new tracked directory; chezmoi creates `~/.claude/` if absent. No stow
  symlink previously existed at `~/.claude/skills`, so no unstow step is needed for it.
- `dot_zsh_plugins.txt` — new tracked file; no stow predecessor.
- `~/.agents/` — created by `run_once_before_install-external-repos.sh` (`mkdir -p`);
  **not** a chezmoi-tracked directory. Chezmoi owns only the symlinks pointing into it.

`AGENTS.md` is updated to document the chezmoi workflow, including the correct
bootstrap command (`git clone <remote> ~/.dotfiles && chezmoi apply`).

---

## Architectural Decisions

### AD-1 — Reuse `~/.dotfiles` as the chezmoi source directory

**Decision:** Configure chezmoi with `sourceDir = "~/.dotfiles"` in `.chezmoi.toml.tmpl`.

**Alternatives considered:**
- New repo at chezmoi's default `~/.local/share/chezmoi`.
- New repo at default location pointing at the same GitHub remote (history loss).

**Rationale:** Preserves the full git history. No new remote or repo fork needed. The
existing dotfiles remote (GitHub) continues to serve as the sync target. Non-chezmoi
files coexist in the repo by listing them in `.chezmoiignore`.

**Trade-offs:** `chezmoi init --source <dir> <remote>` does NOT clone the remote to
`<dir>` — it still clones to `~/.local/share/chezmoi`. The correct bootstrap for a
custom `sourceDir` is therefore a two-step sequence: `git clone <remote> ~/.dotfiles`,
then `chezmoi apply`. This is slightly more explicit than the default `chezmoi init
--apply <remote>` single-command flow but does not add meaningful complexity.

---

### AD-2 — External repos via `run_once_` scripts, not `.chezmoiexternal.toml`

**Decision:** Clone neovim, superpowers, and agentic via a `run_once_` shell script, not
chezmoi's built-in `.chezmoiexternal.toml` git-repo support.

**Alternatives considered:**
- `.chezmoiexternal.toml` with `type = "git-repo"` per repo — chezmoi-native, declarative.

**Rationale:** Chezmoi's `git-repo` external type clones the entire repository to the
declared target path. The three repos each have internal structure (`skills/`, `agents/`,
`commands/` subdirs, `README.md`, etc.) that does not match the desired deployment
structure flat in `~/.agents/`. A `run_once_` script gives full control over clone path
and skip-if-exists semantics. The fan-out symlink logic (M4) that follows also requires
a shell script; co-locating clone and fan-out setup in scripts keeps the mechanism uniform.

**Trade-offs:** Repos are not automatically updated by `chezmoi update` — the user must
run `git pull` in each repo directory manually or add a separate update alias. This is
intentional: automatic pulls could silently break agent behaviour on a `chezmoi update`.

---

### AD-3 — Per-entry symlinks in `~/.agents/` (not directory copies or nested clones)

**Decision:** The `run_onchange_after_sync-agent-skills.sh` script creates individual symlinks
in `~/.agents/skills/`, `~/.agents/agents/`, and `~/.agents/commands/` pointing at
entries inside the cloned repos. Agent tools symlink to `~/.agents/` subdirs.

**Alternatives considered:**
- Nest repos directly as `~/.agents/skills/superpowers/` and `~/.agents/skills/agentic/`
  and point agent tools at those nested dirs. Simpler but agent tools would see
  `superpowers/brainstorming/SKILL.md` not `brainstorming/SKILL.md` — wrong depth.
- Copy (not symlink) skill files into `~/.agents/skills/` on sync. Files diverge from
  the repos; edits in `~/.agents/skills/` are silently lost on next sync.

**Rationale:** Per-entry symlinks reproduce the current stow fan-out exactly, with
`~/.agents/skills/brainstorming/` pointing directly at the repo's `skills/brainstorming/`
entry. Agent tools see a flat skill directory at the correct depth. Edits in the cloned
repos are immediately reflected.

**Trade-offs:** The sync script must be re-run when new skills are added to either repo.
The `run_onchange_` prefix means it re-runs only when the script's own content changes,
not when repo contents change. Adding a new skill to `agentic/skills/` requires
touching the sync script (or running it manually) to create the new symlink.

---

### AD-4 — Antidote as zsh plugin manager

**Decision:** Replace the `zsh-plugins` submodule package with antidote, driven by a
`~/.zsh_plugins.txt` file tracked in chezmoi.

**Alternatives considered:**
- zinit — powerful, large feature surface, complex configuration, past maintainer
  instability.
- sheldon — TOML-based, good but requires a different config format.
- Homebrew/pacman only — works for `zsh-autosuggestions` and `zsh-syntax-highlighting`
  but `fzf-tab` is not available in either package manager.
- `run_once_` clone scripts per plugin — possible but reproduces a plugin manager
  manually.

**Rationale:** Antidote is actively maintained, installs via Homebrew and pacman, and
works with a plain-text plugin list. Its static-bundle mode caches the compiled plugin
file, so shell startup time is unaffected after first load. Using a plugin manager
rather than manual clones aligns with the goal of removing upstream plugin code from
the dotfiles repo.

**Trade-offs:** Adds antidote itself as a dependency. The `~/.zshrc` plugin-source lines
change from explicit paths to antidote's load mechanism — a one-time migration edit.

---

### AD-5 — macOS-only content via `.chezmoiignore` OS conditionals

**Decision:** macOS-specific config directories (`dot_Library/`, `dot_config/iTerm2/`)
are listed in `.chezmoiignore` under a `{{ if ne .chezmoi.os "darwin" }}` template
conditional. They are NOT split into per-OS source subtrees.

**Alternatives considered:**
- Separate `darwin/` and `linux/` subtrees in the source dir with a top-level symlink
  or include strategy.
- Go template `.tmpl` suffix on every macOS-specific file to emit empty content on Linux.

**Rationale:** `.chezmoiignore` with an OS template conditional is the pattern the
chezmoi documentation recommends for platform-specific exclusions. It is a single
declaration per excluded path and requires no changes to the files themselves. The
macOS-specific directories simply do not exist in the deployed home directory on Linux.

**Trade-offs:** `.chezmoiignore` is evaluated at apply time; an ignored path that
previously existed in `$HOME` is not removed by chezmoi automatically. On first apply
on a non-macOS machine, there is nothing to clean up. If the machine later changes OS
(unlikely), manual cleanup of `~/Library` and `~/.config/iTerm2` would be needed.

---

### AD-6 — Stow tooling retired in-place (not archived to a separate branch)

**Decision:** `dotfiles.py`, `import.py`, `test_dotfiles.py`, and all `target.stowy`
files are deleted from the repo in the migration commit. No stow-era branch is preserved
in the main repo; git history serves as the archive.

**Alternatives considered:**
- Preserve a `stow-era` branch pointing at the last stow-managed commit.
- Keep `dotfiles.py` in the repo but stop executing it.

**Rationale:** The stow tooling is tied to the symlink deployment model. Keeping it
alongside chezmoi creates confusion about which tool owns which package. Git history
already provides a complete snapshot of the stow-era state at the merge base. A branch
would require ongoing awareness of its existence without providing any operational value.

**Trade-offs:** Recovering the stow-based setup requires checking out the pre-migration
commit. This is acceptable given how unlikely that scenario is.

---

## Scalability Analysis

**Adding a new config file** — `chezmoi add ~/.config/newtool/config` copies the file
into the source dir with the correct `dot_` prefix. No package declaration, no stow
entry. Scales to arbitrary numbers of tracked files without additional configuration.

**Adding a new machine** — `brew install chezmoi && git clone <remote> ~/.dotfiles && chezmoi apply` on
macOS, or the Linux equivalent (`pacman -S chezmoi git` first). The same sequence works for every additional
machine. Machine-specific state is limited to `machineName` (stored in
`~/.config/chezmoi/chezmoi.toml`, not in the source dir).

**Adding a new agent skill repo** — requires adding a `git clone` call to
`run_once_before_install-external-repos.sh` and updating `run_onchange_after_sync-agent-skills.sh`
to include entries from the new repo. Two small script edits and one `chezmoi apply`.

**Adding a new agent tool** — add one `symlink_*.tmpl` file in the appropriate
`dot_config/<tool>/` directory pointing to `~/.agents/<subdir>`. One file, one `chezmoi apply`.

**Adding a Linux machine of a different distro** — the `run_onchange_before_install-packages.sh.tmpl`
script currently calls `yay` (Arch/AUR). A different distro requires a different
package manager call. The script can be extended with a distribution check
(`/etc/os-release` or `lsb_release`) to branch on package manager. One script edit.

---

## Effectiveness Analysis

The PRD's success criteria are addressed as follows:

1. **Single command to sync** → `chezmoi update --verbose`. Pulls remote and applies in
   one invocation. ✓

2. **Two-command bootstrap** → `git clone <remote> ~/.dotfiles` then
   `chezmoi apply --source ~/.dotfiles`.
   Scripts run as part of apply: packages installed, macOS defaults set,
   external repos cloned, skill symlinks created. ✓

3. **Three deliberate steps to propagate** → `chezmoi edit --apply <file>` (or
   `chezmoi add`), then `chezmoi cd && git commit && git push`, then `chezmoi update` on
   other machines. ✓

4. **No dirty trees from live edits** → chezmoi deploys real copies; edits to live files
   do not write back to the source dir. `chezmoi diff` detects drift; only
   `chezmoi add` or `chezmoi edit` propagates changes intentionally. ✓

5. **Single canonical skills location** → `~/.agents/skills/`. Both agent tools
   (Claude Code, OpenCode) resolve to this path via chezmoi-managed symlinks. ✓

6. **New dependency auto-installed on next sync** → `run_onchange_` scripts fire when
   `Brewfile` or `packages.txt` checksums change. Adding a line to either file and
   running `chezmoi apply` installs the package. ✓

The design is a direct translation of each success criterion to a chezmoi mechanism.
No criterion requires a workaround or partial implementation.

---

## Modernity Justification

**chezmoi** is the current standard for multi-machine dotfile management, actively
maintained (2024–2026), with first-class macOS and Linux support. GNU stow is older and
stable but does not have templating, scripts, or multi-OS guards natively.

**antidote** is the current recommended successor to the abandoned antibody plugin
manager. Its static-bundle approach is faster than zimfw or zinit for typical
configurations and requires no exotic syntax.

**Go templates** (chezmoi's templating language) are used minimally and only where
per-machine variance exists: `machineName` in the config template and `homeDir` in the
symlink templates. No speculative templating is added.

**TPM** remains the standard tmux plugin manager. The only change from current usage
is moving the plugin install path from `~/.config/tmux/plugins/` (stow-managed) to
`~/.tmux/plugins/` (TPM default), which is TPM's documented convention.

No older patterns are used. The spec's approach matches what the current chezmoi
documentation recommends for multi-machine setups with external dependencies.

---

## Reviewer Concerns + Resolutions

*Populated after review rounds 1–2 (2026-06-24).*

| # | Concern | Severity | Resolution |
|---|---|---|---|
| C1 | No step to remove existing stow symlinks before chezmoi apply | Critical | Added `run_once_before_00-unstow.sh` migration script to M3 |
| C2 | `ANTIDOTE_HOME` undefined; `source ${ANTIDOTE_HOME}/…` silently fails | Critical | Fixed M5 to use hardcoded `/opt/homebrew/opt/antidote/…` with `[[ -f ]]` guard |
| C3 | `run_onchange_sync` could run before repos are cloned | Critical | Renamed scripts with `_before_`/`_after_` qualifiers; added guard in sync script |
| C4 | `chezmoi init --apply --source ~/.dotfiles <remote>` clones to wrong location | Critical | Fixed M1 bootstrap to `git clone <remote> ~/.dotfiles && chezmoi apply` |
| C5 | `.chezmoiscripts/darwin/` and `.chezmoiscripts/linux/` subdirs silently ignored | Critical | M3 flattened; all scripts live directly in `.chezmoiscripts/` with OS guards |
| C6 | `nullglob` not set; empty dir expands to literal glob string in fan-out loops | Critical | Added `shopt -s nullglob` and real-dir guard to M4 fan-out script |
| C7 | `ln -sfn "$dir"` trailing slash nests link inside existing real dir | Critical | M4 script strips trailing slash with `${dir%/}` and checks for real dirs |
| C8 | `opencode.json.bak` not excluded — gets copied to `~/.config/opencode/` | Critical | Added to `.chezmoiignore` list in M2 |
| C9 | `TMUXIFIER_LAYOUT_PATH` not addressed alongside tmuxifier path change | Critical | M6 explicitly states `TMUXIFIER_LAYOUT_PATH` is unchanged; layout dir is user-managed |
| C10 | SSH-only clone with `run_once_` = silent failure, no recovery path | Critical | M3 now requires SSH pre-check; unblocked via `chezmoi-clone-repos` alias; trust model documented |
| I1 | `tmux.conf` `run` line still points at stow path | Important | Added explicit `run` line update to M6 |
| I2 | Sync script only re-triggers on script change, not on new skills | Important | Added `sync-skills` alias to M4; documented in `dot_zshrc.alias` |
| I3 | `$(brew --prefix antidote)` forks on every shell; ordering dep on PATH | Important | Fixed M5 to hardcode the verified path |
| I4 | Skill name collision (agentic wins) undocumented | Important | Documented collision policy in M4: agentic wins by loop order, intentional |
| I5 | Source file `dot-` → `dot_` rename never called out | Important | Added source file restructuring section to M8 |
| I6 | Linux script calls `yay` but on vanilla Arch, yay is not pre-installed | Important | Added yay availability guard with error message in M3 |
| I7 | `~/.config/zsh-plugins/` empty dir remains after unstow (not a symlink) | Important | Added `rmdir` cleanup to `run_once_before_00-unstow.sh` description in M3 |
| I8 | `dot_claude/` is net-new, not explicitly called out | Important | Added net-new paths list to M8 |
| I9 | Trust model for skill repos not stated | Important | Added trust model statement to M3 cross-platform scripts section |
| N1 | Ambiguity about which file gets antidote source lines | Minor | M5 now explicitly names `dot_zshrc` |
| N2 | `.zshrc.work`/`.zshrc.home`/`.zshrc.claude` absent from tracked files | Minor | Added note in M2: machine-local, intentionally untracked |
| N3 | `opencode.json` could gain API keys in future | Minor | Added security note in M2 for `private_` prefix requirement |
| C11 | Scalability section still had old broken bootstrap command | Critical | Fixed to `git clone <remote> ~/.dotfiles && chezmoi apply` |
| C12 | `rmdir --ignore-fail-on-non-empty` unavailable on macOS BSD rmdir | Critical | Fixed M3 to `rmdir ... 2>/dev/null \|\| true` |
| C13 | Antidote hardcoded path only works on Apple Silicon; Intel silently skips | Critical | Fixed M5 to loop `/opt/homebrew` then `/usr/local` without subprocess |
| C14 | `agents/`/`commands/` source dirs have no existence guard in fan-out script | Critical | Added `[[ -d ... ]] \|\|` guards before each file loop in M4 |
| C15 | `$dir` trailing slash still passed to `ln -sfn` after name fix | Critical | Fixed M4 to use `"${dir%/}"` in the `ln` call itself |
| C16 | Script name `_before_`/`_after_` dropped in M4, Scalability, AD-3; clone script had spurious `.tmpl` suffix | Critical | Consistent names throughout: `run_once_before_install-external-repos.sh` (no `.tmpl`; uses `$HOME`), `run_onchange_after_sync-agent-skills.sh` |
| C17 | Duplicate cross-platform scripts table in M3 | Critical | Removed duplicate |
| C18 | `ssh -T git@github.com` exits 1 on success — naïve `\|\| fail` always triggers | Critical | M3 now specifies checking exit code 255 (not 1) for auth failure |
| C19 | `chezmoi-clone-repos` alias referenced but never defined | Critical | Defined in M4 alongside `sync-skills` in `dot_zshrc.alias` |
| I-A | iTerm2 double-nesting (`iTerm2/iTerm2/`) not called out in M8 | Important | Added to M8 source file restructuring examples |
| I-B | `sync-skills` alias addition not in M8 migration checklist | Important | Added to M8 modified existing tracked files list |
| C-R3-1 | M7 broken sentence (truncated predicate, unclosed paren) | Critical | M7 rewritten with complete sentences |
| C-R3-3 | No skip-if-exists guard on `~/.config/nvim/` clone for existing machines | Critical | Added `[[ -d ... ]] \|\|` guard to M7 clone description |
| I-R3-1 | `chezmoi-clone-repos` alias ran `bash` on a `.tmpl` file | Important | Clone script renamed to `.sh` (no `.tmpl`); uses `$HOME` not template vars |
| N-R3-2 | `dot_agents/` in net-new list was misleading — not a tracked chezmoi path | Minor | Updated M8 net-new list to clarify `~/.agents/` is script-created, not chezmoi-tracked |
| C-plan-1 | `dot_Library/` maps to `~/.Library/` not `~/Library/` — wrong for Xcode themes | Critical | M2 source path corrected to `Library/` (no `dot_` prefix); `.chezmoiignore` pattern corrected to `Library/**` |

---

## Front-load Refinement Log

Skipped — this is a non-Swift artifact (shell scripts, TOML, Go templates, Markdown).
Per reference-process v1.5.0 §Phase-3, the front-load specialist loop applies to Swift
artifacts only.
