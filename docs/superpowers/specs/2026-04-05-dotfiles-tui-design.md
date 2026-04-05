# Consolidated Dotfiles Manager — Design Spec

Replaces `stowy.sh` and `import.py` with a single Python script (`dotfiles.py`) that provides an interactive TUI for managing stow packages.

## Goals

- Single entry point for stow and import workflows
- Interactive TUI with multi-select, toggle-all, and status indicators
- Zero external dependencies (stdlib only: tty, termios, subprocess, pathlib, shutil)
- Cross-platform: macOS and Linux (assumes zsh shell and `stow` binary available)
- Internal layering that allows adding CLI flags later without restructuring

## Non-Goals

- No curses, no Textual, no third-party TUI libraries
- No daemon or watch mode
- No automatic submodule management

## Package Patterns

Packages fall into two structural patterns that determine how stow maps them and how state detection works:

### Flat packages — files at package root, target is a specific directory

```
ghostty/                        target: ~/.config/ghostty
├── target.stowy
└── config                 →    ~/.config/ghostty/config  (file symlink)
```

Examples: alacritty, fd, ghostty, wezterm, zsh, zshrc, tmux

Stow creates **individual file symlinks** (and directory symlinks for subdirs like `tmux/plugins/`) inside the target directory.

### Nested packages — subdirectory in package, target is a parent directory

```
nvim/                           target: ~/.config
├── target.stowy
└── nvim/                  →    ~/.config/nvim  (directory symlink)
    ├── init.lua
    └── lua/...
```

Examples: nvim, omz, opencode, iTerm2, xcode-themes, omz_plugins, omz_themes

Stow creates a **directory symlink** at `<target>/<subdir-name>` pointing to the package subdirectory. The package subdirectory name becomes the directory name at the target.

### target.stowy Parsing

The file is a single line: `STOWY_TARGET=<path>`. The current `stowy.sh` sources it as shell, so `$HOME` expands naturally. In Python, parsing must:

1. Strip optional quotes around the value (`"$HOME/.config"`)
2. Expand `$HOME` and `~` to `Path.home()`
3. Handle hardcoded absolute paths (e.g., `/home/ronny/.config/alacritty` — legacy)

### Effective Check Path

State detection operates on the **effective check path** — the actual location on disk where this package's content should appear:

| Pattern | Effective check path |
|---------|---------------------|
| **Flat** (target is specific dir) | `STOWY_TARGET` itself (e.g., `~/.config/ghostty`) |
| **Nested** (target is parent dir) | `STOWY_TARGET/<subdir>` for each subdirectory in the package (e.g., `~/.config/nvim`) |

To distinguish: after reading `STOWY_TARGET`, list the package directory contents (excluding `target.stowy`, `.DS_Store`). If the package contains only regular files (and `dot-` prefixed files), it is **flat**. If it contains subdirectories, it is **nested**.

## Package States

| State | Condition | Action on confirm |
|-------|-----------|-------------------|
| `stowed` | Symlinks exist at effective check path, pointing back to this package | Re-stow (update symlinks) |
| `not stowed` | `target.stowy` exists but effective check path doesn't exist or has no symlinks to this package | Create target dir if needed, stow |
| `importable` | Real (non-symlink) files/dirs exist at effective check path AND package has no payload beyond `target.stowy` | Copy into package, remove original, stow |
| `conflict` | Real files/dirs exist at effective check path AND package already has payload | Merge with conflict resolution, then stow |

### State Detection Logic

1. Parse `STOWY_TARGET` from `target.stowy` (expand `$HOME`, strip quotes)
2. Determine package pattern (flat vs nested) by inspecting package contents
3. Compute effective check path(s)
4. For **flat** packages — check if files in the target dir are symlinks pointing into `<dotfiles>/<package>/`
5. For **nested** packages — check if the subdirectory at target is itself a symlink pointing to `<dotfiles>/<package>/<subdir>/`, OR if it's a real directory containing symlinks pointing back
6. Based on symlink presence and package payload:
   - All expected symlinks present → `stowed`
   - No symlinks and no real files at check path → `not stowed`
   - Real files at check path, empty package → `importable`
   - Real files at check path, package has content → `conflict`

## Architecture

Single file `dotfiles.py` at repo root, organized into four internal layers:

```
┌─────────────────────────────┐
│  CLI Layer                  │  argparse: --dry-run (extensible)
├─────────────────────────────┤
│  Core Layer                 │  Pure functions, no TUI imports
│  - scan_packages()          │  Returns list of (name, state, paths)
│  - detect_state()           │  Determines package state
│  - stow_package()           │  Runs stow via subprocess
│  - import_package()         │  Copies files into package dir
│  - merge_package()          │  Merge with conflict tracking
├─────────────────────────────┤
│  TUI Layer                  │  Raw tty/termios interactive list
│  - render_list()            │  Draws the selection UI
│  - get_key()                │  Reads single keypress
│  - run_selection_screen()   │  Main selection loop
│  - run_conflict_screen()    │  Conflict resolution prompts
├─────────────────────────────┤
│  Orchestrator               │  Wires: parse args → scan → TUI → execute
│  - main()                   │  Entry point
└─────────────────────────────┘
```

