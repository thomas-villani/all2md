#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands/llm_minify.py
"""Token-lean conversion command for all2md CLI.

The ``llm-minify`` command converts any supported document the same way the
default ``all2md <file>`` command does, but strips filler that wastes LLM
tokens. Two presets are available:

- **compact Markdown** (default): keep Markdown structure (headings, lists,
  code, tables) while dropping comments, frontmatter, raw HTML and collapsing
  redundant blank lines/whitespace.
- **plain text** (``--aggressive`` / ``--text``): strip all formatting down to
  bare text via the plain-text renderer.

Optional ``--strip-*`` flags layer additional pruning on top of either preset.
"""

import argparse
import re
import sys
from pathlib import Path

from all2md import MarkdownRendererOptions, PlainTextOptions, from_ast, to_ast
from all2md.ast import Image, Link, Node, NodeTransformer, Text, extract_text
from all2md.cli import EXIT_FILE_ERROR
from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS
from all2md.cli.config import apply_config_to_parser


def _create_llm_minify_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``llm-minify`` command.

    Exposed as a factory so ``config generate`` can introspect the command's
    options to emit an ``[llm-minify]`` config-template section.
    """
    parser = argparse.ArgumentParser(
        prog="all2md llm-minify",
        description="Convert a document to token-lean Markdown (or plain text) for LLM consumption.",
    )
    parser.add_argument("input", help="File to convert (use '-' for stdin)")
    parser.add_argument("-o", "--out", help="Write output to a file instead of stdout")
    parser.add_argument(
        "--aggressive",
        "--text",
        dest="aggressive",
        action="store_true",
        help="Strip ALL formatting to bare text (plain-text preset). The default keeps compact Markdown structure.",
    )
    parser.add_argument(
        "--strip-links",
        action="store_true",
        help="Drop link URLs, keeping only the link text.",
    )
    parser.add_argument(
        "--strip-images",
        action="store_true",
        help="Drop images entirely (removes data URIs and alt text).",
    )
    parser.add_argument(
        "--strip-formatting",
        action="store_true",
        help="Remove inline emphasis/strong/strikethrough/underline markers, keeping the text.",
    )
    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [llm-minify] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )
    return parser


class _MinifyTransformer(NodeTransformer):
    """Prune inline nodes according to the ``--strip-*`` flags.

    Unwrapped nodes are replaced with a single ``Text`` node holding their
    concatenated text so the result stays a valid inline child.
    """

    def __init__(self, strip_links: bool, strip_images: bool, strip_formatting: bool) -> None:
        self._strip_links = strip_links
        self._strip_images = strip_images
        self._strip_formatting = strip_formatting

    def visit_image(self, node: Image) -> Node | None:  # type: ignore[override]
        if self._strip_images:
            return None
        return super().visit_image(node)

    def visit_link(self, node: Link) -> Node:  # type: ignore[override]
        if self._strip_links:
            return Text(content=extract_text(node.content, joiner=""))
        return super().visit_link(node)

    def _unwrap(self, node: Node) -> Text:
        return Text(content=extract_text(node.content, joiner=""))  # type: ignore[attr-defined]

    def visit_emphasis(self, node: Node) -> Node:  # type: ignore[override]
        return self._unwrap(node) if self._strip_formatting else super().visit_emphasis(node)  # type: ignore[arg-type]

    def visit_strong(self, node: Node) -> Node:  # type: ignore[override]
        return self._unwrap(node) if self._strip_formatting else super().visit_strong(node)  # type: ignore[arg-type]

    def visit_strikethrough(self, node: Node) -> Node:  # type: ignore[override]
        return self._unwrap(node) if self._strip_formatting else super().visit_strikethrough(node)  # type: ignore[arg-type]

    def visit_underline(self, node: Node) -> Node:  # type: ignore[override]
        return self._unwrap(node) if self._strip_formatting else super().visit_underline(node)  # type: ignore[arg-type]

    def visit_superscript(self, node: Node) -> Node:  # type: ignore[override]
        return self._unwrap(node) if self._strip_formatting else super().visit_superscript(node)  # type: ignore[arg-type]

    def visit_subscript(self, node: Node) -> Node:  # type: ignore[override]
        return self._unwrap(node) if self._strip_formatting else super().visit_subscript(node)  # type: ignore[arg-type]


def _squeeze_whitespace(text: str) -> str:
    """Collapse filler whitespace: trailing spaces, runs of blank lines, edges."""
    # Strip trailing spaces/tabs on each line.
    text = re.sub(r"[ \t]+(\r?\n)", r"\1", text)
    # Collapse two or more blank lines into a single blank line.
    text = re.sub(r"(\r?\n){3,}", "\n\n", text)
    # Trim leading/trailing blank lines and ensure a single trailing newline.
    return text.strip("\n") + "\n"


def handle_llm_minify_command(args: list[str] | None = None) -> int:
    """Handle the ``llm-minify`` command.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond ``llm-minify``).

    Returns
    -------
    int
        Exit code (0 for success).

    """
    parser = _create_llm_minify_parser()

    try:
        # Pre-parse to discover config flags, fold the [llm-minify] config section
        # in as defaults, then parse for real so explicit CLI flags win.
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "llm-minify", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    # Resolve input (file or stdin).
    if parsed.input == "-":
        stdin_data = sys.stdin.buffer.read()
        if not stdin_data:
            print("Error: No data received from stdin", file=sys.stderr)
            return EXIT_FILE_ERROR
        input_source: object = stdin_data
    else:
        input_path = Path(parsed.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {parsed.input}", file=sys.stderr)
            return EXIT_FILE_ERROR
        input_source = parsed.input

    try:
        doc = to_ast(input_source)  # type: ignore[arg-type]

        if parsed.strip_links or parsed.strip_images or parsed.strip_formatting:
            transformer = _MinifyTransformer(
                strip_links=parsed.strip_links,
                strip_images=parsed.strip_images,
                strip_formatting=parsed.strip_formatting,
            )
            transformed = transformer.transform(doc)
            if transformed is not None:
                doc = transformed  # type: ignore[assignment]

        if parsed.aggressive:
            result = from_ast(
                doc,
                "plaintext",
                renderer_options=PlainTextOptions(
                    max_line_width=None,
                    preserve_blank_lines=False,
                    comment_mode="ignore",
                ),
            )
        else:
            result = from_ast(
                doc,
                "markdown",
                renderer_options=MarkdownRendererOptions(
                    comment_mode="ignore",
                    metadata_frontmatter=False,
                    collapse_blank_lines=True,
                    autolink_bare_urls=False,
                    html_passthrough_mode="drop",
                ),
            )
    except Exception as e:  # noqa: BLE001 - surface any conversion error as a CLI error
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    if not isinstance(result, str):
        print("Error: minify produced non-text output", file=sys.stderr)
        return EXIT_ERROR

    output = _squeeze_whitespace(result)

    if parsed.out:
        try:
            Path(parsed.out).write_text(output, encoding="utf-8")
        except OSError as e:
            print(f"Error: could not write output file: {e}", file=sys.stderr)
            return EXIT_FILE_ERROR
    else:
        sys.stdout.write(output)

    return EXIT_SUCCESS
