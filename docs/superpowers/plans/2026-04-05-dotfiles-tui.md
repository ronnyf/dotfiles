# Dotfiles TUI Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate `stowy.sh` and `import.py` into a single Python TUI script (`dotfiles.py`) that scans packages, shows their state, and lets the user stow/import interactively.

**Architecture:** Single file with four internal layers (CLI, Core, TUI, Orchestrator). Core is pure functions with no TUI imports. TUI uses raw tty/termios. CLI uses argparse with `--dry-run` today, extensible later.

**Tech Stack:** Python 3 stdlib only (pathlib, subprocess, shutil, tty, termios, argparse, os, sys, enum)

**Spec:** `docs/superpowers/specs/2026-04-05-dotfiles-tui-design.md`

---

### Task 1: Data types and target.stowy parser

**Files:**
- Create: `dotfiles.py`
- Create: `test_dotfiles.py`

- [ ] **Step 1: Write test for target.stowy parsing**

```python
# test_dotfiles.py
import unittest
import tempfile
from pathlib import Path


class TestParseTargetStowy(unittest.TestCase):
    def test_home_var(self):
        from dotfiles import parse_target_stowy
        with tempfile.NamedTemporaryFile(mode="w", suffix=".stowy", delete=False) as f:
            f.write("STOWY_TARGET=$HOME/.config/ghostty\n")
            f.flush()
            result = parse_target_stowy(Path(f.name))
        self.assertEqual(result, Path.home() / ".config" / "ghostty")

    def test_quoted_home_var(self):
        from dotfiles import parse_target_stowy
        with tempfile.NamedTemporaryFile(mode="w", suffix=".stowy", delete=False) as f:
            f.write('STOWY_TARGET="$HOME/.config"\n')
            f.flush()
            result = parse_target_stowy(Path(f.name))
        self.assertEqual(result, Path.home() / ".config")

    def test_tilde(self):
        from dotfiles import parse_target_stowy
        with tempfile.NamedTemporaryFile(mode="w", suffix=".stowy", delete=False) as f:
            f.write("STOWY_TARGET=~/.config/fd\n")
            f.flush()
            result = parse_target_stowy(Path(f.name))
        self.assertEqual(result, Path.home() / ".config" / "fd")

    def test_absolute_path(self):
        from dotfiles import parse_target_stowy
        with tempfile.NamedTemporaryFile(mode="w", suffix=".stowy", delete=False) as f:
            f.write("STOWY_TARGET=/home/ronny/.config/alacritty\n")
            f.flush()
            result = parse_target_stowy(Path(f.name))
        self.assertEqual(result, Path("/home/ronny/.config/alacritty"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest test_dotfiles.py::TestParseTargetStowy -v`
Expected: `ModuleNotFoundError` or `ImportError` — `dotfiles` module doesn't exist yet.

- [ ] **Step 3: Write data types and parser**

```python
#!/usr/bin/env python3
"""Dotfiles manager — stow, import, and resolve conflicts via TUI."""

import os
import sys
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class PackageState(Enum):
    STOWED = "stowed"
    NOT_STOWED = "not stowed"
    IMPORTABLE = "importable"
    CONFLICT = "conflict"


class PackagePattern(Enum):
    FLAT = "flat"
    NESTED = "nested"


@dataclass
class Package:
    name: str
    path: Path                  # absolute path to package dir in dotfiles repo
    target: Path                # parsed STOWY_TARGET
    pattern: PackagePattern
    state: PackageState
    check_paths: list           # effective check paths on disk


DOTFILES_ROOT = Path(__file__).parent.resolve()
IGNORED = {"target.stowy", ".DS_Store"}


# ---------------------------------------------------------------------------
# Core — target.stowy parser
# ---------------------------------------------------------------------------

def parse_target_stowy(filepath: Path) -> Path:
    """Parse a target.stowy file and return the resolved target path."""
    text = filepath.read_text().strip()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("STOWY_TARGET="):
            value = line.split("=", 1)[1]
            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            # Expand $HOME and ~
            value = value.replace("$HOME", str(Path.home()))
            if value.startswith("~"):
                value = str(Path.home()) + value[1:]
            return Path(value)
    raise ValueError(f"No STOWY_TARGET found in {filepath}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test_dotfiles.py::TestParseTargetStowy -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add dotfiles.py test_dotfiles.py
git commit -m "feat: add data types and target.stowy parser"
```

