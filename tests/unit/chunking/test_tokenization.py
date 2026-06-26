#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for chunking token-counter resolution and backends."""

import pytest

from all2md.chunking.tokenization import (
    WhitespaceCounter,
    get_counter,
    tiktoken_available,
)
from all2md.exceptions import DependencyError

pytestmark = pytest.mark.unit


class TestWhitespaceCounter:
    """The dependency-free approximate counter."""

    def test_counts_whitespace_runs(self):
        """Tokens are whitespace-delimited runs; collapsed whitespace ignored."""
        counter = WhitespaceCounter()
        assert counter.count("one two three") == 3
        assert counter.count("  leading   and   trailing  ") == 3
        assert counter.count("") == 0
        assert counter.name == "whitespace"

    def test_has_no_encoding(self):
        """Whitespace counter exposes no tiktoken encoding."""
        assert WhitespaceCounter().encoding is None


class TestGetCounter:
    """Backend resolution and fallback rules."""

    def test_whitespace_explicit(self):
        """Explicit whitespace request returns the approximation."""
        assert isinstance(get_counter("whitespace", strategy="paragraph"), WhitespaceCounter)

    def test_whitespace_rejected_for_token_strategies(self):
        """Whitespace cannot serve strategies that split on real token boundaries."""
        for strategy in ("semantic", "token", "char"):
            with pytest.raises(ValueError, match="real token boundaries"):
                get_counter("whitespace", strategy=strategy)

    def test_auto_falls_back_for_count_only(self, monkeypatch):
        """When tiktoken is unavailable, auto degrades to whitespace for count-only strategies."""
        monkeypatch.setattr("all2md.chunking.tokenization.tiktoken_available", lambda: False)
        assert isinstance(get_counter("auto", strategy="paragraph"), WhitespaceCounter)

    def test_auto_raises_for_token_strategy_without_tiktoken(self, monkeypatch):
        """Auto surfaces a DependencyError (not silent degradation) for token strategies."""
        monkeypatch.setattr("all2md.chunking.tokenization.tiktoken_available", lambda: False)

        def _boom(*_a, **_k):
            raise DependencyError(converter_name="chunk", missing_packages=[("tiktoken", ">=0.7.0")])

        monkeypatch.setattr("all2md.chunking.tokenization.TiktokenCounter", _boom)
        with pytest.raises(DependencyError):
            get_counter("auto", strategy="semantic")

    def test_unknown_backend(self):
        """An unrecognized backend name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown token counter"):
            get_counter("bogus")


@pytest.mark.skipif(not tiktoken_available(), reason="tiktoken not installed")
class TestTiktokenCounter:
    """Real BPE counting (only when tiktoken is installed)."""

    def test_counts_and_exposes_encoding(self):
        """Tiktoken counter returns positive counts and exposes its encoding."""
        counter = get_counter("tiktoken")
        assert counter.name == "tiktoken"
        assert counter.encoding is not None
        assert counter.count("hello world") >= 2
