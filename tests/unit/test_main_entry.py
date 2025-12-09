"""Unit tests for __main__.py entry points."""

import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestAll2mdMain:
    """Test all2md/__main__.py entry point."""

    def test_main_module_importable(self):
        """Test that __main__.py module is importable."""
        import all2md.__main__  # noqa: F401

    def test_main_calls_cli_main(self):
        """Test that running module calls cli main."""
        with patch("all2md.cli.main", return_value=0):
            # We can't easily test if __name__ == "__main__" block,
            # but we can verify the import structure is correct
            from all2md.__main__ import main  # noqa: F401
            from all2md.cli import main as cli_main

            # Verify cli.main exists and is callable
            assert callable(cli_main)

    def test_main_with_help(self, monkeypatch):
        """Test running with --help argument."""
        from all2md.cli import main

        # main() should handle --help gracefully
        with patch.object(sys, "argv", ["all2md", "--help"]):
            try:
                result = main()
                # --help typically returns 0
                assert result == 0
            except SystemExit as e:
                # argparse may call sys.exit(0) for --help
                assert e.code == 0


@pytest.mark.unit
class TestMcpMain:
    """Test all2md/mcp/__main__.py entry point."""

    def test_mcp_main_module_importable(self):
        """Test that mcp/__main__.py module is importable."""
        try:
            import all2md.mcp.__main__  # noqa: F401
        except ImportError:
            pytest.skip("MCP module not available")

    def test_mcp_main_function_exists(self):
        """Test that mcp module has a main function."""
        try:
            from all2md.mcp import main

            assert callable(main)
        except ImportError:
            pytest.skip("MCP module not available")
