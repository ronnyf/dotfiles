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


from unittest.mock import patch, MagicMock


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
