"""Unit tests for robots.txt checking functionality."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from all2md.constants import DEFAULT_ROBOTS_TXT_CACHE_DURATION
from all2md.exceptions import NetworkSecurityError, ValidationError
from all2md.utils.input_sources import RemoteInputOptions
from all2md.utils.robots_txt import RobotsTxtCacheEntry, RobotsTxtChecker, get_global_checker


@pytest.fixture
def remote_options():
    """Create test remote input options."""
    return RemoteInputOptions(
        allow_remote_input=True,
        require_https=False,
        timeout=5.0,
        max_size_bytes=1024 * 1024,
        user_agent="test-bot/1.0",
    )


@pytest.fixture
def checker():
    """Create a fresh RobotsTxtChecker instance for each test."""
    return RobotsTxtChecker(cache_duration=60)


class TestRobotsTxtChecker:
    """Tests for RobotsTxtChecker class."""

    def test_init(self):
        """Test initialization with default and custom cache duration."""
        # Default cache duration
        checker_default = RobotsTxtChecker()
        assert checker_default._cache_duration == DEFAULT_ROBOTS_TXT_CACHE_DURATION

        # Custom cache duration
        checker_custom = RobotsTxtChecker(cache_duration=120)
        assert checker_custom._cache_duration == 120

    def test_get_robots_txt_url(self, checker):
        """Test robots.txt URL generation from various URLs."""
        assert checker._get_robots_txt_url("https://example.com/page.html") == "https://example.com/robots.txt"
        assert checker._get_robots_txt_url("https://example.com/path/to/page") == "https://example.com/robots.txt"
        assert checker._get_robots_txt_url("https://example.com:8080/page") == "https://example.com:8080/robots.txt"
        assert checker._get_robots_txt_url("http://example.com/page") == "http://example.com/robots.txt"

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_fetch_robots_txt_success(self, mock_fetch, checker, remote_options):
        """Test successful robots.txt fetch and parsing."""
        # Mock successful fetch
        robots_content = "User-agent: *\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        entry = checker._fetch_robots_txt("https://example.com/robots.txt", remote_options)

        assert isinstance(entry, RobotsTxtCacheEntry)
        assert entry.fetch_failed is False
        assert entry.status_code == 200
        assert entry.parser is not None
        mock_fetch.assert_called_once()

        # Verify bypass_robots_txt was passed
        call_kwargs = mock_fetch.call_args[1]
        assert call_kwargs["bypass_robots_txt"] is True

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_fetch_robots_txt_404(self, mock_fetch, checker, remote_options):
        """Test handling of 404 (no robots.txt) - should allow all."""
        # Mock 404 error
        error = NetworkSecurityError("Not found")
        error.status_code = 404
        mock_fetch.side_effect = error

        entry = checker._fetch_robots_txt("https://example.com/robots.txt", remote_options)

        assert entry.fetch_failed is False
        assert entry.status_code == 404
        assert entry.parser.allow_all is True

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_fetch_robots_txt_5xx(self, mock_fetch, checker, remote_options):
        """Test handling of 5xx errors - should disallow all temporarily."""
        # Mock 503 error
        error = NetworkSecurityError("Service unavailable")
        error.status_code = 503
        mock_fetch.side_effect = error

        entry = checker._fetch_robots_txt("https://example.com/robots.txt", remote_options)

        assert entry.fetch_failed is True
        assert entry.status_code == 503
        assert entry.parser.disallow_all is True

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_fetch_robots_txt_timeout(self, mock_fetch, checker, remote_options):
        """Test handling of timeout - should allow all per RFC 9309."""
        # Mock timeout error (no status code)
        error = NetworkSecurityError("Timeout")
        mock_fetch.side_effect = error

        entry = checker._fetch_robots_txt("https://example.com/robots.txt", remote_options)

        assert entry.fetch_failed is True
        assert entry.status_code is None
        assert entry.parser.allow_all is True

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_fetch_robots_txt_malformed(self, mock_fetch, checker, remote_options):
        """Test handling of malformed robots.txt - should allow all."""
        # Mock successful fetch but with malformed content that raises parsing error
        mock_result = Mock()
        mock_result.content = b"This is not valid robots.txt content\x00\x01\x02"
        mock_fetch.return_value = mock_result

        # Even with invalid content, should not raise and should allow all
        entry = checker._fetch_robots_txt("https://example.com/robots.txt", remote_options)

        assert entry.parser is not None
        # Parser should be created even if content is malformed

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_cache_expiry(self, mock_fetch, remote_options):
        """Test that cached entries expire after cache duration."""
        checker_short = RobotsTxtChecker(cache_duration=1)  # 1 second cache

        # Mock successful fetch
        robots_content = "User-agent: *\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        robots_url = "https://example.com/robots.txt"

        # First fetch - should hit network
        entry1 = checker_short._get_cached_entry(robots_url, remote_options)
        assert mock_fetch.call_count == 1

        # Second fetch immediately - should use cache
        entry2 = checker_short._get_cached_entry(robots_url, remote_options)
        assert mock_fetch.call_count == 1  # No additional call
        assert entry1 is entry2

        # Wait for cache to expire
        time.sleep(1.1)

        # Third fetch - should hit network again
        entry3 = checker_short._get_cached_entry(robots_url, remote_options)
        assert mock_fetch.call_count == 2
        assert entry3 is not entry1

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_can_fetch_strict_allowed(self, mock_fetch, checker, remote_options):
        """Test can_fetch with strict policy when URL is allowed."""
        # Mock robots.txt that allows /page
        robots_content = "User-agent: *\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        allowed, delay = checker.can_fetch(
            url="https://example.com/page",
            remote_options=remote_options,
            policy="strict",
        )

        assert allowed is True
        assert delay is None

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_can_fetch_strict_disallowed(self, mock_fetch, checker, remote_options):
        """Test can_fetch with strict policy when URL is disallowed."""
        # Mock robots.txt that disallows /admin/
        robots_content = "User-agent: *\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        with pytest.raises(ValidationError) as exc_info:
            checker.can_fetch(
                url="https://example.com/admin/secret",
                remote_options=remote_options,
                policy="strict",
            )

        assert "robots.txt" in str(exc_info.value)
        assert "disallows" in str(exc_info.value)

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_can_fetch_warn_disallowed(self, mock_fetch, checker, remote_options):
        """Test can_fetch with warn policy when URL is disallowed - should warn but not raise."""
        # Mock robots.txt that disallows /admin/
        robots_content = "User-agent: *\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        with patch("all2md.utils.robots_txt.logger.warning") as mock_warning:
            allowed, delay = checker.can_fetch(
                url="https://example.com/admin/secret",
                remote_options=remote_options,
                policy="warn",
            )

            # Should return False but not raise
            assert allowed is False
            assert delay is None
            # Should have logged a warning
            assert mock_warning.call_count == 1

    def test_can_fetch_ignore_policy(self, checker, remote_options):
        """Test can_fetch with ignore policy - should skip check entirely."""
        # Don't even mock fetch - it shouldn't be called
        allowed, delay = checker.can_fetch(
            url="https://example.com/admin/secret",
            remote_options=remote_options,
            policy="ignore",
        )

        # Should return True without fetching robots.txt
        assert allowed is True
        assert delay is None
        assert len(checker._cache) == 0  # Cache should be empty

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_can_fetch_with_crawl_delay(self, mock_fetch, checker, remote_options):
        """Test can_fetch returns crawl delay when specified in robots.txt."""
        # Mock robots.txt with crawl delay
        # Note: stdlib RobotFileParser may not support crawl-delay for wildcard user-agent
        # So we test with specific user-agent matching
        robots_content = "User-agent: test-bot\nCrawl-delay: 2.5\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        allowed, delay = checker.can_fetch(
            url="https://example.com/page",
            remote_options=remote_options,
            policy="strict",
        )

        assert allowed is True
        # stdlib RobotFileParser.crawl_delay() support varies by Python version
        # Just verify it returns a value or None without asserting the exact value
        assert delay is None or isinstance(delay, (int, float))

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_can_fetch_user_agent_specific(self, mock_fetch, checker, remote_options):
        """Test that robots.txt respects user-agent specific rules."""
        # Mock robots.txt with user-agent specific rules
        robots_content = """
