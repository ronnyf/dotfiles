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


class TestStowTargetName(unittest.TestCase):
    def test_dot_prefix_converted(self):
        from dotfiles import stow_target_name
        self.assertEqual(stow_target_name("dot-zshrc"), ".zshrc")

    def test_dot_prefix_nested(self):
        from dotfiles import stow_target_name
        self.assertEqual(stow_target_name("dot-zshrc.alias"), ".zshrc.alias")

    def test_no_dot_prefix_unchanged(self):
        from dotfiles import stow_target_name
        self.assertEqual(stow_target_name("config"), "config")
        self.assertEqual(stow_target_name("init.lua"), "init.lua")

    def test_dotfile_not_dotprefix(self):
        from dotfiles import stow_target_name
        self.assertEqual(stow_target_name(".gitignore"), ".gitignore")


class TestDetectPattern(unittest.TestCase):
    def test_flat_package(self):
        from dotfiles import detect_pattern, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "ghostty"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("STOWY_TARGET=$HOME/.config/ghostty\n")
            (pkg / "config").write_text("font-size = 15\n")
            result = detect_pattern(pkg)
            self.assertEqual(result, PackagePattern.FLAT)

    def test_nested_package(self):
        from dotfiles import detect_pattern, PackagePattern
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


class TestGetPackageTargetPaths(unittest.TestCase):
    def test_flat_with_dot_prefix(self):
        from dotfiles import get_package_target_paths, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "zshrc"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("STOWY_TARGET=$HOME\n")
            (pkg / "dot-zshrc").write_text("# zsh config\n")
            (pkg / "dot-zshrc.alias").write_text("# aliases\n")
            target = Path(tmp) / "home"

            result = get_package_target_paths(pkg, target, PackagePattern.FLAT)

            self.assertEqual(len(result), 2)
            pkg_files = {r[0].name for r in result}
            target_files = {r[1].name for r in result}
            self.assertEqual(pkg_files, {"dot-zshrc", "dot-zshrc.alias"})
            self.assertEqual(target_files, {".zshrc", ".zshrc.alias"})

    def test_flat_without_dot_prefix(self):
        from dotfiles import get_package_target_paths, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "ghostty"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            (pkg / "config").write_text("font=15\n")
            target = Path(tmp) / "target"

            result = get_package_target_paths(pkg, target, PackagePattern.FLAT)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0].name, "config")
            self.assertEqual(result[0][1].name, "config")

    def test_nested_package(self):
        from dotfiles import get_package_target_paths, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "neovim"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            nvim = pkg / "nvim"
            nvim.mkdir()
            (nvim / "init.lua").write_text("-- nvim\n")
            (nvim / "lua").mkdir()
            (nvim / "lua" / "settings.lua").write_text("-- s\n")
            target = Path(tmp) / "config"

            result = get_package_target_paths(pkg, target, PackagePattern.NESTED)

            pkg_rels = {str(r[0].relative_to(pkg)) for r in result}
            target_rels = {str(r[1].relative_to(target)) for r in result}
            self.assertEqual(pkg_rels, {"nvim/init.lua", "nvim/lua/settings.lua"})
            self.assertEqual(target_rels, {"nvim/init.lua", "nvim/lua/settings.lua"})


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
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir", files={"config": "x"})
            check_paths = [Path(f"{tmp}/target_dir")]
            state = detect_state(pkg, Path(f"{tmp}/target_dir"), PackagePattern.FLAT, check_paths)
            self.assertEqual(state, PackageState.NOT_STOWED)

    def test_stowed_flat(self):
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir", files={"config": "x"})
            target = Path(f"{tmp}/target_dir")
            target.mkdir()
            (target / "config").symlink_to(pkg / "config")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.STOWED)

    def test_stowed_nested_dir_symlink(self):
        from dotfiles import detect_state, PackagePattern, PackageState
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
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir")
            target = Path(f"{tmp}/target_dir")
            target.mkdir()
            (target / "config").write_text("real content")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.IMPORTABLE)

    def test_conflict(self):
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "ghostty", f"{tmp}/target_dir",
                                     files={"config": "local version"})
            target = Path(f"{tmp}/target_dir")
            target.mkdir()
            (target / "config").write_text("remote version")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.CONFLICT)