### Layer Rules

- **Core** has zero TUI imports. All functions take explicit arguments and return data. This makes them callable from future CLI flags (e.g., `--stow-all`) without going through the TUI.
- **TUI** only handles display and user input. It calls Core functions for all logic.
- **Orchestrator** is the glue: parses CLI args, calls Core to scan, hands results to TUI for selection, then calls Core to execute actions.

## TUI Behavior

### Main Selection Screen

```
dotfiles manager

  ◉ ghostty          [stowed]
  ○ nvim             [stowed]
  ○ alacritty        [not stowed]
  ○ opencode         [importable]
  ○ wezterm          [conflict]

  ↑/↓ navigate  SPACE toggle  a select all  ENTER confirm  q quit
```

- Arrow keys (up/down) to navigate
- Space to toggle selection on current item
- `a` to toggle all (select all / deselect all)
- Enter to confirm and execute actions on selected packages
- `q` or Ctrl+C to quit without changes
- Scrolling window when list exceeds terminal height (same approach as `lmstudio_hf.py`)
- State shown inline with color-coded brackets (using ANSI escape codes):
  - `[stowed]` — green
  - `[not stowed]` — yellow
  - `[importable]` — cyan
  - `[conflict]` — red

### Conflict Resolution Screen

Shown after the main selection, only for packages in `importable` or `conflict` state. One package at a time:

```
Import 'wezterm' — 2 conflict(s):

  wezterm.lua        [local differs from remote]
  colors.lua         [local differs from remote]

  For each file: (l)ocal / (r)emote / (b)oth
```

- `l` — keep the version already in the dotfiles package
- `r` — overwrite with the version from the target location
- `b` — keep both (backup local as `<file>.orig`, copy remote in)
- After resolving all conflicts, the original target dir is removed and the package is stowed

### Dry-Run Mode

When `--dry-run` is passed:
- Footer shows `[DRY RUN]` indicator
- All actions print what would happen but make no filesystem changes
- Stow subprocess is not invoked

## Stow Invocation

Reimplements `stowy.sh` logic in Python via `subprocess.run`:

```python
subprocess.run([
    "stow",
    "-t", stow_target,
    "-v", package_name,
    "--dotfiles",
    "--ignore=^target\\.stowy$",
    "--ignore=\\.DS_Store"
], cwd=dotfiles_root, check=True)
```

- `dotfiles_root` is the directory containing `dotfiles.py` (detected via `Path(__file__).parent`)
- Target dir is created with `mkdir -p` equivalent before stowing
- Errors from stow are captured and displayed after all actions complete

## Import Flow

For packages in `importable` or `conflict` state that the user selects:

### Flat packages (e.g., ghostty → `~/.config/ghostty`)

1. Copy files from `STOWY_TARGET` into the package root (e.g., `~/.config/ghostty/config` → `<dotfiles>/ghostty/config`)
2. For `conflict` state: run conflict resolution screen first
3. Remove the original target directory (`shutil.rmtree`)
4. Run stow to recreate symlinks

### Nested packages (e.g., opencode → `~/.config`)

1. Copy the subdirectory from `STOWY_TARGET/<subdir>` into the package (e.g., `~/.config/opencode/` → `<dotfiles>/opencode/opencode/`)
2. For `conflict` state: run conflict resolution screen first
3. Remove the original subdirectory at target (`shutil.rmtree` on `STOWY_TARGET/<subdir>`)
4. Run stow to create directory symlink

## File Layout

```
.dotfiles/
├── dotfiles.py          # NEW — consolidated manager
├── stowy.sh             # DEPRECATED — kept for reference, removed later
├── import.py            # DEPRECATED — kept for reference, removed later
├── alacritty/
│   ├── target.stowy
│   └── ...
└── ...
```

## CLI Interface

```
usage: dotfiles.py [--dry-run]

Manage dotfiles packages — stow, import, and resolve conflicts.

optional arguments:
  --dry-run    Show what would be done without making changes
```

Future flags (not implemented now, but the argparse structure supports them):
- `--stow-all` — stow everything non-interactively
- `--package <name>` — operate on a single package
- `--verbose` — extra output

## Platform Notes

- macOS and Linux supported
- Assumes `zsh` shell and `stow` binary are installed and on PATH
- Uses `tty` and `termios` from Python stdlib (POSIX-only, which covers both targets)
- Paths use `Path.home()` — no hardcoded `/home/` or `/Users/`
- ANSI escape codes for colors and screen clearing (supported by all modern terminals on both platforms)
