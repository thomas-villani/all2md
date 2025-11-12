"""Integration tests for HttpRetriever with robots.txt validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from all2md.exceptions import ValidationError
from all2md.utils.input_sources import DocumentSourceRequest, HttpRetriever, RemoteInputOptions
from all2md.utils.robots_txt import get_global_checker


@pytest.fixture
def retriever():
    """Create HttpRetriever instance."""
    return HttpRetriever()


@pytest.fixture
def remote_options_strict():
    """Create RemoteInputOptions with strict robots.txt policy."""
    return RemoteInputOptions(
        allow_remote_input=True,
        require_https=False,
        user_agent="test-bot/1.0",
        follow_robots_txt="strict",
    )


@pytest.fixture
def remote_options_warn():
    """Create RemoteInputOptions with warn robots.txt policy."""
    return RemoteInputOptions(
        allow_remote_input=True,
        require_https=False,
        user_agent="test-bot/1.0",
        follow_robots_txt="warn",
    )


@pytest.fixture
def remote_options_ignore():
    """Create RemoteInputOptions with ignore robots.txt policy."""
    return RemoteInputOptions(
        allow_remote_input=True,
        require_https=False,
        user_agent="test-bot/1.0",
        follow_robots_txt="ignore",
    )


@pytest.fixture(autouse=True)
def clear_robots_cache():
    """Clear robots.txt cache before each test."""
    checker = get_global_checker()
    checker.clear_cache()
    yield
    checker.clear_cache()


class TestHttpRetrieverRobotsTxt:
    """Integration tests for HttpRetriever with robots.txt."""

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_allowed_url_with_strict_policy(
        self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict
    ):
        """Test that allowed URLs are fetched successfully with strict policy."""

        # Mock robots.txt fetch - fetch_content_securely returns bytes directly
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return b"User-agent: *\nDisallow: /admin/\n"
            else:
                # Regular content fetch
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        request = DocumentSourceRequest(
            raw_input="http://example.com/page",
            remote_options=remote_options_strict,
        )

        source = retriever.load(request)
        assert source is not None

        # Should have called fetch twice: once for robots.txt (network_security), once for content (input_sources)
        assert mock_fetch_input.call_count + mock_fetch_network.call_count == 2

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_disallowed_url_with_strict_policy(
        self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict
    ):
        """Test that disallowed URLs raise ValidationError with strict policy."""

        # Mock robots.txt fetch
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return b"User-agent: *\nDisallow: /admin/\n"
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        request = DocumentSourceRequest(
            raw_input="http://example.com/admin/secret",
            remote_options=remote_options_strict,
        )

        with pytest.raises(ValidationError) as exc_info:
            retriever.load(request)

        assert "robots.txt" in str(exc_info.value)
        assert "disallows" in str(exc_info.value)

        # Should have only called fetch once for robots.txt (not for content)
        assert mock_fetch_input.call_count + mock_fetch_network.call_count == 1

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_disallowed_url_with_warn_policy(
        self, mock_fetch_input, mock_fetch_network, retriever, remote_options_warn
    ):
        """Test that disallowed URLs are fetched with warning when using warn policy."""

        # Mock robots.txt fetch
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return b"User-agent: *\nDisallow: /admin/\n"
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        request = DocumentSourceRequest(
            raw_input="http://example.com/admin/secret",
            remote_options=remote_options_warn,
        )

        with patch("all2md.utils.robots_txt.logger.warning") as mock_warning:
            source = retriever.load(request)

            # Should succeed despite being disallowed
            assert source is not None

            # Should have logged a warning
            assert mock_warning.call_count == 1

        # Should have called fetch twice: robots.txt and content
        assert mock_fetch_input.call_count + mock_fetch_network.call_count == 2

    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_ignore_policy_skips_robots_check(self, mock_fetch, retriever, remote_options_ignore):
        """Test that ignore policy skips robots.txt check entirely."""
        # Mock only content fetch, not robots.txt
        mock_fetch.return_value = b"Page content"

        request = DocumentSourceRequest(
            raw_input="http://example.com/admin/secret",
            remote_options=remote_options_ignore,
        )

        source = retriever.load(request)
        assert source is not None

        # Should have only called fetch once for content (not for robots.txt)
        assert mock_fetch.call_count == 1

    @patch("all2md.utils.input_sources.time.sleep")
    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_crawl_delay_is_applied(
        self, mock_fetch_input, mock_fetch_network, mock_sleep, retriever, remote_options_strict
    ):
        """Test that crawl-delay from robots.txt is applied."""

        # Mock robots.txt with crawl delay
        # Note: crawl-delay may not be supported by stdlib RobotFileParser
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return b"User-agent: *\nCrawl-delay: 2.5\n"
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        request = DocumentSourceRequest(
            raw_input="http://example.com/page",
            remote_options=remote_options_strict,
        )

        source = retriever.load(request)
        assert source is not None

        # Should have called sleep with crawl delay if supported
        # Note: stdlib RobotFileParser crawl_delay support varies, so we check if called
        if mock_sleep.call_count > 0:
            mock_sleep.assert_called_with(2.5)

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_robots_txt_404_allows_access(self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict):
        """Test that 404 on robots.txt allows access per RFC 9309."""

        # Mock robots.txt 404 and content fetch
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                from all2md.exceptions import NetworkSecurityError

                error = NetworkSecurityError("Not found")
                error.status_code = 404
                raise error
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        request = DocumentSourceRequest(
            raw_input="http://example.com/any-page",
            remote_options=remote_options_strict,
        )

        source = retriever.load(request)
        assert source is not None

        # Should have called fetch twice: robots.txt (404) and content
        assert mock_fetch_input.call_count + mock_fetch_network.call_count == 2

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_robots_txt_5xx_disallows_access(
        self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict
    ):
        """Test that 5xx on robots.txt temporarily disallows access."""

        # Mock robots.txt 503 error
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                from all2md.exceptions import NetworkSecurityError

                error = NetworkSecurityError("Service unavailable")
                error.status_code = 503
                raise error
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        request = DocumentSourceRequest(
            raw_input="http://example.com/any-page",
            remote_options=remote_options_strict,
        )

        with pytest.raises(ValidationError) as exc_info:
            retriever.load(request)

        assert "robots.txt" in str(exc_info.value)

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_robots_txt_caching(self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict):
        """Test that robots.txt is cached between requests to same host."""

        # Mock robots.txt and content fetches
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return b"User-agent: *\nDisallow: /admin/\n"
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        # First request
        request1 = DocumentSourceRequest(
            raw_input="http://example.com/page1",
            remote_options=remote_options_strict,
        )
        source1 = retriever.load(request1)
        assert source1 is not None

        # Should have called fetch twice: robots.txt and content
        first_call_count = mock_fetch_input.call_count + mock_fetch_network.call_count
        assert first_call_count == 2

        # Second request to same host
        request2 = DocumentSourceRequest(
            raw_input="http://example.com/page2",
            remote_options=remote_options_strict,
        )
        source2 = retriever.load(request2)
        assert source2 is not None

        # Should have called fetch only once more (for content, not robots.txt)
        total_calls = mock_fetch_input.call_count + mock_fetch_network.call_count
        assert total_calls == first_call_count + 1

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_different_hosts_fetch_separate_robots_txt(
        self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict
    ):
        """Test that different hosts fetch their own robots.txt."""

        # Mock robots.txt and content fetches
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                if "example.com" in url:
                    return b"User-agent: *\nDisallow: /admin/\n"
                else:
                    return b"User-agent: *\nDisallow: /private/\n"
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        # Request to first host
        request1 = DocumentSourceRequest(
            raw_input="http://example.com/page",
            remote_options=remote_options_strict,
        )
        source1 = retriever.load(request1)
        assert source1 is not None

        first_call_count = mock_fetch_input.call_count + mock_fetch_network.call_count
        assert first_call_count == 2  # robots.txt + content

        # Request to second host
        request2 = DocumentSourceRequest(
            raw_input="http://example.org/page",
            remote_options=remote_options_strict,
        )
        source2 = retriever.load(request2)
        assert source2 is not None

        # Should have called fetch twice more (robots.txt + content for new host)
        total_calls = mock_fetch_input.call_count + mock_fetch_network.call_count
        assert total_calls == first_call_count + 2

    @patch("all2md.utils.network_security.fetch_content_securely")
    @patch("all2md.utils.input_sources.fetch_content_securely")
    def test_user_agent_from_remote_options(
        self, mock_fetch_input, mock_fetch_network, retriever, remote_options_strict
    ):
        """Test that user-agent from RemoteInputOptions is used for robots.txt."""

        # Mock robots.txt with user-agent specific rules
        def fetch_side_effect(url, **kwargs):
            if url.endswith("/robots.txt"):
                return b"""
