#!/usr/bin/env python3
"""Demo of LLM-based document translation using AST transforms.

This example translates a document section-by-section with an LLM while
preserving its structure and formatting through the AST. The workflow is:

1. Parse the document to an AST (preserves structure)
2. Apply a translation transform (translates Text nodes only)
3. Render back to the original format (preserves formatting)

Because it operates on the AST, it works with any format all2md can parse --
PDF, DOCX, HTML, Markdown, and more -- making it format-agnostic.

LLM access goes through the shared ``_llm_client`` helper, which talks to Claude
via the official ``anthropic`` SDK. Use ``--llm mock`` to run with no API key.
"""

import argparse
import os
import sys
from typing import Callable, Optional

from all2md.api import from_ast, to_ast
from all2md.ast import Text
from all2md.ast.transforms import NodeTransformer


class LLMTranslateTransform(NodeTransformer):
    """Transform that translates text nodes using an LLM.

    Visits every Text node and replaces its content with a translation, leaving
    document structure, formatting, and metadata untouched. Code is preserved.

    Parameters
    ----------
    target_language : str
        Target language for translation (e.g. "Spanish", "French", "German").
    llm_client : callable
        Function ``(text, target_language) -> translated_text``. Any LLM (or the
        bundled mock) can be wrapped to match this signature.
    preserve_code : bool, default = True
        If True, skip translating code blocks and inline code.
    preserve_links : bool, default = True
        If True, only translate link text, not URLs.
    """

    def __init__(
        self,
        target_language: str,
        llm_client: Callable[[str, str], str],
        preserve_code: bool = True,
        preserve_links: bool = True,
    ):
        """Initialize the LLM translation transform.

        See the class docstring for parameter descriptions.
        """
        super().__init__()
        self.target_language = target_language
        self.llm_client = llm_client
        self.preserve_code = preserve_code
        self.preserve_links = preserve_links
        self._in_code = False

    def visit_text(self, node: Text) -> Text:
        """Translate the content of a Text node."""
        # Skip translation if we're inside a code block
        if self._in_code and self.preserve_code:
            return node

        # Don't translate empty or whitespace-only text
        if not node.content or node.content.isspace():
            return node

        # Translate the text
        try:
            translated = self.llm_client(node.content, self.target_language)
            return Text(content=translated, metadata=node.metadata.copy())
        except Exception as e:
            # On error, keep the original text and record the failure in metadata
            metadata = node.metadata.copy()
            metadata["translation_error"] = str(e)
            return Text(content=node.content, metadata=metadata)

    def visit_code_block(self, node):
        """Mark when we're inside a code block."""
        self._in_code = True
        result = super().visit_code_block(node)
        self._in_code = False
        return result

    def visit_code(self, node):
        """Mark when we're inside inline code."""
        if self.preserve_code:
            return node  # Don't translate inline code
        return super().visit_code(node)


def mock_llm_translate(text: str, target_language: str) -> str:
    """Offline stand-in for a real translator (no API key required).

    Prepends the target language so you can see the transform working end-to-end
    without spending tokens.
    """
    return f"[{target_language.upper()}] {text}"


def anthropic_translate(text: str, target_language: str) -> str:
    """Translate one chunk of text with Claude via the shared helper.

    Requires: pip install anthropic
    Environment: ANTHROPIC_API_KEY

    See ``_llm_client.py`` for the SDK wiring. For a long document this is
    called once per text node, so a cheaper current model
    (e.g. "claude-haiku-4-5") is often a better fit -- see DEFAULT_MODEL there.
    """
    from _llm_client import get_client

    client = get_client("anthropic")  # cached: built once, reused per node
    system = (
        f"You are a professional translator. Translate the user's text into {target_language}. "
        "Preserve all formatting, Markdown syntax, and technical terms. "
        "Return only the translated text, with no preamble or commentary."
    )
    return client(text, system=system)


# Map output file extensions to all2md renderer formats.
_FORMAT_BY_EXT = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".pdf": "pdf",
    ".docx": "docx",
    ".rst": "rst",
    ".txt": "plaintext",
    ".json": "ast_json",
}


def translate_document(
    input_path: str,
    output_path: str,
    target_language: str,
    llm_client: Optional[Callable[[str, str], str]] = None,
):
    """Translate a document while preserving its format.

    Parameters
    ----------
    input_path : str
        Path to the input document (PDF, DOCX, HTML, Markdown, ...).
    output_path : str
        Path to the output document; its extension selects the output format.
    target_language : str
        Target language for translation.
    llm_client : callable, optional
        ``(text, target_language) -> str``. Uses the mock translator if omitted.
    """
    if llm_client is None:
        llm_client = mock_llm_translate

    # Step 1: Parse document to AST
    print(f"Parsing {input_path}...")
    doc_ast = to_ast(input_path)

    # Step 2: Apply translation transform
    print(f"Translating to {target_language}...")
    translator = LLMTranslateTransform(target_language, llm_client)
    translated_ast = translator.transform(doc_ast)

    # Step 3: Render back out. The output extension selects the target format.
    ext = os.path.splitext(output_path)[1].lower()
    output_format = _FORMAT_BY_EXT.get(ext, "markdown")

    print(f"Rendering to {output_format} format...")
    from_ast(translated_ast, output_format, output=output_path)

    print(f"✓ Translation complete: {output_path}")


def main():
    """Run the translation demo."""
    parser = argparse.ArgumentParser(description="Translate documents using an LLM while preserving format")
    parser.add_argument("input", help="Input document path")
    parser.add_argument("output", help="Output document path")
    parser.add_argument("--language", "-l", default="Spanish", help="Target language (default: Spanish)")
    parser.add_argument(
        "--llm",
        choices=["mock", "anthropic"],
        default="mock",
        help="LLM provider: mock (no API key) or anthropic = Claude (default: mock)",
    )

    args = parser.parse_args()

    llm_clients = {"mock": mock_llm_translate, "anthropic": anthropic_translate}
    llm_client = llm_clients[args.llm]

    if args.llm == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    translate_document(args.input, args.output, args.language, llm_client)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("LLM Translation Demo")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python llm_translation_demo.py input.pdf output.pdf --language Spanish")
        print("  python llm_translation_demo.py input.docx output.docx --language French --llm anthropic")
        print("  python llm_translation_demo.py input.md output.md --language German --llm anthropic")
        print()
        print("Supported formats: PDF, DOCX, HTML, Markdown, RST, plain text, and more")
        print()
        print("LLM providers:")
        print("  --llm mock        Demo mode (adds a language prefix, no API key)")
        print("  --llm anthropic   Use Anthropic Claude (requires ANTHROPIC_API_KEY)")
        print()
        print("Example with the mock LLM:")
        print("  python llm_translation_demo.py document.pdf translated.pdf --language Spanish")
        sys.exit(0)

    main()
