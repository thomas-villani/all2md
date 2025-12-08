#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for diff/renderers/unified.py UnifiedDiffRenderer."""


from all2md.diff.renderers.unified import UnifiedDiffRenderer, colorize_diff


class TestUnifiedDiffRenderer:
    """Tests for the UnifiedDiffRenderer class."""

    def test_init_defaults(self):
        """Test default initialization."""
        renderer = UnifiedDiffRenderer()
        assert renderer.use_color is True
        assert renderer.context_lines == 3

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        renderer = UnifiedDiffRenderer(use_color=False, context_lines=5)
        assert renderer.use_color is False
        assert renderer.context_lines == 5

    def test_render_without_color(self):
        """Test rendering without color codes."""
        renderer = UnifiedDiffRenderer(use_color=False)
        diff_lines = iter(
            [
                "--- old.txt",
                "+++ new.txt",
                "@@ -1,3 +1,3 @@",
                " context line",
                "-deleted line",
                "+added line",
            ]
        )

        result = list(renderer.render(diff_lines))

        assert result == [
            "--- old.txt",
            "+++ new.txt",
            "@@ -1,3 +1,3 @@",
            " context line",
            "-deleted line",
            "+added line",
        ]

    def test_render_with_color_file_headers(self):
        """Test that file headers are rendered in bold."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(
            [
                "--- old.txt",
                "+++ new.txt",
            ]
        )

        result = list(renderer.render(diff_lines))

        # Check for bold ANSI codes
        BOLD = "\033[1m"
        RESET = "\033[0m"
        assert result[0] == f"{BOLD}--- old.txt{RESET}"
        assert result[1] == f"{BOLD}+++ new.txt{RESET}"

    def test_render_with_color_hunk_headers(self):
        """Test that hunk headers are rendered in cyan."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(
            [
                "@@ -1,3 +1,3 @@",
                "@@ -10,5 +12,7 @@ function test()",
            ]
        )

        result = list(renderer.render(diff_lines))

        CYAN = "\033[36m"
        RESET = "\033[0m"
        assert result[0] == f"{CYAN}@@ -1,3 +1,3 @@{RESET}"
        assert result[1] == f"{CYAN}@@ -10,5 +12,7 @@ function test(){RESET}"

    def test_render_with_color_additions(self):
        """Test that additions are rendered in green."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(
            [
                "+added line",
                "+another added line",
            ]
        )

        result = list(renderer.render(diff_lines))

        GREEN = "\033[32m"
        RESET = "\033[0m"
        assert result[0] == f"{GREEN}+added line{RESET}"
        assert result[1] == f"{GREEN}+another added line{RESET}"

    def test_render_with_color_deletions(self):
        """Test that deletions are rendered in red."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(
            [
                "-deleted line",
                "-another deleted line",
            ]
        )

        result = list(renderer.render(diff_lines))

        RED = "\033[31m"
        RESET = "\033[0m"
        assert result[0] == f"{RED}-deleted line{RESET}"
        assert result[1] == f"{RED}-another deleted line{RESET}"

    def test_render_with_color_context_lines(self):
        """Test that context lines are not colorized."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(
            [
                " context line 1",
                " context line 2",
            ]
        )

        result = list(renderer.render(diff_lines))

        # Context lines should be unchanged
        assert result[0] == " context line 1"
        assert result[1] == " context line 2"

    def test_render_empty_input(self):
        """Test rendering empty input."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter([])

        result = list(renderer.render(diff_lines))

        assert result == []

    def test_render_complete_diff(self):
        """Test rendering a complete unified diff."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(
            [
                "--- a/file.txt",
                "+++ b/file.txt",
                "@@ -1,5 +1,6 @@",
                " first line",
                "-removed line",
                "+added line",
                "+another addition",
                " last line",
            ]
        )

        result = list(renderer.render(diff_lines))

        BOLD = "\033[1m"
        CYAN = "\033[36m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        RESET = "\033[0m"

        assert result[0] == f"{BOLD}--- a/file.txt{RESET}"
        assert result[1] == f"{BOLD}+++ b/file.txt{RESET}"
        assert result[2] == f"{CYAN}@@ -1,5 +1,6 @@{RESET}"
        assert result[3] == " first line"
        assert result[4] == f"{RED}-removed line{RESET}"
        assert result[5] == f"{GREEN}+added line{RESET}"
        assert result[6] == f"{GREEN}+another addition{RESET}"
        assert result[7] == " last line"

    def test_render_handles_special_characters(self):
        """Test rendering lines with special characters."""
        renderer = UnifiedDiffRenderer(use_color=False)
        diff_lines = iter(
            [
                "-line with tabs\t\there",
                "+line with unicode: \u00e9\u00e8",
                " line with spaces   ",
            ]
        )

        result = list(renderer.render(diff_lines))

        assert result[0] == "-line with tabs\t\there"
        assert result[1] == "+line with unicode: \u00e9\u00e8"
        assert result[2] == " line with spaces   "

    def test_render_lines_starting_with_plus_plus_plus(self):
        """Test that +++ lines are treated as file headers."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(["+++ b/file.txt"])

        result = list(renderer.render(diff_lines))

        BOLD = "\033[1m"
        RESET = "\033[0m"
        assert result[0] == f"{BOLD}+++ b/file.txt{RESET}"

    def test_render_lines_starting_with_minus_minus_minus(self):
        """Test that --- lines are treated as file headers."""
        renderer = UnifiedDiffRenderer(use_color=True)
        diff_lines = iter(["--- a/file.txt"])

        result = list(renderer.render(diff_lines))

        BOLD = "\033[1m"
        RESET = "\033[0m"
        assert result[0] == f"{BOLD}--- a/file.txt{RESET}"


class TestColorizeDiff:
    """Tests for the colorize_diff convenience function."""

    def test_colorize_diff_with_color(self):
        """Test colorize_diff with color enabled."""
        diff_lines = iter(
            [
                "--- old.txt",
                "+++ new.txt",
                "@@ -1,1 +1,1 @@",
                "-old",
                "+new",
            ]
        )

        result = list(colorize_diff(diff_lines, use_color=True))

        # Should have color codes
        assert "\033[" in result[0]  # ANSI escape code present

    def test_colorize_diff_without_color(self):
        """Test colorize_diff with color disabled."""
        diff_lines = iter(
            [
                "--- old.txt",
                "+++ new.txt",
                "@@ -1,1 +1,1 @@",
                "-old",
                "+new",
            ]
        )

        result = list(colorize_diff(diff_lines, use_color=False))

        # Should be unchanged
        assert result == [
            "--- old.txt",
            "+++ new.txt",
            "@@ -1,1 +1,1 @@",
            "-old",
            "+new",
        ]

    def test_colorize_diff_default_color(self):
        """Test that colorize_diff uses color by default."""
        diff_lines = iter(["+added"])

        result = list(colorize_diff(diff_lines))

        GREEN = "\033[32m"
        RESET = "\033[0m"
        assert result[0] == f"{GREEN}+added{RESET}"