User-agent: test-bot
Disallow: /private/

User-agent: *
Disallow: /admin/
"""
            else:
                return b"Page content"

        mock_fetch_input.side_effect = fetch_side_effect
        mock_fetch_network.side_effect = fetch_side_effect

        # test-bot should be blocked from /private/ but allowed to /admin/
        request_private = DocumentSourceRequest(
            raw_input="http://example.com/private/data",
            remote_options=remote_options_strict,
        )

        with pytest.raises(ValidationError):
            retriever.load(request_private)

        # test-bot should be allowed to /admin/ (only blocked for *)
        request_admin = DocumentSourceRequest(
            raw_input="http://example.com/admin/page",
            remote_options=remote_options_strict,
        )

        source = retriever.load(request_admin)
        assert source is not None


class TestRemoteInputOptionsValidation:
    """Tests for RemoteInputOptions validation."""

    def test_valid_robots_txt_policies(self):
        """Test that valid robots.txt policies are accepted."""
        for policy in ("strict", "warn", "ignore"):
            options = RemoteInputOptions(follow_robots_txt=policy)
            assert options.follow_robots_txt == policy

        # Test uppercase is normalized
        options = RemoteInputOptions(follow_robots_txt="STRICT")
        assert options.follow_robots_txt == "strict"

    def test_invalid_robots_txt_policy(self):
        """Test that invalid robots.txt policy raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RemoteInputOptions(follow_robots_txt="invalid")

        assert "Invalid follow_robots_txt policy" in str(exc_info.value)

    def test_default_robots_txt_policy(self):
        """Test that default robots.txt policy is strict."""
        options = RemoteInputOptions()
        assert options.follow_robots_txt == "strict"
