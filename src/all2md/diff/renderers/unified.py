#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/renderers/unified.py
"""Unified diff renderer with optional ANSI colors.

This renderer adds ANSI color codes to unified diff output for
terminal display, compatible with standard diff tools.
"""

from __future__ import annotations

from typing import Iterator


class UnifiedDiffRenderer:
    """Render unified diff with optional ANSI colors.

    This renderer adds color codes to standard unified diff output:
    - Red for deletions (lines starting with -)
    - Green for additions (lines starting with +)
    - Cyan for hunk headers (lines starting with @@)
    - Bold for file headers (lines starting with --- or +++)

    Parameters
    ----------
    use_color : bool, default = True
        If True, add ANSI color codes to output
    context_lines : int, default = 3
        Number of context lines (informational, not used by renderer)

    Examples
    --------
    Colorize diff output:
        >>> from all2md.diff import compare_files
        >>> from all2md.diff.renderers import UnifiedDiffRenderer
        >>> diff_lines = compare_files("old.docx", "new.docx")
        >>> renderer = UnifiedDiffRenderer()
        >>> for line in renderer.render(diff_lines):
        ...     print(line)

    """

    def __init__(
        self,
        use_color: bool = True,
        context_lines: int = 3,
    ):
        """Initialize the unified diff renderer."""
        self.use_color = use_color
        self.context_lines = context_lines

    def render(self, diff_lines: Iterator[str]) -> Iterator[str]:
        """Render unified diff with optional colors.

        Parameters
        ----------
        diff_lines : Iterator[str]
            Lines of unified diff output

        Yields
        ------
        str
            Colorized diff lines (or original lines if color disabled)

        """
        if not self.use_color:
            # Just pass through
            yield from diff_lines
            return

        # Define ANSI color codes
        RED = "\033[31m"
        GREEN = "\033[32m"
        CYAN = "\033[36m"
        BOLD = "\033[1m"
        RESET = "\033[0m"

        for line in diff_lines:
            if line.startswith("---") or line.startswith("+++"):
                # File headers: bold
                yield f"{BOLD}{line}{RESET}"
            elif line.startswith("@@"):
                # Hunk headers: cyan
                yield f"{CYAN}{line}{RESET}"
            elif line.startswith("+"):
                # Additions: green
                yield f"{GREEN}{line}{RESET}"
            elif line.startswith("-"):
                # Deletions: red
                yield f"{RED}{line}{RESET}"
            else:
                # Context lines: no color
                yield line


def colorize_diff(diff_lines: Iterator[str], use_color: bool = True) -> Iterator[str]:
    """Colorize unified diff output.

    Parameters
    ----------
    diff_lines : Iterator[str]
        Lines of unified diff output
    use_color : bool, default = True
        If True, add ANSI color codes

    Yields
    ------
    str
        Colorized diff lines

    """
    renderer = UnifiedDiffRenderer(use_color=use_color)
    yield from renderer.render(diff_lines)
