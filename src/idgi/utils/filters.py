"""
Filtering utilities for path and file selection.
"""

import fnmatch
import re
from pathlib import Path
from typing import List, Optional, Pattern


class PathFilter:
    """
    Handles filtering of file paths based on include/exclude patterns.
    Supports glob patterns, regex patterns, and directory exclusions.
    """

    DEFAULT_EXCLUDES = [
        # Python cache and build directories
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".mypy_cache",
        ".pytest_cache",
        "*.egg-info",
        "build",
        "dist",
        # Virtual environments
        "venv",
        "env",
        ".env",
        ".venv",
        "virtualenv",
        # Version control
        ".git",
        ".svn",
        ".hg",
        ".bzr",
        # IDE and editor files
        ".vscode",
        ".idea",
        "*.swp",
        "*.swo",
        "*~",
        # OS generated files
        ".DS_Store",
        "Thumbs.db",
        # Common test and documentation directories that might be large
        "node_modules",
        ".tox",
        "htmlcov",
        ".coverage",
    ]

    def __init__(
        self,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        use_default_excludes: bool = True,
    ):
        """
        Initialize the path filter.

        Args:
            exclude_patterns: List of patterns to exclude
            include_patterns: List of patterns to include (if None, includes all)
            use_default_excludes: Whether to use default exclusion patterns
        """
        self.exclude_patterns = []
        self.include_patterns = include_patterns or []

        # Add default excludes
        if use_default_excludes:
            self.exclude_patterns.extend(self.DEFAULT_EXCLUDES)

        # Add user-specified excludes
        if exclude_patterns:
            self.exclude_patterns.extend(exclude_patterns)

        # Compile regex patterns for better performance
        self.exclude_regexes = self._compile_patterns(self.exclude_patterns)
        self.include_regexes = self._compile_patterns(self.include_patterns)

    def _compile_patterns(self, patterns: List[str]) -> List[Pattern[str]]:
        """Compile glob patterns to regex patterns."""
        regex_patterns = []

        for pattern in patterns:
            # Convert glob pattern to regex
            if pattern.startswith("/") and pattern.endswith("/"):
                # Direct regex pattern (enclosed in forward slashes)
                regex_pattern = pattern[1:-1]
            else:
                # Glob pattern - convert to regex
                regex_pattern = fnmatch.translate(pattern)

            try:
                compiled = re.compile(regex_pattern, re.IGNORECASE)
                regex_patterns.append(compiled)
            except re.error:
                # Skip invalid patterns
                continue

        return regex_patterns

    def should_include(self, path: Path) -> bool:
        """
        Determine if a path should be included based on filters.

        Args:
            path: Path to check

        Returns:
            True if path should be included, False otherwise
        """
        path_str = str(path)
        path_name = path.name

        # Check if any part of the path matches exclude patterns
        for exclude_regex in self.exclude_regexes:
            if exclude_regex.search(path_str) or exclude_regex.search(path_name):
                return False

            # Also check individual path parts for directory excludes
            for part in path.parts:
                if exclude_regex.search(part):
                    return False

        # If no include patterns specified, include everything not excluded
        if not self.include_regexes:
            return True

        # Check if path matches any include pattern
        for include_regex in self.include_regexes:
            if include_regex.search(path_str) or include_regex.search(path_name):
                return True

        return False

    def filter_paths(self, paths: List[Path]) -> List[Path]:
        """
        Filter a list of paths.

        Args:
            paths: List of paths to filter

        Returns:
            Filtered list of paths
        """
        return [path for path in paths if self.should_include(path)]

    def should_exclude_directory(self, directory: Path) -> bool:
        """
        Check if an entire directory should be excluded from traversal.
        This is more efficient than checking individual files in large directories.

        Args:
            directory: Directory path to check

        Returns:
            True if directory should be excluded from traversal
        """
        dir_name = directory.name
        dir_path = str(directory)

        for exclude_regex in self.exclude_regexes:
            if exclude_regex.search(dir_name) or exclude_regex.search(dir_path):
                return True

        return False


class ContentFilter:
    """
    Filters based on file content patterns.
    Useful for finding specific code patterns or excluding certain file types.
    """

    def __init__(
        self,
        content_patterns: Optional[List[str]] = None,
        exclude_content_patterns: Optional[List[str]] = None,
        max_file_size: int = 1024 * 1024,  # 1MB default
    ):
        """
        Initialize content filter.

        Args:
            content_patterns: Patterns that must be present in file content
            exclude_content_patterns: Patterns that exclude files if found
            max_file_size: Maximum file size to check (in bytes)
        """
        self.content_patterns = self._compile_patterns(content_patterns or [])
        self.exclude_content_patterns = self._compile_patterns(
            exclude_content_patterns or []
        )
        self.max_file_size = max_file_size

    def _compile_patterns(self, patterns: List[str]) -> List[Pattern[str]]:
        """Compile string patterns to regex."""
        compiled_patterns = []

        for pattern in patterns:
            try:
                compiled = re.compile(pattern, re.MULTILINE)
                compiled_patterns.append(compiled)
            except re.error:
                continue

        return compiled_patterns

    def should_include_file(self, file_path: Path) -> bool:
        """
        Check if a file should be included based on its content.

        Args:
            file_path: Path to the file to check

        Returns:
            True if file should be included
        """
        try:
            # Skip large files
            if file_path.stat().st_size > self.max_file_size:
                return False

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(self.max_file_size)  # Read only first chunk

            # Check exclude patterns first
            for pattern in self.exclude_content_patterns:
                if pattern.search(content):
                    return False

            # If no include patterns, include by default
            if not self.content_patterns:
                return True

            # Check include patterns
            for pattern in self.content_patterns:
                if pattern.search(content):
                    return True

            return False

        except Exception:
            # If we can't read the file, exclude it
            return False
