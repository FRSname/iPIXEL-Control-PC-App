"""
Base class for API data fetching services.

Provides a common pattern for fetching data from external APIs in background
threads with proper error handling and UI updates.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional
import threading
import tkinter as tk


class APIFetcher(ABC):
    """
    Abstract base class for API data fetching.

    Encapsulates the threading pattern used by Stock, YouTube, and Weather
    services. Each subclass implements _fetch_data_impl() with the specific
    API logic.

    Features:
    - Background thread execution
    - Thread-safe UI updates via root.after()
    - Consistent error handling
    - Prevents concurrent fetches
    - Callback-based result handling

    Usage:
        class MyService(APIFetcher):
            def _fetch_data_impl(self) -> Dict:
                return call_my_api(self._params['key'])

        service = MyService(root, on_success, on_error)
        service.fetch(key="value")
    """

    def __init__(
        self,
        root: tk.Tk,
        on_success: Callable[[Dict[str, Any]], None],
        on_error: Callable[[str], None],
        on_start: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the API fetcher.

        Args:
            root: Tkinter root window for thread-safe callbacks
            on_success: Callback when data is fetched successfully
            on_error: Callback when an error occurs
            on_start: Optional callback when fetch starts
        """
        self._root = root
        self._on_success = on_success
        self._on_error = on_error
        self._on_start = on_start
        self._is_fetching = False
        self._params: Dict[str, Any] = {}

    @property
    def is_fetching(self) -> bool:
        """Check if a fetch is currently in progress."""
        return self._is_fetching

    @abstractmethod
    def _fetch_data_impl(self) -> Dict[str, Any]:
        """
        Implement the actual API call.

        This method runs in a background thread. Access parameters via
        self._params.

        Returns:
            Dictionary containing the fetched data

        Raises:
            Any exception to trigger the error callback
        """
        pass

    def fetch(self, **params) -> bool:
        """
        Start fetching data in a background thread.

        Args:
            **params: Parameters to pass to _fetch_data_impl via self._params

        Returns:
            True if fetch started, False if already fetching
        """
        if self._is_fetching:
            return False

        self._is_fetching = True
        self._params = params

        # Notify start
        if self._on_start:
            self._on_start()

        def fetch_task():
            try:
                data = self._fetch_data_impl()
                self._root.after(0, lambda: self._handle_success(data))
            except ImportError as e:
                self._root.after(0, lambda: self._handle_error(f"Missing library: {e}"))
            except Exception as e:
                self._root.after(0, lambda: self._handle_error(str(e)))

        thread = threading.Thread(target=fetch_task, daemon=True)
        thread.start()
        return True

    def _handle_success(self, data: Dict[str, Any]) -> None:
        """Handle successful fetch."""
        self._is_fetching = False
        self._on_success(data)

    def _handle_error(self, message: str) -> None:
        """Handle fetch error."""
        self._is_fetching = False
        self._on_error(message)

    def cancel(self) -> None:
        """
        Cancel the current fetch.

        Note: This doesn't actually stop the background thread, but it
        prevents the callbacks from being called.
        """
        self._is_fetching = False


class CachingAPIFetcher(APIFetcher):
    """
    API fetcher with result caching.

    Extends APIFetcher to cache results and optionally return cached data
    while fetching fresh data.
    """

    def __init__(
        self,
        root: tk.Tk,
        on_success: Callable[[Dict[str, Any]], None],
        on_error: Callable[[str], None],
        on_start: Optional[Callable[[], None]] = None,
        cache_ttl_seconds: int = 60
    ):
        super().__init__(root, on_success, on_error, on_start)
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_key: Optional[str] = None
        self._cache_time: float = 0
        self._cache_ttl = cache_ttl_seconds

    def _get_cache_key(self) -> str:
        """Generate a cache key from current params."""
        return str(sorted(self._params.items()))

    def get_cached(self) -> Optional[Dict[str, Any]]:
        """Get cached data if available and not expired."""
        import time
        if self._cache is None:
            return None
        if time.time() - self._cache_time > self._cache_ttl:
            return None
        if self._get_cache_key() != self._cache_key:
            return None
        return self._cache

    def _handle_success(self, data: Dict[str, Any]) -> None:
        """Handle success and update cache."""
        import time
        self._cache = data
        self._cache_key = self._get_cache_key()
        self._cache_time = time.time()
        super()._handle_success(data)

    def clear_cache(self) -> None:
        """Clear the cached data."""
        self._cache = None
        self._cache_key = None
        self._cache_time = 0