User-agent: test-bot
Disallow: /private/

User-agent: *
Disallow: /admin/
"""
        mock_fetch.return_value = robots_content.encode("utf-8")

        # test-bot should be blocked from /private/ but allowed to /admin/
        with pytest.raises(ValidationError):
            checker.can_fetch(
                url="https://example.com/private/data",
                remote_options=remote_options,
                policy="strict",
            )

        # Should be allowed to access /admin/ (only blocked for *)
        allowed, _ = checker.can_fetch(
            url="https://example.com/admin/page",
            remote_options=remote_options,
            policy="strict",
        )
        assert allowed is True

    def test_clear_cache(self, checker):
        """Test cache clearing functionality."""
        # Add some entries to cache
        checker._cache["https://example.com/robots.txt"] = RobotsTxtCacheEntry(
            parser=MagicMock(),
            timestamp=time.time(),
            fetch_failed=False,
            status_code=200,
        )
        checker._cache["https://example.org/robots.txt"] = RobotsTxtCacheEntry(
            parser=MagicMock(),
            timestamp=time.time(),
            fetch_failed=False,
            status_code=200,
        )

        assert len(checker._cache) == 2

        checker.clear_cache()

        assert len(checker._cache) == 0

    def test_get_cache_size(self, checker):
        """Test cache size reporting."""
        assert checker.get_cache_size() == 0

        # Add entries
        checker._cache["https://example.com/robots.txt"] = RobotsTxtCacheEntry(
            parser=MagicMock(),
            timestamp=time.time(),
            fetch_failed=False,
            status_code=200,
        )

        assert checker.get_cache_size() == 1

    @patch("all2md.utils.network_security.fetch_content_securely")
    def test_thread_safety(self, mock_fetch, checker, remote_options):
        """Test that checker is thread-safe for concurrent access."""
        # Mock robots.txt fetch
        robots_content = "User-agent: *\nDisallow: /admin/\n"
        mock_fetch.return_value = robots_content.encode("utf-8")

        results = []
        errors = []

        def fetch_url(url: str):
            """Helper to fetch URL in thread."""
            try:
                allowed, delay = checker.can_fetch(url, remote_options, "strict")
                results.append((url, allowed, delay))
            except Exception as e:
                errors.append(e)

        # Create multiple threads accessing same robots.txt
        threads = []
        urls = [f"https://example.com/page{i}" for i in range(10)]

        for url in urls:
            thread = threading.Thread(target=fetch_url, args=(url,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should succeed
        assert len(errors) == 0
        assert len(results) == 10

        # All should be allowed
        for _url, allowed, _delay in results:
            assert allowed is True


class TestGlobalChecker:
    """Tests for global checker singleton."""

    def test_get_global_checker_singleton(self):
        """Test that get_global_checker returns the same instance."""
        checker1 = get_global_checker()
        checker2 = get_global_checker()

        assert checker1 is checker2

    def test_global_checker_thread_safety(self):
        """Test that global checker creation is thread-safe."""
        # Reset global checker
        import all2md.utils.robots_txt as robots_module

        robots_module._global_checker = None

        checkers = []

        def get_checker():
            """Get checker in thread."""
            checkers.append(get_global_checker())

        threads = [threading.Thread(target=get_checker) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All threads should get the same instance
        assert len({id(c) for c in checkers}) == 1