class TestDetectStateDotPrefix(unittest.TestCase):
    def _make_package(self, tmp, name, target_path, files=None, subdirs=None):
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

    def test_dot_prefix_not_stowed(self):
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "zshrc", f"{tmp}/home",
                                     files={"dot-zshrc": "# config"})
            target = Path(f"{tmp}/home")
            target.mkdir()
            (target / "Documents").mkdir()
            (target / ".bashrc").write_text("# bash")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.NOT_STOWED)

    def test_dot_prefix_conflict(self):
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "zshrc", f"{tmp}/home",
                                     files={"dot-zshrc": "# local config"})
            target = Path(f"{tmp}/home")
            target.mkdir()
            (target / ".zshrc").write_text("# remote config")
            (target / "Documents").mkdir()
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.CONFLICT)

    def test_dot_prefix_stowed(self):
        from dotfiles import detect_state, PackagePattern, PackageState
        with tempfile.TemporaryDirectory() as tmp:
            pkg = self._make_package(tmp, "zshrc", f"{tmp}/home",
                                     files={"dot-zshrc": "# config"})
            target = Path(f"{tmp}/home")
            target.mkdir()
            (target / ".zshrc").symlink_to(pkg / "dot-zshrc")
            state = detect_state(pkg, target, PackagePattern.FLAT, [target])
            self.assertEqual(state, PackageState.STOWED)


from unittest.mock import patch, MagicMock


class TestFindConflictsDotPrefix(unittest.TestCase):
    def test_dot_prefix_conflict_detected(self):
        from dotfiles import find_conflicts, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "zshrc"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            (pkg / "dot-zshrc").write_text("# local")
            target = Path(tmp) / "home"
            target.mkdir()
            (target / ".zshrc").write_text("# remote")
            (target / ".bashrc").write_text("# bash")

            conflicts = find_conflicts(pkg, target, PackagePattern.FLAT)
            self.assertEqual(len(conflicts), 1)
            rel_path, pkg_file, target_file = conflicts[0]
            self.assertEqual(rel_path, "dot-zshrc")
            self.assertEqual(pkg_file, pkg / "dot-zshrc")
            self.assertEqual(target_file, target / ".zshrc")

    def test_no_dot_prefix_still_works(self):
        from dotfiles import find_conflicts, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "ghostty"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            (pkg / "config").write_text("# local")
            target = Path(tmp) / "target"
            target.mkdir()
            (target / "config").write_text("# remote")

            conflicts = find_conflicts(pkg, target, PackagePattern.FLAT)
            self.assertEqual(len(conflicts), 1)
            self.assertEqual(conflicts[0][0], "config")

    def test_no_conflict_when_target_missing(self):
        from dotfiles import find_conflicts, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "zshrc"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            (pkg / "dot-zshrc").write_text("# local")
            target = Path(tmp) / "home"
            target.mkdir()

            conflicts = find_conflicts(pkg, target, PackagePattern.FLAT)
            self.assertEqual(len(conflicts), 0)


class TestPackageFileName(unittest.TestCase):
    def test_dot_prefix_reversed(self):
        from dotfiles import package_file_name
        self.assertEqual(package_file_name(".zshrc"), "dot-zshrc")

    def test_no_dot_prefix_unchanged(self):
        from dotfiles import package_file_name
        self.assertEqual(package_file_name("config"), "config")


class TestImportPackageDotPrefix(unittest.TestCase):
    def test_import_dot_prefix_flat(self):
        """Import translates . prefix to dot- prefix in package"""
        from dotfiles import import_package, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "zshrc"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            target = Path(tmp) / "home"
            target.mkdir()
            (target / ".zshrc").write_text("# my config\n")
            (target / ".zshrc.alias").write_text("# aliases\n")

            copied = import_package(pkg, target, PackagePattern.FLAT)

            self.assertIn("dot-zshrc", copied)
            self.assertIn("dot-zshrc.alias", copied)
            self.assertTrue((pkg / "dot-zshrc").exists())
            self.assertEqual((pkg / "dot-zshrc").read_text(), "# my config\n")
            self.assertTrue((pkg / "dot-zshrc.alias").exists())

    def test_import_skips_existing_dot_prefix(self):
        """Already-resolved files (dot-zshrc exists in pkg) are not re-imported"""
        from dotfiles import import_package, PackagePattern
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "zshrc"
            pkg.mkdir()
            (pkg / "target.stowy").write_text("x\n")
            (pkg / "dot-zshrc").write_text("# local version\n")
            target = Path(tmp) / "home"
            target.mkdir()
            (target / ".zshrc").write_text("# remote version\n")
            (target / ".zshrc.alias").write_text("# aliases\n")

            copied = import_package(pkg, target, PackagePattern.FLAT)

            self.assertNotIn("dot-zshrc", copied)
            self.assertIn("dot-zshrc.alias", copied)
            self.assertEqual((pkg / "dot-zshrc").read_text(), "# local version\n")


class TestStowPackage(unittest.TestCase):
    @patch("dotfiles.subprocess.run")
    def test_stow_calls_subprocess(self, mock_run):
        from dotfiles import stow_package
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            pkg_path = Path(tmp) / "ghostty"
            pkg_path.mkdir()
            dotfiles_root = Path(tmp)
            target = Path(tmp) / "target"
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

            self.assertFalse((pkg / "config").exists())