---

### Task 2: Package scanning and pattern detection

**Files:**
- Modify: `dotfiles.py`
- Modify: `test_dotfiles.py`

- [ ] **Step 1: Write tests for pattern detection and scanning**

Append to `test_dotfiles.py`:

```python
class TestDetectPattern(unittest.TestCase):
    def test_flat_package(self):
        from dotfiles import detect_pattern, IGNORED
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "ghostty"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("STOWY_TARGET=$HOME/.config/ghostty\n")
            (pkg / "config").write_text("font-size = 15\n")
            result = detect_pattern(pkg)
            self.assertEqual(result, PackagePattern.FLAT)

    def test_nested_package(self):
        from dotfiles import detect_pattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "nvim"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("STOWY_TARGET=$HOME/.config\n")
            subdir = pkg / "nvim"
            subdir.mkdir()
            (subdir / "init.lua").write_text("-- nvim\n")
            result = detect_pattern(pkg)
            self.assertEqual(result, PackagePattern.NESTED)


class TestGetCheckPaths(unittest.TestCase):
    def test_flat_returns_target(self):
        from dotfiles import get_check_paths, PackagePattern
        target = Path("/tmp/test_target")
        result = get_check_paths(Path("/tmp/pkg"), target, PackagePattern.FLAT)
        self.assertEqual(result, [target])

    def test_nested_returns_subdirs(self):
        from dotfiles import get_check_paths, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "target.stowy").write_text("x\n")
            (pkg / "myapp").mkdir()
            (pkg / "myapp" / "config.json").write_text("{}\n")
            target = Path("/tmp/parent")
            result = get_check_paths(pkg, target, PackagePattern.NESTED)
            self.assertEqual(result, [Path("/tmp/parent/myapp")])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test_dotfiles.py::TestDetectPattern test_dotfiles.py::TestGetCheckPaths -v`
Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Implement pattern detection and check path computation**

Add to `dotfiles.py` after `parse_target_stowy`:

```python
def detect_pattern(package_path: Path) -> PackagePattern:
    """Determine if a package is flat (files at root) or nested (has subdirectories)."""
    for item in package_path.iterdir():
        if item.name in IGNORED:
            continue
        if item.is_dir():
            return PackagePattern.NESTED
    return PackagePattern.FLAT


def get_check_paths(package_path: Path, target: Path, pattern: PackagePattern) -> list:
    """Compute the effective check paths where this package's content should appear."""
    if pattern == PackagePattern.FLAT:
        return [target]
    # Nested: each subdirectory in the package maps to target/<subdir>
    paths = []
    for item in sorted(package_path.iterdir()):
        if item.name in IGNORED:
            continue
        if item.is_dir():
            paths.append(target / item.name)
    return paths
```

- [ ] **Step 4: Implement scan_packages**

Add to `dotfiles.py`:

```python
def scan_packages(dotfiles_root: Path) -> list:
    """Scan the dotfiles repo for all stowy packages. Returns list of Package objects."""
    packages = []
    for entry in sorted(dotfiles_root.iterdir()):
        if not entry.is_dir():
            continue
        target_file = entry / "target.stowy"
        if not target_file.exists():
            continue
        target = parse_target_stowy(target_file)
        pattern = detect_pattern(entry)
        check_paths = get_check_paths(entry, target, pattern)
        state = detect_state(entry, target, pattern, check_paths)
        packages.append(Package(
            name=entry.name,
            path=entry,
            target=target,
            pattern=pattern,
            state=state,
            check_paths=check_paths,
        ))
    return packages
```

Note: `detect_state` is implemented in Task 3. Add a temporary stub so this compiles:

```python
def detect_state(package_path, target, pattern, check_paths):
    """Stub — implemented in Task 3."""
    return PackageState.NOT_STOWED
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest test_dotfiles.py::TestDetectPattern test_dotfiles.py::TestGetCheckPaths -v`
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add dotfiles.py test_dotfiles.py
git commit -m "feat: add package scanning and pattern detection"
```

---

### Task 3: State detection

**Files:**
- Modify: `dotfiles.py`
- Modify: `test_dotfiles.py`

- [ ] **Step 1: Write tests for state detection**

Append to `test_dotfiles.py`:

```python
class TestDetectState(unittest.TestCase):
    def _make_package(self, tmp, name, target_path, files=None, subdirs=None):
        """Helper: create a package dir with optional payload."""
        pkg = Path(tmp) / name
        pkg.mkdir(exist_ok=True)
        (pkg / "target.stowy").write_text(f"STOWY_TARGET={target_path}\n")
        if files:
            for fname, content in files.items():
                (pkg / fname).write_text(content)
        if subdirs:
            for dname, dfiles in subdirs.items():
                d = pkg / dname
                d.mkdir(exist_ok=True)
                for fname, content in dfiles.items():
                    (d / fname).write_text(content)
        return pkg

    def test_not_stowed_target_missing(self):
        from dotfiles import detect_state, detect_pattern, get_check_paths, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir", files={"config": "x"})
            pattern = PackagePattern.FLAT
            check_paths = [Path(f"{tmp}/target_dir")]
            state = detect_state(pkg, Path(f"{tmp}/target_dir"), pattern, check_paths)
            self.assertEqual(state, PackageState.NOT_STOWED)

    def test_stowed_flat(self):
        from dotfiles import detect_state, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir", files={"config": "x"})
            target = Path(f"{tmp}/target_dir")
            target.mkdir()
            (target / "config").symlink_to(pkg / "config")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.STOWED)

    def test_stowed_nested_dir_symlink(self):
        from dotfiles import detect_state, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "nvim", f"{tmp}/config_parent",
                                     subdirs={"nvim": {"init.lua": "-- nvim"}})
            parent = Path(f"{tmp}/config_parent")
            parent.mkdir()
            (parent / "nvim").symlink_to(pkg / "nvim")
            check = [parent / "nvim"]
            state = detect_state(pkg, parent, PackagePattern.NESTED, check)
            self.assertEqual(state, PackageState.STOWED)

    def test_importable(self):
        from dotfiles import detect_state, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            # Package with no payload (just target.stowy)
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir")
            target = Path(f"{tmp}/target_dir")
            target.mkdir()
            (target / "config").write_text("real content")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.IMPORTABLE)

    def test_conflict(self):
        from dotfiles import detect_state, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            # Package WITH payload, AND real files at target
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir",
                                     files={"config": "local version"})
            target = Path(f"{tmp}/target_dir")
            target.mkdir()
            (target / "config").write_text("remote version")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.CONFLICT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test_dotfiles.py::TestDetectState -v`
Expected: FAIL — `detect_state` is still a stub returning `NOT_STOWED`.

- [ ] **Step 3: Implement detect_state**

Replace the `detect_state` stub in `dotfiles.py`:

```python
def _has_payload(package_path: Path) -> bool:
    """Check if a package has content beyond target.stowy."""
    for item in package_path.iterdir():
        if item.name not in IGNORED:
            return True
    return False


def _has_symlinks_to_package(check_path: Path, package_path: Path) -> bool:
    """Check if check_path contains symlinks pointing back to package_path."""
    if not check_path.exists():
        return False
    # Check if the check_path itself is a symlink to the package
    if check_path.is_symlink():
        try:
            resolved = check_path.resolve()
            if str(resolved).startswith(str(package_path.resolve())):
                return True
        except OSError:
            pass
        return False
    # Check files inside the directory
    if check_path.is_dir():
        for item in check_path.iterdir():
            if item.is_symlink():
                try:
                    resolved = item.resolve()
                    if str(resolved).startswith(str(package_path.resolve())):
                        return True
                except OSError:
                    continue
    return False


def _has_real_files(check_path: Path) -> bool:
    """Check if check_path contains real (non-symlink) files."""
    if not check_path.exists():
        return False
    if check_path.is_symlink():
        return False
    if check_path.is_dir():
        for item in check_path.iterdir():
            if not item.is_symlink() and item.is_file():
                return True
            if item.is_dir() and not item.is_symlink():
                return True
    return False


