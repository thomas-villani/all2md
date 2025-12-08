"""robots.txt validation and caching for respectful web crawling.

This module provides robots.txt checking functionality that follows RFC 9309
(Robot Exclusion Protocol) to ensure respectful access to web resources.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from all2md.constants import DEFAULT_ROBOTS_TXT_CACHE_DURATION, RobotsTxtPolicy
from all2md.exceptions import NetworkSecurityError, ValidationError

if TYPE_CHECKING:
    from all2md.utils.input_sources import RemoteInputOptions

logger = logging.getLogger(__name__)


@dataclass
class RobotsTxtCacheEntry:
    """Cache entry for a parsed robots.txt file.

    Parameters
    ----------
    parser : RobotFileParser
        Parsed robots.txt file
    timestamp : float
        Unix timestamp when the entry was cached
    fetch_failed : bool
        Whether fetching robots.txt failed (determines allow/disallow behavior)
    status_code : int | None
        HTTP status code from robots.txt fetch (if applicable)

    """

    parser: RobotFileParser
    timestamp: float
    fetch_failed: bool
    status_code: int | None


class RobotsTxtChecker:
    """Thread-safe robots.txt checker with TTL-based caching.

    This class fetches, parses, and caches robots.txt files to determine
    whether a given URL can be accessed according to the robot exclusion
    protocol (RFC 9309).

    Parameters
    ----------
    cache_duration : int
        Cache duration in seconds (default: 3600 = 1 hour)

    Notes
    -----
    - Uses stdlib urllib.robotparser.RobotFileParser for parsing
    - Thread-safe cache with TTL expiration
    - Respects HTTP status codes:
        - 404: Allow all (no robots.txt)
        - 5xx: Temporarily disallow all
        - Timeout/network error: Allow all (per RFC 9309)
    - Special handling for fetching robots.txt itself (bypasses robots.txt check)

    """

    def __init__(self, cache_duration: int = DEFAULT_ROBOTS_TXT_CACHE_DURATION) -> None:
        """Initialize the robots.txt checker."""
        self._cache: dict[str, RobotsTxtCacheEntry] = {}
        self._lock = threading.RLock()
        self._cache_duration = cache_duration

    def _get_robots_txt_url(self, url: str) -> str:
        """Get the robots.txt URL for a given URL.

        Parameters
        ----------
        url : str
            The URL to check

        Returns
        -------
        str
            The robots.txt URL (scheme://host/robots.txt)

        """
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _fetch_robots_txt(self, robots_url: str, remote_options: RemoteInputOptions) -> RobotsTxtCacheEntry:
        """Fetch and parse robots.txt file.

        Parameters
        ----------
        robots_url : str
            URL to robots.txt file
        remote_options : RemoteInputOptions
            Remote input options (used for timeout, user agent, etc.)

        Returns
        -------
        RobotsTxtCacheEntry
            Cache entry with parsed robots.txt or failure information

        """
        from all2md.utils.network_security import fetch_content_securely

        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            # Fetch robots.txt with bypass flag to avoid infinite recursion
            content_bytes = fetch_content_securely(
                url=robots_url,
                allowed_hosts=remote_options.allowed_hosts,
                require_https=remote_options.require_https,
                timeout=remote_options.timeout,
                max_size_bytes=remote_options.max_size_bytes,
                user_agent=remote_options.user_agent,
                bypass_robots_txt=True,
            )

            # Parse the robots.txt content
            robots_txt_content = content_bytes.decode("utf-8", errors="replace")
            parser.parse(robots_txt_content.splitlines())

            logger.debug(f"Successfully fetched and parsed robots.txt from {robots_url}")
            return RobotsTxtCacheEntry(
                parser=parser,
                timestamp=time.time(),
                fetch_failed=False,
                status_code=200,
            )

        except NetworkSecurityError as e:
            # Handle HTTP errors according to RFC 9309
            status_code = getattr(e, "status_code", None)

            if status_code == 404:
                # 404 means no robots.txt, allow all
                logger.debug(f"No robots.txt found at {robots_url} (404), allowing all access")
                parser.allow_all = True  # type: ignore[attr-defined]
                return RobotsTxtCacheEntry(
                    parser=parser,
                    timestamp=time.time(),
                    fetch_failed=False,
                    status_code=404,
                )
            elif status_code and 500 <= status_code < 600:
                # 5xx means temporary error, disallow all temporarily
                logger.warning(
                    f"Server error fetching robots.txt from {robots_url} ({status_code}), temporarily disallowing"
                )
                parser.disallow_all = True  # type: ignore[attr-defined]
                return RobotsTxtCacheEntry(
                    parser=parser,
                    timestamp=time.time(),
                    fetch_failed=True,
                    status_code=status_code,
                )
            else:
                # Other errors (timeout, connection error, etc.), allow per RFC 9309
                logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}, allowing access per RFC 9309")
                parser.allow_all = True  # type: ignore[attr-defined]
                return RobotsTxtCacheEntry(
                    parser=parser,
                    timestamp=time.time(),
                    fetch_failed=True,
                    status_code=status_code,
                )

        except Exception as e:
            # Malformed robots.txt or parsing errors - allow access per RFC 9309
            logger.warning(f"Error parsing robots.txt from {robots_url}: {e}, allowing access")
            parser.allow_all = True  # type: ignore[attr-defined]
            return RobotsTxtCacheEntry(
                parser=parser,
                timestamp=time.time(),
                fetch_failed=True,
                status_code=None,
            )

    def _get_cached_entry(self, robots_url: str, remote_options: RemoteInputOptions) -> RobotsTxtCacheEntry:
        """Get cached robots.txt entry or fetch if expired/missing.

        Parameters
        ----------
        robots_url : str
            URL to robots.txt file
        remote_options : RemoteInputOptions
            Remote input options

        Returns
        -------
        RobotsTxtCacheEntry
            Valid cache entry

        """
        with self._lock:
            # Check if we have a cached entry
            if robots_url in self._cache:
                entry = self._cache[robots_url]
                age = time.time() - entry.timestamp

                # Return cached entry if still valid
                if age < self._cache_duration:
                    logger.debug(f"Using cached robots.txt for {robots_url} (age: {age:.1f}s)")
                    return entry

                logger.debug(f"robots.txt cache expired for {robots_url} (age: {age:.1f}s), refetching")

            # Fetch and cache new entry
            entry = self._fetch_robots_txt(robots_url, remote_options)
            self._cache[robots_url] = entry
            return entry

    def can_fetch(
        self,
        url: str,
        remote_options: RemoteInputOptions,
        policy: RobotsTxtPolicy,
    ) -> tuple[bool, float | None]:
        """Check if a URL can be fetched according to robots.txt and policy.

        Parameters
        ----------
        url : str
            The URL to check
        remote_options : RemoteInputOptions
            Remote input options (contains user_agent, timeout, etc.)
        policy : RobotsTxtPolicy
            Policy for handling robots.txt ("strict", "warn", or "ignore")

        Returns
        -------
        tuple[bool, float | None]
            Tuple of (allowed, crawl_delay)
            - allowed: Whether the URL can be fetched
            - crawl_delay: Crawl delay in seconds (None if not specified)

        Raises
        ------
        ValidationError
            If policy is "strict" and robots.txt disallows the URL

        """
        # If policy is "ignore", skip the check entirely
        if policy == "ignore":
            return True, None

        # Get robots.txt URL
        robots_url = self._get_robots_txt_url(url)

        # Get cached or fetch robots.txt
        entry = self._get_cached_entry(robots_url, remote_options)

        # Check if URL is allowed
        user_agent = remote_options.user_agent
        allowed = entry.parser.can_fetch(user_agent, url)

        # Get crawl delay if specified (typeshed says str|None but it's actually int|None)
        raw_delay = entry.parser.crawl_delay(user_agent)
        crawl_delay: float | None = float(raw_delay) if raw_delay is not None else None

        # Handle policy
        if not allowed:
            msg = f"robots.txt at {robots_url} disallows access to {url} for user-agent '{user_agent}'"
            if policy == "strict":
                logger.error(msg)
                raise ValidationError(msg)
            elif policy == "warn":
                logger.warning(msg)
            # For "ignore" we already returned early above

        return allowed, crawl_delay

    def clear_cache(self) -> None:
        """Clear all cached robots.txt entries."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cleared robots.txt cache")

    def get_cache_size(self) -> int:
        """Get the current cache size.

        Returns
        -------
        int
            Number of cached robots.txt entries

        """
        with self._lock:
            return len(self._cache)


# Global singleton instance
_global_checker: RobotsTxtChecker | None = None
_global_checker_lock = threading.Lock()


def get_global_checker() -> RobotsTxtChecker:
    """Get or create the global robots.txt checker instance.

    Returns
    -------
    RobotsTxtChecker
        The global singleton instance

    """
    global _global_checker
    if _global_checker is None:
        with _global_checker_lock:
            if _global_checker is None:
                _global_checker = RobotsTxtChecker()
    return _global_checker
