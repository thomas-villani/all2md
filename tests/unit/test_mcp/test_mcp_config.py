"""Unit tests for MCP configuration module."""

import os

import pytest

from all2md.mcp.config import (
    MCPConfig,
    _parse_semicolon_list,
    _str_to_bool,
    load_config_from_env,
)


class TestHelperFunctions:
    """Tests for configuration helper functions."""

    def test_str_to_bool_true_values(self):
        """Test that various true values are recognized."""
        assert _str_to_bool("true") is True
        assert _str_to_bool("TRUE") is True
        assert _str_to_bool("1") is True
        assert _str_to_bool("yes") is True
        assert _str_to_bool("YES") is True
        assert _str_to_bool("on") is True

    def test_str_to_bool_false_values(self):
        """Test that non-true values are recognized as false."""
        assert _str_to_bool("false") is False
        assert _str_to_bool("0") is False
        assert _str_to_bool("no") is False
        assert _str_to_bool("off") is False
        assert _str_to_bool("other") is False

    def test_str_to_bool_none_default(self):
        """Test that None returns default value."""
        assert _str_to_bool(None, default=True) is True
        assert _str_to_bool(None, default=False) is False

    def test_parse_semicolon_list_basic(self):
        """Test basic semicolon list parsing."""
        result = _parse_semicolon_list("/path/one;/path/two;/path/three")
        assert result == ["/path/one", "/path/two", "/path/three"]

    def test_parse_semicolon_list_with_spaces(self):
        """Test that whitespace is trimmed."""
        result = _parse_semicolon_list("  /path/one  ;  /path/two  ;  /path/three  ")
        assert result == ["/path/one", "/path/two", "/path/three"]

    def test_parse_semicolon_list_empty(self):
        """Test that empty or None input returns None."""
        assert _parse_semicolon_list(None) is None
        assert _parse_semicolon_list("") is None
        assert _parse_semicolon_list("  ;  ;  ") is None

    def test_parse_semicolon_list_single_path(self):
        """Test single path without semicolons."""
        result = _parse_semicolon_list("/single/path")
        assert result == ["/single/path"]


class TestMCPConfig:
    """Tests for MCPConfig dataclass."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = MCPConfig()
        assert config.enable_to_md is True
        assert config.enable_from_md is False  # Disabled by default for security
        assert config.read_allowlist is None  # Will be set to CWD by load_config_from_env
        assert config.write_allowlist is None  # Will be set to CWD by load_config_from_env
        assert config.attachment_mode == "base64"  # Default for vLLM visibility
        assert config.disable_network is True
        assert config.log_level == "INFO"

    def test_config_validate_no_tools_enabled(self):
        """Test that at least one tool must be enabled."""
        config = MCPConfig(enable_to_md=False, enable_from_md=False)
        with pytest.raises(ValueError, match="At least one tool must be enabled"):
            config.validate()

    def test_config_validate_download_mode_not_allowed(self):
        """Test that download mode is not allowed in MCP."""
        config = MCPConfig(attachment_mode="download")
        with pytest.raises(ValueError, match="Invalid attachment_mode"):
            config.validate()

    def test_config_validate_allowed_attachment_modes(self):
        """Test that only skip, alt_text, and base64 modes are allowed."""
        # Valid modes should not raise
        for mode in ['skip', 'alt_text', 'base64']:
            config = MCPConfig(attachment_mode=mode)
            config.validate()  # Should not raise

    def test_config_validate_base64_mode_with_network_disabled(self):
        """Test that base64 mode works with network disabled (for embedded images)."""
        config = MCPConfig(
            attachment_mode="base64",
            disable_network=True
        )
        config.validate()  # Should not raise


class TestLoadConfigFromEnv:
    """Tests for loading configuration from environment variables."""

    def test_load_config_defaults(self, monkeypatch):
        """Test loading with no env vars set (defaults to CWD)."""
        # Clear any existing env vars
        for key in list(os.environ.keys()):
            if key.startswith("ALL2MD_MCP_"):
                monkeypatch.delenv(key, raising=False)

        config = load_config_from_env()

        assert config.enable_to_md is True
        assert config.enable_from_md is False  # Disabled by default for security
        # Should default to CWD
        assert config.read_allowlist == [os.getcwd()]
        assert config.write_allowlist == [os.getcwd()]
        assert config.attachment_mode == "base64"  # Default for vLLM visibility
        assert config.disable_network is True
        assert config.log_level == "INFO"

    def test_load_config_from_env_vars(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("ALL2MD_MCP_ENABLE_TO_MD", "false")
        monkeypatch.setenv("ALL2MD_MCP_ENABLE_FROM_MD", "true")
        monkeypatch.setenv("ALL2MD_MCP_ALLOWED_READ_DIRS", "/read/dir1;/read/dir2")
        monkeypatch.setenv("ALL2MD_MCP_ALLOWED_WRITE_DIRS", "/write/dir1")
        monkeypatch.setenv("ALL2MD_MCP_ATTACHMENT_MODE", "base64")
        monkeypatch.setenv("ALL2MD_MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("ALL2MD_DISABLE_NETWORK", "false")

        config = load_config_from_env()

        assert config.enable_to_md is False
        assert config.enable_from_md is True
        assert config.read_allowlist == ["/read/dir1", "/read/dir2"]
        assert config.write_allowlist == ["/write/dir1"]
        assert config.attachment_mode == "base64"
        assert config.log_level == "DEBUG"
        assert config.disable_network is False
