"""SQL file loader utility with caching and reload support."""

import os
from pathlib import Path


class SQLLoader:
    """Loads and caches SQL files from a domain's sql directory.

    Features:
    - In-memory caching for performance
    - Reload support for development
    - File modification detection (optional)
    """

    def __init__(
        self, domain: str, base_path: Path | None = None, enable_cache: bool = True
    ) -> None:
        """Initialize SQL loader.

        Args:
            domain: Domain name (e.g., 'users', 'authentication')
            base_path: Base path for domains directory
            enable_cache: Enable in-memory caching (default: True)
        """
        self.domain = domain
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent / "domains"
        self.sql_path = base_path / domain / "sql"
        self.enable_cache = enable_cache
        self._cache: dict[str, str] = {}
        self._mtime_cache: dict[str, float] = {}

    def load(self, filename: str, force_reload: bool = False) -> str:
        """Load a SQL file with optional caching.

        Args:
            filename: SQL file path relative to domain/sql directory
            force_reload: Force reload from disk even if cached

        Returns:
            SQL query string

        Raises:
            FileNotFoundError: If SQL file does not exist
        """
        file_path = self.sql_path / filename

        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        # Check if we should use cache
        if self.enable_cache and not force_reload:
            # Check if file was modified (development mode)
            if self._is_file_modified(file_path):
                # File changed, invalidate cache
                if filename in self._cache:
                    del self._cache[filename]

            # Return cached version if available
            if filename in self._cache:
                return self._cache[filename]

        # Load from disk
        content = file_path.read_text(encoding="utf-8").strip()

        # Cache the content
        if self.enable_cache:
            self._cache[filename] = content
            self._mtime_cache[filename] = file_path.stat().st_mtime

        return content

    def _is_file_modified(self, file_path: Path) -> bool:
        """Check if file was modified since last load.

        Args:
            file_path: Path to SQL file

        Returns:
            True if file was modified
        """
        filename = str(file_path.relative_to(self.sql_path))
        if filename not in self._mtime_cache:
            return True

        current_mtime = file_path.stat().st_mtime
        cached_mtime = self._mtime_cache[filename]
        return current_mtime > cached_mtime

    def load_query(self, filename: str, force_reload: bool = False) -> str:
        """Load a SQL query file from queries/ subdirectory.

        Args:
            filename: Query filename without .sql extension
            force_reload: Force reload from disk

        Returns:
            SQL query string
        """
        return self.load(f"queries/{filename}.sql", force_reload=force_reload)

    def load_command(self, filename: str, force_reload: bool = False) -> str:
        """Load a SQL command file from commands/ subdirectory.

        Args:
            filename: Command filename without .sql extension
            force_reload: Force reload from disk

        Returns:
            SQL command string
        """
        return self.load(f"commands/{filename}.sql", force_reload=force_reload)

    def reload(self, filename: str | None = None) -> None:
        """Reload SQL files from disk.

        Args:
            filename: Specific file to reload, or None to reload all
        """
        if filename is None:
            # Clear entire cache
            self._cache.clear()
            self._mtime_cache.clear()
        else:
            # Clear specific file
            if filename in self._cache:
                del self._cache[filename]
            if filename in self._mtime_cache:
                del self._mtime_cache[filename]

    def clear_cache(self) -> None:
        """Clear all cached SQL queries.

        Useful for testing or when SQL files are updated.
        """
        self._cache.clear()
        self._mtime_cache.clear()

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache size and file count
        """
        return {
            "cached_files": len(self._cache),
            "tracked_files": len(self._mtime_cache),
        }


# Global cache for SQLLoader instances (singleton pattern)
_loader_instances: dict[str, SQLLoader] = {}


def create_sql_loader(domain: str, enable_cache: bool = True) -> SQLLoader:
    """Create or retrieve a cached SQL loader for a specific domain.

    Uses singleton pattern to ensure one loader instance per domain.

    Args:
        domain: Domain name (e.g., 'users', 'authentication')
        enable_cache: Enable SQL query caching (default: True)

    Returns:
        SQLLoader instance for the domain
    """
    # Check if we're in development mode
    os.getenv("ENV", "development") == "development"

    # In development, always use cache but with modification detection
    # In production, always use cache for performance
    cache_key = domain

    if cache_key not in _loader_instances:
        _loader_instances[cache_key] = SQLLoader(domain, enable_cache=enable_cache)

    return _loader_instances[cache_key]


def reload_all_loaders() -> None:
    """Reload all SQL loaders.

    Useful for development when SQL files are updated.
    """
    for loader in _loader_instances.values():
        loader.clear_cache()
