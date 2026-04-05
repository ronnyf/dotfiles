#!/usr/bin/env python3
"""Dotfiles manager — stow, import, and resolve conflicts via TUI."""

import os
import sys
import shutil
import subprocess
import tty
import termios
import argparse
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


# ---------------------------------------------------------------------------
# Core — package scanning
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core — stow, import, merge operations
# ---------------------------------------------------------------------------

def stow_package(package_path: Path, target: Path, dotfiles_root: Path,
                 dry_run: bool = False) -> str:
    """Run stow for a package. Returns status message."""
    name = package_path.name
    if dry_run:
        return f"[DRY RUN] Would stow '{name}' \u2192 {target}"

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
    return f"Stowed '{name}' \u2192 {target}"


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
        if not target.exists():
            return copied
        for item in target.rglob("*"):
            if item.is_file() and not item.is_symlink():
                rel = item.relative_to(target)
                dest = package_path / rel
                if dest.exists():
                    continue
                if dry_run:
                    copied.append(str(rel))
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                copied.append(str(rel))
    else:
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
                        continue
                    if dry_run:
                        copied.append(f"{subdir_name}/{rel}")
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)
                    copied.append(f"{subdir_name}/{rel}")

    return copied


def find_conflicts(package_path: Path, target: Path, pattern: PackagePattern,
                   check_paths: list = None) -> list:
    """Find files that exist in both package and target.
    Returns list of (relative_path, pkg_file, target_file)."""
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
            return f"[DRY RUN] Would backup {pkg_file.name} \u2192 {backup.name}, copy remote"
        shutil.copy2(pkg_file, backup)
        shutil.copy2(target_file, pkg_file)
        return f"Backed up {pkg_file.name} \u2192 {backup.name}, copied remote"
    return f"Unknown choice: {choice}"


def remove_target(target_path: Path, dry_run: bool = False) -> str:
    """Remove the real directory at target so stow can create symlinks."""
    if dry_run:
        return f"[DRY RUN] Would remove {target_path}"
    if target_path.exists() and not target_path.is_symlink():
        shutil.rmtree(target_path)
        return f"Removed {target_path}"
    return f"Nothing to remove at {target_path}"


# ---------------------------------------------------------------------------
# TUI — ANSI helpers and key input
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


def render_list(packages: list, selected: list, cursor: int,
                dry_run: bool = False):
    """Render the package selection list to the terminal."""
    clear_screen()
    try:
        term_height = os.get_terminal_size().lines
    except OSError:
        term_height = 40
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


# ---------------------------------------------------------------------------
# TUI — screens
# ---------------------------------------------------------------------------

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


def run_conflict_screen(pkg: Package, dry_run: bool = False) -> list:
    """Show conflict resolution for a single package.
    Returns list of (relative_path, choice, pkg_file, target_file) tuples."""
    conflicts = find_conflicts(pkg.path, pkg.target, pkg.pattern, pkg.check_paths)
    if not conflicts:
        return []

    resolutions = []
    clear_screen()
    title = f"{Color.BOLD}Import '{pkg.name}'{Color.RESET} \u2014 {len(conflicts)} conflict(s):"
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


# ---------------------------------------------------------------------------
# CLI and orchestrator
# ---------------------------------------------------------------------------

def parse_args(argv: list = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Manage dotfiles packages \u2014 stow, import, and resolve conflicts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    return parser.parse_args(argv)


def execute_actions(packages: list, dotfiles_root: Path, dry_run: bool = False):
    """Execute stow/import actions for selected packages."""
    results = []

    for pkg in packages:
        print(f"\n{Color.BOLD}Processing '{pkg.name}'...{Color.RESET}")

        if pkg.state == PackageState.IMPORTABLE:
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

        elif pkg.state == PackageState.CONFLICT:
            resolutions = run_conflict_screen(pkg, dry_run=dry_run)
            if not resolutions:
                results.append(f"Skipped '{pkg.name}' (conflict resolution cancelled)")
                continue
            for rel_path, choice, pkg_file, target_file in resolutions:
                msg = resolve_conflict(pkg_file, target_file, choice, dry_run=dry_run)
                print(f"  {msg}")
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
            msg = stow_package(pkg.path, pkg.target, dotfiles_root, dry_run=dry_run)
            results.append(msg)

    # Summary
    print(f"\n{Color.BOLD}Results:{Color.RESET}")
    for r in results:
        print(f"  {r}")


def main(argv: list = None):
    """Entry point: parse args \u2192 scan \u2192 TUI \u2192 execute."""
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
