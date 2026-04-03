#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path
from subprocess import run

DOTFILES_ROOT = Path.home() / ".dotfiles"
CONFIG_ROOT = Path.home() / ".config"


def is_directory_managed(dir_name: str) -> bool:
    """Check if directory is already a stowy package with symlinks."""
    package_path = DOTFILES_ROOT / dir_name
    if not package_path.exists():
        return False
    
    target_file = package_path / "target.stowy"
    if not target_file.exists():
        return False
    
    target_line = target_file.read_text().strip()
    if not target_line.startswith("STOWY_TARGET="):
        return False
    
    target_path = Path(target_line.split("=", 1)[1]).expanduser()
    if not target_path.exists():
        return False
    
    for item in target_path.iterdir():
        if item.is_symlink():
            target = item.resolve()
            if str(DOTFILES_ROOT) in str(target):
                return True
    
    return False


def find_directories_to_import() -> list:
    """Find directories in ~/.config that need to be imported."""
    to_import = []
    
    if not CONFIG_ROOT.exists():
        print(f"Error: {CONFIG_ROOT} does not exist")
        return to_import
    
    for item in sorted(CONFIG_ROOT.iterdir()):
        if not item.is_dir():
            continue
        
        if item.is_symlink():
            continue
        
        dir_name = item.name
        
        if is_directory_managed(dir_name):
            continue
        
        package_path = DOTFILES_ROOT / dir_name
        target_file = package_path / "target.stowy"
        if not target_file.exists():
            continue
        
        has_content = any(item.rglob("*"))
        if not has_content:
            continue
        
        to_import.append(dir_name)
    
    return to_import


def count_files(path: Path) -> int:
    """Count files in a directory."""
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
    return count


def count_files(path: Path) -> int:
    """Count files in a directory."""
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
    return count


def prompt_action(dir_name: str, is_new: bool = True) -> str:
    """Prompt user for action on a directory. Returns 'skip', 'replace', or 'merge'."""
    if is_new:
        prompt = f"Import '{dir_name}'? (y/n): "
    else:
        prompt = f"Package '{dir_name}' has content. Action? (s=skip/r=replace/m=merge): "
    
    while True:
        response = input(prompt).strip().lower()
        if is_new:
            if response in ('y', 'yes'):
                return 'import'
            elif response in ('n', 'no', 'skip'):
                return 'skip'
        else:
            if response in ('s', 'skip'):
                return 'skip'
            elif response in ('r', 'replace'):
                return 'replace'
            elif response in ('m', 'merge'):
                return 'merge'
        print("Please enter: y/n" if is_new else "s=skip/r=replace/m=merge")


def prompt_conflict(local_path: str, remote_path: str, auto_resolve: bool = False) -> str:
    """Prompt for conflict resolution. Returns 'local', 'remote', or 'both'."""
    if auto_resolve:
        # When --yes is used, prefer remote (current config) for conflicts
        print(f"Conflict: {local_path} -> Using remote (current config)")
        return 'remote'
    
    prompt = f"Conflict: {local_path}\nKeep (l)ocal / (r)emote / (b)oth? "
    
    while True:
        response = input(prompt).strip().lower()
        if response in ('l', 'local'):
            return 'local'
        elif response in ('r', 'remote'):
            return 'remote'
        elif response in ('b', 'both'):
            return 'both'
        print("Please enter: l/r/b")


def create_package_structure(dir_name: str, dry_run: bool = False) -> Path:
    """Create package directory and target.stowy. Returns package path."""
    package_path = DOTFILES_ROOT / dir_name
    
    if not dry_run:
        package_path.mkdir(parents=True, exist_ok=True)
    
    target_path = CONFIG_ROOT / dir_name
    target_stowy = package_path / "target.stowy"
    
    if not dry_run and not target_stowy.exists():
        target_stowy.write_text(f"STOWY_TARGET={target_path}\n")
    
    return package_path


def copy_directory_content(source: Path, dest: Path, dry_run: bool = False) -> list:
    """Copy all files from source to dest. Returns list of copied files."""
    copied = []
    
    for item in source.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(source)
            dest_path = dest / rel_path
            
            if not dry_run:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)
            
            copied.append(str(rel_path))
    
    return copied


def merge_directory(source: Path, dest: Path, dry_run: bool = False) -> tuple:
    """Merge source into dest, handling conflicts. Returns (copied, conflicts)."""
    copied = []
    conflicts = []
    
    for item in source.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(source)
            dest_path = dest / rel_path
            
            if dest_path.exists() and not dest_path.is_symlink():
                conflicts.append(str(rel_path))
            else:
                if not dry_run:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_path)
                copied.append(str(rel_path))
    
    return copied, conflicts


def run_stow(package_name: str, dry_run: bool = False) -> bool:
    """Run stow to create symlinks for a package."""
    cmd = ["stow", "-t", str(CONFIG_ROOT), "-v", package_name, "--dotfiles", "--ignore=^target\\.stowy$", "--ignore=\\.DS_Store"]
    
    if dry_run:
        print(f"  Would run: {' '.join(cmd)}")
        return True
    
    result = run(cmd, cwd=str(DOTFILES_ROOT), capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"  Stow successful")
        return True
    else:
        print(f"  Stow failed: {result.stderr}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import config directories into dotfiles")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()
    
    print("Scanning ~/.config for directories to import...")
    directories = find_directories_to_import()
    
    if not directories:
        print("No directories found that need importing.")
        return
    
    print(f"\nFound {len(directories)} directory(s) to import:")
    for dir_name in directories:
        print(f"  - {dir_name}")
    
    if args.yes:
        actions = {dir_name: 'import' for dir_name in directories}
    else:
        actions = {}
        for dir_name in directories:
            action = prompt_action(dir_name, is_new=True)
            actions[dir_name] = action
    
    print("\nSummary:")
    for dir_name, action in actions.items():
        print(f"  {dir_name}: {action}")
    
    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return
    
    if not args.yes:
        confirm = input("\nProceed with import? (y/n): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("Aborted.")
            return
    
    for dir_name, action in actions.items():
        if action == 'skip':
            print(f"\nSkipping {dir_name}")
            continue
        
        print(f"\nProcessing {dir_name}...")
        package_path = create_package_structure(dir_name, dry_run=False)
        
        source_dir = CONFIG_ROOT / dir_name
        
        if action == 'replace':
            for item in package_path.iterdir():
                if item.is_file():
                    if not args.dry_run:
                        item.unlink()
            
            copied = copy_directory_content(source_dir, package_path, dry_run=False)
        else:  # merge
            copied, conflicts = merge_directory(source_dir, package_path, dry_run=False)
            
            if conflicts:
                print(f"  Found {len(conflicts)} conflict(s):")
                for conflict in conflicts:
                    print(f"    - {conflict}")
                
                for conflict in conflicts:
                    dest_file = package_path / conflict
                    source_file = source_dir / conflict
                    
                    choice = prompt_conflict(str(dest_file), str(source_file), auto_resolve=args.yes)
                    
                    if choice == 'local':
                        pass
                    elif choice == 'remote':
                        if not args.dry_run:
                            shutil.copy2(source_file, dest_file)
                    elif choice == 'both':
                        backup = dest_file.with_name(dest_file.name + ".orig")
                        if not args.dry_run:
                            shutil.copy2(dest_file, backup)
                            shutil.copy2(source_file, dest_file)
                        print(f"    -> Kept both (backup: {backup.name})")
        
        print(f"  Copied {len(copied)} file(s)")
        for f in copied:
            print(f"    - {f}")
        
        run_stow(dir_name, dry_run=False)
    
    print("\nImport complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