def detect_state(
    package_path: Path,
    target: Path,
    pattern: PackagePattern,
    check_paths: list,
) -> PackageState:
    """Determine the current state of a package."""
    has_payload = _has_payload(package_path)

    # Check all effective check paths
    any_symlinked = False
    any_real_files = False
    for cp in check_paths:
        if _has_symlinks_to_package(cp, package_path):
            any_symlinked = True
        if _has_real_files(cp):
            any_real_files = True

    if any_symlinked:
        return PackageState.STOWED
    if any_real_files and has_payload:
        return PackageState.CONFLICT
    if any_real_files and not has_payload:
        return PackageState.IMPORTABLE
    return PackageState.NOT_STOWED
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest test_dotfiles.py::TestDetectState -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Verify against real repo**

Run: `python3 -c "from dotfiles import scan_packages; from pathlib import Path; [print(f'{p.name:20s} {p.pattern.value:8s} {p.state.value}') for p in scan_packages(Path('.')))]"`

Expected: prints all packages with their detected patterns and states matching reality (ghostty=stowed, nvim=stowed, etc.).

- [ ] **Step 6: Commit**

```bash
git add dotfiles.py test_dotfiles.py
git commit -m "feat: add state detection for stow packages"
```

---

### Task 4: Stow and import operations

**Files:**
- Modify: `dotfiles.py`
- Modify: `test_dotfiles.py`

- [ ] **Step 1: Write tests for stow and import**

Append to `test_dotfiles.py`:

```python
from unittest.mock import patch, MagicMock


class TestStowPackage(unittest.TestCase):
    @patch("dotfiles.subprocess.run")
    def test_stow_calls_subprocess(self, mock_run):
        from dotfiles import stow_package
        mock_run.return_value = MagicMock(returncode=0)
        pkg_path = Path("/fake/dotfiles/ghostty")
        dotfiles_root = Path("/fake/dotfiles")
        target = Path("/home/user/.config/ghostty")
        stow_package(pkg_path, target, dotfiles_root, dry_run=False)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "stow")
        self.assertIn("--dotfiles", args)
        self.assertIn("ghostty", args)

    @patch("dotfiles.subprocess.run")
    def test_stow_dry_run_skips(self, mock_run):
        from dotfiles import stow_package
        pkg_path = Path("/fake/dotfiles/ghostty")
        dotfiles_root = Path("/fake/dotfiles")
        target = Path("/home/user/.config/ghostty")
        stow_package(pkg_path, target, dotfiles_root, dry_run=True)
        mock_run.assert_not_called()


class TestImportPackage(unittest.TestCase):
    def test_import_flat(self):
        from dotfiles import import_package, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "ghostty"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            target = Path(tmp) / "target"
            target.mkdir()
            (target / "config").write_text("font-size = 15\n")
            (target / "themes").mkdir()
            (target / "themes" / "dark.conf").write_text("bg=#000\n")

            import_package(pkg, target, PackagePattern.FLAT, dry_run=False)

            self.assertTrue((pkg / "config").exists())
            self.assertTrue((pkg / "themes" / "dark.conf").exists())
            self.assertEqual((pkg / "config").read_text(), "font-size = 15\n")

    def test_import_nested(self):
        from dotfiles import import_package, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "opencode"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            # Real files at target/<subdir>
            target = Path(tmp) / "config_parent"
            target.mkdir()
            subdir = target / "opencode"
            subdir.mkdir()
            (subdir / "opencode.json").write_text("{}\n")

            import_package(pkg, target, PackagePattern.NESTED, dry_run=False,
                           check_paths=[subdir])

            self.assertTrue((pkg / "opencode" / "opencode.json").exists())

    def test_import_dry_run(self):
        from dotfiles import import_package, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "ghostty"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            target = Path(tmp) / "target"
            target.mkdir()
            (target / "config").write_text("content\n")

            import_package(pkg, target, PackagePattern.FLAT, dry_run=True)

            # Nothing should have been copied
            self.assertFalse((pkg / "config").exists())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test_dotfiles.py::TestStowPackage test_dotfiles.py::TestImportPackage -v`
Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Implement stow_package**

