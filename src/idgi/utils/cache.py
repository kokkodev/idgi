"""
Caching utilities for performance optimization with large codebases.
"""

import hashlib
import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.analyzer import AnalysisResult


class FileSystemCache:
    """
    File system-based cache for analysis results and parsed data.
    Helps avoid reprocessing large codebases when files haven't changed.
    """

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the cache.

        Args:
            cache_dir: Directory to store cache files (default: ~/.idgi_cache)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".idgi_cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_metadata(self) -> None:
        """Save cache metadata."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception:
            pass

    def _get_cache_key(self, root_path: Path, exclude_patterns: List[str]) -> str:
        """Generate cache key for a codebase analysis."""
        # Include root path and exclude patterns in key
        key_data = {
            "root_path": str(root_path),
            "exclude_patterns": sorted(exclude_patterns or []),
        }

        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _get_codebase_fingerprint(self, root_path: Path) -> Dict[str, Any]:
        """Generate fingerprint of codebase for cache validation."""
        fingerprint = {
            "files": {},
            "total_files": 0,
            "total_size": 0,
            "last_modified": 0,
        }

        try:
            for py_file in root_path.rglob("*.py"):
                if py_file.is_file():
                    stat = py_file.stat()
                    relative_path = str(py_file.relative_to(root_path))

                    fingerprint["files"][relative_path] = {
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }

                    fingerprint["total_files"] += 1
                    fingerprint["total_size"] += stat.st_size
                    fingerprint["last_modified"] = max(
                        fingerprint["last_modified"], stat.st_mtime
                    )

        except Exception:
            # If we can't generate fingerprint, return empty one
            pass

        return fingerprint

    def get_analysis_result(
        self, root_path: Path, exclude_patterns: Optional[List[str]] = None
    ) -> Optional[AnalysisResult]:
        """
        Get cached analysis result if available and valid.

        Args:
            root_path: Root path that was analyzed
            exclude_patterns: Exclude patterns used in analysis

        Returns:
            Cached AnalysisResult if valid, None if cache miss or invalid
        """
        cache_key = self._get_cache_key(root_path, exclude_patterns or [])
        cache_file = self.cache_dir / f"analysis_{cache_key}.pkl"

        if not cache_file.exists():
            return None

        # Check if cache is still valid
        if not self._is_cache_valid(cache_key, root_path):
            # Clean up invalid cache
            try:
                cache_file.unlink()
            except Exception:
                pass
            return None

        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            # Cache file corrupted, remove it
            try:
                cache_file.unlink()
            except Exception:
                pass
            return None

    def store_analysis_result(
        self,
        root_path: Path,
        analysis_result: AnalysisResult,
        exclude_patterns: Optional[List[str]] = None,
    ) -> bool:
        """
        Store analysis result in cache.

        Args:
            root_path: Root path that was analyzed
            analysis_result: Analysis result to cache
            exclude_patterns: Exclude patterns used in analysis

        Returns:
            True if stored successfully, False otherwise
        """
        cache_key = self._get_cache_key(root_path, exclude_patterns or [])
        cache_file = self.cache_dir / f"analysis_{cache_key}.pkl"

        try:
            # Store the analysis result
            with open(cache_file, "wb") as f:
                pickle.dump(analysis_result, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Update metadata
            fingerprint = self._get_codebase_fingerprint(root_path)
            self.metadata[cache_key] = {
                "root_path": str(root_path),
                "exclude_patterns": exclude_patterns or [],
                "fingerprint": fingerprint,
                "cached_at": time.time(),
                "cache_file": str(cache_file),
            }

            self._save_metadata()
            return True

        except Exception:
            return False

    def _is_cache_valid(self, cache_key: str, root_path: Path) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self.metadata:
            return False

        cached_info = self.metadata[cache_key]

        # Check if root path matches
        if cached_info.get("root_path") != str(root_path):
            return False

        # Check age (invalidate after 24 hours by default)
        cached_at = cached_info.get("cached_at", 0)
        max_age = 24 * 60 * 60  # 24 hours in seconds

        if time.time() - cached_at > max_age:
            return False

        # Check if codebase has changed
        current_fingerprint = self._get_codebase_fingerprint(root_path)
        cached_fingerprint = cached_info.get("fingerprint", {})

        # Compare total files and last modified time for quick check
        if current_fingerprint.get("total_files") != cached_fingerprint.get(
            "total_files"
        ) or current_fingerprint.get("last_modified") > cached_fingerprint.get(
            "last_modified", 0
        ):
            return False

        # For more thorough check, compare file-level changes
        current_files = current_fingerprint.get("files", {})
        cached_files = cached_fingerprint.get("files", {})

        # Quick check: if file counts differ, cache is invalid
        if len(current_files) != len(cached_files):
            return False

        # Check a sample of files (for performance with large codebases)
        files_to_check = list(current_files.keys())[:100]  # Check first 100 files

        for file_path in files_to_check:
            if file_path not in cached_files:
                return False

            current_file_info = current_files[file_path]
            cached_file_info = cached_files[file_path]

            if current_file_info.get("mtime", 0) != cached_file_info.get(
                "mtime", 0
            ) or current_file_info.get("size", 0) != cached_file_info.get("size", 0):
                return False

        return True

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cache files.

        Args:
            older_than_days: Only clear files older than this many days (None = clear all)

        Returns:
            Number of files removed
        """
        removed_count = 0
        current_time = time.time()

        # Clean cache files
        for cache_file in self.cache_dir.glob("analysis_*.pkl"):
            should_remove = False

            if older_than_days is None:
                should_remove = True
            else:
                try:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > (older_than_days * 24 * 60 * 60):
                        should_remove = True
                except Exception:
                    should_remove = True

            if should_remove:
                try:
                    cache_file.unlink()
                    removed_count += 1
                except Exception:
                    pass

        # Clean metadata
        if older_than_days is None:
            self.metadata.clear()
        else:
            cutoff_time = current_time - (older_than_days * 24 * 60 * 60)
            keys_to_remove = []

            for key, info in self.metadata.items():
                if info.get("cached_at", 0) < cutoff_time:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.metadata[key]

        self._save_metadata()
        return removed_count

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the cache."""
        cache_files = list(self.cache_dir.glob("analysis_*.pkl"))

        total_size = 0
        oldest_cache = None
        newest_cache = None

        for cache_file in cache_files:
            try:
                stat = cache_file.stat()
                total_size += stat.st_size

                if oldest_cache is None or stat.st_mtime < oldest_cache:
                    oldest_cache = stat.st_mtime

                if newest_cache is None or stat.st_mtime > newest_cache:
                    newest_cache = stat.st_mtime

            except Exception:
                continue

        return {
            "cache_dir": str(self.cache_dir),
            "total_entries": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "oldest_cache": oldest_cache,
            "newest_cache": newest_cache,
        }


class InMemoryCache:
    """
    In-memory cache for frequently accessed data during a single session.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize in-memory cache.

        Args:
            max_size: Maximum number of items to keep in cache
        """
        self.max_size = max_size
        self.cache: Dict[str, Any] = {}
        self.access_times: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        if key in self.cache:
            self.access_times[key] = time.time()
            return self.cache[key]
        return None

    def put(self, key: str, value: Any) -> None:
        """Put item in cache."""
        current_time = time.time()

        # If cache is full, remove oldest item
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_oldest()

        self.cache[key] = value
        self.access_times[key] = current_time

    def _evict_oldest(self) -> None:
        """Remove the oldest (least recently used) item."""
        if not self.access_times:
            return

        oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])

        del self.cache[oldest_key]
        del self.access_times[oldest_key]

    def clear(self) -> None:
        """Clear all cached items."""
        self.cache.clear()
        self.access_times.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


# Global cache instances
_fs_cache: Optional[FileSystemCache] = None
_memory_cache: Optional[InMemoryCache] = None


def get_filesystem_cache() -> FileSystemCache:
    """Get global filesystem cache instance."""
    global _fs_cache
    if _fs_cache is None:
        _fs_cache = FileSystemCache()
    return _fs_cache


def get_memory_cache() -> InMemoryCache:
    """Get global in-memory cache instance."""
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = InMemoryCache()
    return _memory_cache


def clear_all_caches() -> Dict[str, int]:
    """Clear all caches and return statistics."""
    global _fs_cache, _memory_cache

    results = {}

    # Clear filesystem cache
    if _fs_cache is not None:
        results["filesystem_removed"] = _fs_cache.clear_cache()
        _fs_cache = None
    else:
        results["filesystem_removed"] = 0

    # Clear memory cache
    if _memory_cache is not None:
        results["memory_size"] = _memory_cache.size()
        _memory_cache.clear()
        _memory_cache = None
    else:
        results["memory_size"] = 0

    return results
