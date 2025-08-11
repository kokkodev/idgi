"""
Directory and file scanning functionality for Python codebases.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from ..utils.filters import PathFilter


@dataclass
class ScanResult:
    """Result of scanning a directory."""

    python_files: List[Path]
    packages: Dict[str, List[Path]]  # package_name -> list of module files
    total_files: int
    total_lines: int
    errors: List[Tuple[Path, str]]  # (file_path, error_message)


class DirectoryScanner:
    """
    Efficiently scans directories for Python files and packages.
    Handles large codebases with 5,000+ files.
    """

    def __init__(
        self,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        max_workers: int = 4,
    ):
        """
        Initialize the scanner.

        Args:
            exclude_patterns: Patterns to exclude (e.g., ['venv', '*.pyc', '__pycache__'])
            include_patterns: Patterns to include (e.g., ['*.py'])
            max_workers: Maximum number of worker processes for parallel processing
        """
        self.path_filter = PathFilter(exclude_patterns, include_patterns)
        self.max_workers = max_workers

    def scan(self, root_path: Path, recursive: bool = True) -> ScanResult:
        """
        Scan a directory for Python files and packages.

        Args:
            root_path: Root directory to scan
            recursive: Whether to scan recursively

        Returns:
            ScanResult containing discovered files and packages
        """
        root_path = Path(root_path).resolve()

        if not root_path.exists():
            raise FileNotFoundError(f"Directory not found: {root_path}")

        if not root_path.is_dir():
            raise ValueError(f"Path is not a directory: {root_path}")

        # Find all Python files
        python_files = list(self._find_python_files(root_path, recursive))

        # Analyze packages
        packages = self._analyze_packages(python_files, root_path)

        # Count lines in parallel for large codebases
        total_lines, errors = self._count_lines_parallel(python_files)

        return ScanResult(
            python_files=python_files,
            packages=packages,
            total_files=len(python_files),
            total_lines=total_lines,
            errors=errors,
        )

    def _find_python_files(
        self, root_path: Path, recursive: bool
    ) -> Generator[Path, None, None]:
        """Find all Python files in the directory."""
        if recursive:
            pattern = "**/*.py"
        else:
            pattern = "*.py"

        for file_path in root_path.glob(pattern):
            if self.path_filter.should_include(file_path):
                yield file_path

    def _analyze_packages(
        self, python_files: List[Path], root_path: Path
    ) -> Dict[str, List[Path]]:
        """
        Analyze Python files to identify packages and modules.

        Returns:
            Dictionary mapping package names to lists of module files
        """
        packages: Dict[str, List[Path]] = {}

        for file_path in python_files:
            try:
                relative_path = file_path.relative_to(root_path)

                # Get package path by removing the file name
                if relative_path.name == "__init__.py":
                    # This is a package __init__.py file
                    package_parts = relative_path.parent.parts
                else:
                    # This is a module file
                    package_parts = relative_path.parent.parts

                if package_parts:
                    package_name = ".".join(package_parts)
                else:
                    package_name = "."  # Root level modules

                if package_name not in packages:
                    packages[package_name] = []

                packages[package_name].append(file_path)

            except ValueError:
                # File is outside root_path, skip
                continue

        return packages

    def _count_lines_parallel(
        self, python_files: List[Path]
    ) -> Tuple[int, List[Tuple[Path, str]]]:
        """
        Count lines in Python files using parallel processing.

        Returns:
            Tuple of (total_lines, errors)
        """
        total_lines = 0
        errors = []

        # For small numbers of files, don't use parallelization
        if len(python_files) < 50:
            for file_path in python_files:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        total_lines += sum(1 for _ in f)
                except Exception as e:
                    errors.append((file_path, str(e)))
            return total_lines, errors

        # Use ThreadPoolExecutor for I/O bound operations
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self._count_file_lines, file_path): file_path
                for file_path in python_files
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    lines = future.result()
                    total_lines += lines
                except Exception as e:
                    errors.append((file_path, str(e)))

        return total_lines, errors

    @staticmethod
    def _count_file_lines(file_path: Path) -> int:
        """Count lines in a single file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def get_package_hierarchy(self, packages: Dict[str, List[Path]]) -> Dict[str, Dict]:
        """
        Build a hierarchical representation of packages.

        Args:
            packages: Package dictionary from scan results

        Returns:
            Nested dictionary representing package hierarchy
        """
        hierarchy = {}

        for package_name in packages.keys():
            if package_name == ".":
                continue

            parts = package_name.split(".")
            current = hierarchy

            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]

        return hierarchy

    def find_entry_points(self, python_files: List[Path]) -> List[Path]:
        """
        Find potential entry points (files with __main__ or main functions).

        Args:
            python_files: List of Python files to analyze

        Returns:
            List of files that appear to be entry points
        """
        entry_points = []
        main_patterns = [
            re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']'),
            re.compile(r"def\s+main\s*\("),
        ]

        for file_path in python_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for pattern in main_patterns:
                    if pattern.search(content):
                        entry_points.append(file_path)
                        break

            except Exception:
                continue

        return entry_points