Add to `dotfiles.py`:

```python
def stow_package(package_path: Path, target: Path, dotfiles_root: Path,
                 dry_run: bool = False) -> str:
    """Run stow for a package. Returns status message."""
    name = package_path.name
    if dry_run:
        return f"[DRY RUN] Would stow '{name}' → {target}"

    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "stow",
            "-t", str(target),
            "-v", name,
            "--dotfiles",
            "--ignore=^target\\.stowy$",
            "--ignore=\\.DS_Store",
        ],
        cwd=str(dotfiles_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"FAILED stow '{name}': {result.stderr.strip()}"
    return f"Stowed '{name}' → {target}"
```

- [ ] **Step 4: Implement import_package**

Add to `dotfiles.py`:

```python
def import_package(
    package_path: Path,
    target: Path,
    pattern: PackagePattern,
    dry_run: bool = False,
    check_paths: list = None,
) -> list:
    """Copy files from target into the package. Skips files that already
    exist in the package (e.g., already handled by conflict resolution).
    Returns list of copied relative paths."""
    copied = []

    if pattern == PackagePattern.FLAT:
        # Copy all files from target dir into package root
        if not target.exists():
            return copied
        for item in target.rglob("*"):
            if item.is_file() and not item.is_symlink():
                rel = item.relative_to(target)
                dest = package_path / rel
                if dest.exists():
                    continue  # already handled (e.g., conflict resolution)
                if dry_run:
                    copied.append(str(rel))
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                copied.append(str(rel))
    else:
        # Nested: copy each check_path subdir into the package
        paths = check_paths or []
        for cp in paths:
            if not cp.exists() or cp.is_symlink():
                continue
            subdir_name = cp.name
            dest_base = package_path / subdir_name
            for item in cp.rglob("*"):
                if item.is_file() and not item.is_symlink():
                    rel = item.relative_to(cp)
                    dest = dest_base / rel
                    if dest.exists():
                        continue  # already handled (e.g., conflict resolution)
                    if dry_run:
                        copied.append(f"{subdir_name}/{rel}")
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    copied.append(f"{subdir_name}/{rel}")

    return copied
```

- [ ] **Step 5: Implement merge_package**

Add to `dotfiles.py`:

```python
def find_conflicts(package_path: Path, target: Path, pattern: PackagePattern,
                   check_paths: list = None) -> list:
    """Find files that exist in both package and target. Returns list of (relative_path, pkg_file, target_file)."""
    conflicts = []

    if pattern == PackagePattern.FLAT:
        if not target.exists():
            return conflicts
        for item in target.rglob("*"):
            if item.is_file() and not item.is_symlink():
                rel = item.relative_to(target)
                pkg_file = package_path / rel
                if pkg_file.exists() and not pkg_file.is_symlink():
                    conflicts.append((str(rel), pkg_file, item))
    else:
        paths = check_paths or []
        for cp in paths:
            if not cp.exists() or cp.is_symlink():
                continue
            subdir_name = cp.name
            for item in cp.rglob("*"):
                if item.is_file() and not item.is_symlink():
                    rel = item.relative_to(cp)
                    pkg_file = package_path / subdir_name / rel
                    if pkg_file.exists() and not pkg_file.is_symlink():
                        conflicts.append((f"{subdir_name}/{rel}", pkg_file, item))

    return conflicts


def resolve_conflict(pkg_file: Path, target_file: Path, choice: str,
                     dry_run: bool = False) -> str:
    """Apply a conflict resolution. choice is 'local', 'remote', or 'both'."""
    if choice == "local":
        if dry_run:
            return f"[DRY RUN] Keep local: {pkg_file.name}"
        return f"Kept local: {pkg_file.name}"
    elif choice == "remote":
        if dry_run:
            return f"[DRY RUN] Would overwrite with remote: {pkg_file.name}"
        shutil.copy2(target_file, pkg_file)
        return f"Replaced with remote: {pkg_file.name}"
    elif choice == "both":
        backup = pkg_file.with_name(pkg_file.name + ".orig")
        if dry_run:
            return f"[DRY RUN] Would backup {pkg_file.name} → {backup.name}, copy remote"
        shutil.copy2(pkg_file, backup)
        shutil.copy2(target_file, pkg_file)
        return f"Backed up {pkg_file.name} → {backup.name}, copied remote"
    return f"Unknown choice: {choice}"


def remove_target(target_path: Path, dry_run: bool = False) -> str:
    """Remove the real directory at target so stow can create symlinks."""
    if dry_run:
        return f"[DRY RUN] Would remove {target_path}"
    if target_path.exists() and not target_path.is_symlink():
        shutil.rmtree(target_path)
        return f"Removed {target_path}"
    return f"Nothing to remove at {target_path}"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest test_dotfiles.py::TestStowPackage test_dotfiles.py::TestImportPackage -v`
