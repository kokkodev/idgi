"""
Tests for the directory scanner module.
"""

import tempfile
from pathlib import Path
from unittest import TestCase

from idgi.core.scanner import DirectoryScanner
from idgi.utils.filters import PathFilter


class TestDirectoryScanner(TestCase):
    """Test cases for DirectoryScanner."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create test directory structure
        (self.temp_dir / "package1").mkdir()
        (self.temp_dir / "package1" / "__init__.py").write_text("# Package 1")
        (self.temp_dir / "package1" / "module1.py").write_text("def func1(): pass")

        (self.temp_dir / "package2").mkdir()
        (self.temp_dir / "package2" / "__init__.py").write_text("# Package 2")
        (self.temp_dir / "package2" / "module2.py").write_text("class Class2: pass")

        # Create some files to exclude
        (self.temp_dir / "venv").mkdir()
        (self.temp_dir / "venv" / "lib.py").write_text("# Should be excluded")

        (self.temp_dir / "__pycache__").mkdir()
        (self.temp_dir / "__pycache__" / "test.pyc").write_text("# Should be excluded")

        # Root level module
        (self.temp_dir / "main.py").write_text('if __name__ == "__main__": pass')

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_basic_scan(self):
        """Test basic directory scanning."""
        scanner = DirectoryScanner()
        result = scanner.scan(self.temp_dir)

        self.assertGreater(len(result.python_files), 0)
        self.assertGreater(result.total_files, 0)
        self.assertGreater(result.total_lines, 0)

    def test_exclusion_patterns(self):
        """Test that exclusion patterns work."""
        scanner = DirectoryScanner(exclude_patterns=["venv", "__pycache__"])
        result = scanner.scan(self.temp_dir)

        # Check that excluded files are not in results
        file_paths = [str(f) for f in result.python_files]
        self.assertFalse(any("venv" in path for path in file_paths))
        self.assertFalse(any("__pycache__" in path for path in file_paths))

    def test_package_analysis(self):
        """Test package structure analysis."""
        scanner = DirectoryScanner()
        result = scanner.scan(self.temp_dir)

        # Should find our test packages
        package_names = set(result.packages.keys())
        self.assertIn("package1", package_names)
        self.assertIn("package2", package_names)

    def test_nonrecursive_scan(self):
        """Test non-recursive scanning."""
        scanner = DirectoryScanner()
        result = scanner.scan(self.temp_dir, recursive=False)

        # Should only find root level files
        file_names = [f.name for f in result.python_files]
        self.assertIn("main.py", file_names)
        self.assertNotIn("module1.py", file_names)  # Should not find nested files

    def test_entry_point_detection(self):
        """Test detection of entry points."""
        scanner = DirectoryScanner()
        result = scanner.scan(self.temp_dir)

        entry_points = scanner.find_entry_points(result.python_files)

        # main.py should be detected as entry point
        entry_names = [ep.name for ep in entry_points]
        self.assertIn("main.py", entry_names)


class TestPathFilter(TestCase):
    """Test cases for PathFilter."""

    def test_default_excludes(self):
        """Test default exclusion patterns."""
        path_filter = PathFilter()

        # Should exclude common patterns
        self.assertFalse(path_filter.should_include(Path("__pycache__/test.pyc")))
        self.assertFalse(path_filter.should_include(Path("venv/lib/python.py")))
        self.assertFalse(path_filter.should_include(Path(".git/config")))

    def test_custom_excludes(self):
        """Test custom exclusion patterns."""
        path_filter = PathFilter(exclude_patterns=["test_*", "*.tmp"])

        self.assertFalse(path_filter.should_include(Path("test_module.py")))
        self.assertFalse(path_filter.should_include(Path("temp.tmp")))
        self.assertTrue(path_filter.should_include(Path("normal_module.py")))

    def test_include_patterns(self):
        """Test inclusion patterns."""
        path_filter = PathFilter(
            include_patterns=["*.py"], exclude_patterns=[], use_default_excludes=False
        )

        self.assertTrue(path_filter.should_include(Path("module.py")))
        self.assertFalse(path_filter.should_include(Path("module.txt")))

    def test_directory_exclusion(self):
        """Test directory-level exclusion."""
        path_filter = PathFilter(exclude_patterns=["test_dir"])

        test_dir = Path("test_dir")
        self.assertTrue(path_filter.should_exclude_directory(test_dir))