Expected: All 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add dotfiles.py test_dotfiles.py
git commit -m "feat: add stow, import, and merge operations"
```

---

### Task 5: TUI primitives — key input, ANSI helpers, list rendering

**Files:**
- Modify: `dotfiles.py`

- [ ] **Step 1: Add ANSI color helpers and get_key**

Add to `dotfiles.py`:

```python
import tty
import termios


# ---------------------------------------------------------------------------
# TUI — ANSI helpers
# ---------------------------------------------------------------------------

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RED = "\033[31m"
    DIM = "\033[2m"


STATE_COLORS = {
    PackageState.STOWED: Color.GREEN,
    PackageState.NOT_STOWED: Color.YELLOW,
    PackageState.IMPORTABLE: Color.CYAN,
    PackageState.CONFLICT: Color.RED,
}


def clear_screen():
    print("\033[H\033[J", end="")


def get_key() -> str:
    """Read a single keypress. Returns escape sequences for arrow keys."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch
```

- [ ] **Step 2: Add render_list function**

Add to `dotfiles.py`:

```python
def render_list(packages: list, selected: list, cursor: int,
                dry_run: bool = False):
    """Render the package selection list to the terminal."""
    clear_screen()
    term_height = os.get_terminal_size().lines
    header_lines = 3
    footer_lines = 3
    available = term_height - header_lines - footer_lines
    total = len(packages)

    # Header
    title = f"{Color.BOLD}dotfiles manager{Color.RESET}"
    if dry_run:
        title += f"  {Color.YELLOW}[DRY RUN]{Color.RESET}"
    print(title)
    print()

    # Scrolling window
    window_start = max(0, min(cursor - available + 3, total - available))
    window_start = max(0, window_start)
    window_end = min(window_start + available, total)

    for i in range(window_start, window_end):
        pkg = packages[i]
        is_selected = selected[i]
        is_cursor = i == cursor

        marker = ">" if is_cursor else " "
        check = "\u25c9" if is_selected else "\u25cb"  # ◉ or ○
        color = STATE_COLORS.get(pkg.state, Color.RESET)
        state_label = f"{color}[{pkg.state.value}]{Color.RESET}"
        name_pad = pkg.name.ljust(20)

        print(f"  {marker} {check} {name_pad} {state_label}")

    # Footer
    print()
    print(f"  {Color.DIM}\u2191/\u2193 navigate  SPACE toggle  a select all  ENTER confirm  q quit{Color.RESET}")
```

- [ ] **Step 3: Verify rendering manually**

Run: `python3 -c "
from dotfiles import *
pkgs = scan_packages(DOTFILES_ROOT)
selected = [False] * len(pkgs)
render_list(pkgs, selected, 0)
"`

Expected: Prints the formatted package list with color-coded states. Verify visually.

- [ ] **Step 4: Commit**

```bash
git add dotfiles.py
git commit -m "feat: add TUI primitives — key input, ANSI colors, list rendering"
```

---

### Task 6: TUI — main selection screen

**Files:**
- Modify: `dotfiles.py`

- [ ] **Step 1: Implement run_selection_screen**

Add to `dotfiles.py`:

```python
def run_selection_screen(packages: list, dry_run: bool = False) -> list:
    """Interactive selection loop. Returns list of selected Package objects."""
    if not packages:
        print("No packages found.")
        return []

    selected = [False] * len(packages)
    cursor = 0

    while True:
        render_list(packages, selected, cursor, dry_run)
        key = get_key()

        if key == "\x1b[A":  # Up
            cursor = max(0, cursor - 1)
        elif key == "\x1b[B":  # Down
            cursor = min(len(packages) - 1, cursor + 1)
        elif key == " ":  # Space — toggle
            selected[cursor] = not selected[cursor]
        elif key == "a":  # Toggle all
            all_selected = all(selected)
            selected = [not all_selected] * len(packages)
        elif key == "\r":  # Enter — confirm
            break
        elif key == "q" or key == "\x03":  # q or Ctrl+C
            clear_screen()
            print("Cancelled.")
            return []

    clear_screen()
    return [pkg for pkg, sel in zip(packages, selected) if sel]
```

- [ ] **Step 2: Test interactively**

Run: `python3 -c "
from dotfiles import *
pkgs = scan_packages(DOTFILES_ROOT)
result = run_selection_screen(pkgs)
for p in result:
    print(f'Selected: {p.name} [{p.state.value}]')
"`

Manually test: up/down navigation, space to toggle, `a` to select all, enter to confirm, `q` to quit.

- [ ] **Step 3: Commit**

```bash
git add dotfiles.py
git commit -m "feat: add TUI main selection screen"
```

---

### Task 7: TUI — conflict resolution screen

**Files:**
- Modify: `dotfiles.py`

- [ ] **Step 1: Implement run_conflict_screen**

Add to `dotfiles.py`:

```python
def run_conflict_screen(pkg: Package, dry_run: bool = False) -> list:
    """Show conflict resolution for a single package.
    Returns list of (relative_path, choice, pkg_file, target_file) tuples."""
    conflicts = find_conflicts(pkg.path, pkg.target, pkg.pattern, pkg.check_paths)
    if not conflicts:
        return []

    resolutions = []
    clear_screen()
    title = f"{Color.BOLD}Import '{pkg.name}'{Color.RESET} — {len(conflicts)} conflict(s):"
    if dry_run:
        title += f"  {Color.YELLOW}[DRY RUN]{Color.RESET}"
    print(title)
    print()

    for rel_path, pkg_file, target_file in conflicts:
        print(f"  {Color.RED}{rel_path}{Color.RESET}  [local differs from remote]")

    print()
    print(f"  For each file: ({Color.BOLD}l{Color.RESET})ocal / ({Color.BOLD}r{Color.RESET})emote / ({Color.BOLD}b{Color.RESET})oth")
    print()

    for rel_path, pkg_file, target_file in conflicts:
        while True:
            print(f"  {rel_path}: ", end="", flush=True)
            key = get_key()
            if key == "l":
                print("local")
                resolutions.append((rel_path, "local", pkg_file, target_file))
                break
            elif key == "r":
                print("remote")
                resolutions.append((rel_path, "remote", pkg_file, target_file))
                break
            elif key == "b":
                print("both")
                resolutions.append((rel_path, "both", pkg_file, target_file))
                break
            elif key == "\x03":  # Ctrl+C
                print("\nCancelled conflict resolution.")
                return []
            else:
                print()  # ignore invalid key, re-prompt

    return resolutions
```

- [ ] **Step 2: Commit**

```bash
git add dotfiles.py
git commit -m "feat: add TUI conflict resolution screen"
```

---

### Task 8: CLI layer, orchestrator, and main entry point

**Files:**
- Modify: `dotfiles.py`

- [ ] **Step 1: Implement CLI parsing**

Add to `dotfiles.py`:

```python
import argparse


def parse_args(argv: list = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Manage dotfiles packages — stow, import, and resolve conflicts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    return parser.parse_args(argv)
```

- [ ] **Step 2: Implement execute_actions**

Add to `dotfiles.py`:

```python
def execute_actions(packages: list, dotfiles_root: Path, dry_run: bool = False):
    """Execute stow/import actions for selected packages."""
    results = []

    for pkg in packages:
        print(f"\n{Color.BOLD}Processing '{pkg.name}'...{Color.RESET}")

        if pkg.state == PackageState.IMPORTABLE:
            # Import then stow
            copied = import_package(pkg.path, pkg.target, pkg.pattern,
                                    dry_run=dry_run, check_paths=pkg.check_paths)
            for f in copied:
                print(f"  Copied: {f}")
            # Remove original target so stow can create symlinks
            if pkg.pattern == PackagePattern.FLAT:
                msg = remove_target(pkg.target, dry_run=dry_run)
            else:
                for cp in pkg.check_paths:
                    msg = remove_target(cp, dry_run=dry_run)
            print(f"  {msg}")
            msg = stow_package(pkg.path, pkg.target, dotfiles_root, dry_run=dry_run)
            results.append(msg)

        elif pkg.state == PackageState.CONFLICT:
            # Resolve conflicts, import remaining, then stow
            resolutions = run_conflict_screen(pkg, dry_run=dry_run)
            if not resolutions:
                results.append(f"Skipped '{pkg.name}' (conflict resolution cancelled)")
                continue
            for rel_path, choice, pkg_file, target_file in resolutions:
                msg = resolve_conflict(pkg_file, target_file, choice, dry_run=dry_run)
                print(f"  {msg}")
            # Import non-conflicting files
            copied = import_package(pkg.path, pkg.target, pkg.pattern,
                                    dry_run=dry_run, check_paths=pkg.check_paths)
            for f in copied:
                print(f"  Copied: {f}")
            if pkg.pattern == PackagePattern.FLAT:
                msg = remove_target(pkg.target, dry_run=dry_run)
            else:
                for cp in pkg.check_paths:
                    msg = remove_target(cp, dry_run=dry_run)
            print(f"  {msg}")
            msg = stow_package(pkg.path, pkg.target, dotfiles_root, dry_run=dry_run)
            results.append(msg)

        elif pkg.state in (PackageState.STOWED, PackageState.NOT_STOWED):
            # Just (re-)stow
            msg = stow_package(pkg.path, pkg.target, dotfiles_root, dry_run=dry_run)
            results.append(msg)

    # Summary
    print(f"\n{Color.BOLD}Results:{Color.RESET}")
    for r in results:
        print(f"  {r}")
```

- [ ] **Step 3: Implement main**

Add to `dotfiles.py`:

```python
def main(argv: list = None):
    """Entry point: parse args → scan → TUI → execute."""
    args = parse_args(argv)
    dotfiles_root = DOTFILES_ROOT

    packages = scan_packages(dotfiles_root)
    if not packages:
        print("No stowy packages found.")
        return

    selected = run_selection_screen(packages, dry_run=args.dry_run)
    if not selected:
        return

    execute_actions(selected, dotfiles_root, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
```

- [ ] **Step 4: Make the script executable**

Run: `chmod +x dotfiles.py`

- [ ] **Step 5: Run all unit tests**

Run: `python3 -m pytest test_dotfiles.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add dotfiles.py
git commit -m "feat: add CLI, orchestrator, and main entry point"
```

---

### Task 9: End-to-end verification

**Files:**
- No new files

- [ ] **Step 1: Dry-run test against real repo**

Run: `./dotfiles.py --dry-run`

Verify:
1. All packages appear with correct states
2. Up/down navigation works
3. Space toggles, `a` selects all
4. Selecting stowed packages and pressing Enter shows `[DRY RUN] Would stow...`
5. `q` exits cleanly

- [ ] **Step 2: Live stow test — re-stow an already-stowed package**

Run: `./dotfiles.py`

Select a package already in `[stowed]` state (e.g., ghostty). Press Enter.
Verify: stow runs and symlinks remain correct.

Run: `ls -la ~/.config/ghostty/`
Expected: symlinks still point to `~/.dotfiles/ghostty/`.

- [ ] **Step 3: Live stow test — stow a not-stowed package**

If any package shows `[not stowed]`, select it and confirm.
Verify: target dir created, symlinks established.

- [ ] **Step 4: Commit final state**

```bash
git add dotfiles.py test_dotfiles.py
git commit -m "feat: dotfiles.py — consolidated TUI dotfiles manager"
```
