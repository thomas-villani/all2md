#!/usr/bin/env python3
"""Demo of LLM-based document translation using AST transforms.

This example demonstrates how to translate a document section-by-section
using an LLM while preserving the document's structure and format through
the AST. The workflow is:

1. Parse document to AST (preserves structure)
2. Apply translation transform (translates text nodes)
3. Render to original format (preserves formatting)

This works with any format supported by all2md, making it format-agnostic.
"""
from typing import Callable
import os
import argparse

from all2md.api import from_ast, to_ast
from all2md.ast import Text
from all2md.ast.transforms import NodeTransformer


class LLMTranslateTransform(NodeTransformer):
    """Transform that translates text nodes using an LLM.

    This transform visits all Text nodes in the AST and translates their
    content using an LLM API. The document structure, formatting, and
    metadata are preserved.

    Parameters
    ----------
    target_language : str
        Target language for translation (e.g., "Spanish", "French", "German")
    llm_client : callable
        Function that takes (text, target_lang) and returns translated text.
        This can be OpenAI, Anthropic, or any other LLM API.
    preserve_code : bool, default = True
        If True, skip translating code blocks and inline code
    preserve_links : bool, default = True
        If True, only translate link text, not URLs

    """

    def __init__(
        self,
        target_language: str,
        llm_client: Callable[[str, str], str],
        preserve_code: bool = True,
        preserve_links: bool = True,
    ):
        """Initialize the LLM translation transform.

        See class docstring for parameter descriptions.
        """
        super().__init__()
        self.target_language = target_language
        self.llm_client = llm_client
        self.preserve_code = preserve_code
        self.preserve_links = preserve_links
        self._in_code = False

    def visit_text(self, node: Text) -> Text:
        """Translate text node content."""
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
            # On error, return original text with error in metadata
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
    """Mock LLM translation function for demonstration.

    In a real implementation, this would call an actual LLM API like:
    - OpenAI: openai.chat.completions.create()
    - Anthropic: anthropic.messages.create()
    - Google: genai.GenerativeModel().generate_content()

    Parameters
    ----------
    text : str
        Text to translate
    target_language : str
        Target language

    Returns
    -------
    str
        Translated text

    """
    # For demo purposes, just prepend the target language
    return f"[{target_language.upper()}] {text}"


def translate_document(input_path: str, output_path: str, target_language: str, llm_client: callable = None):
    """Translate a document while preserving its format.

    This function demonstrates the full workflow:
    1. Parse document to AST (any supported format)
    2. Apply translation transform
    3. Render back to original format

    Parameters
    ----------
    input_path : str
        Path to input document (PDF, DOCX, HTML, Markdown, etc.)
    output_path : str
        Path to output document (same format as input)
    target_language : str
        Target language for translation
    llm_client : callable, optional
        LLM translation function. Uses mock if not provided.

    """

    # Use mock LLM if no client provided
    if llm_client is None:
        llm_client = mock_llm_translate

    # Step 1: Parse document to AST
    print(f"Parsing {input_path}...")
    doc_ast = to_ast(input_path)

    # Step 2: Apply translation transform
    print(f"Translating to {target_language}...")
    translator = LLMTranslateTransform(target_language, llm_client)
    translated_ast = translator.transform(doc_ast)

    # Step 3: Render back to original format
    # Auto-detect output format from extension
    ext = os.path.splitext(output_path)[1].lower()
    format_map = {
        ".md": "markdown",
        ".pdf": "pdf",
        ".docx": "docx",
        ".html": "html",
        ".sdoc": "simpledoc",
        ".json": "simpledoc",
    }
    output_format = format_map.get(ext, "markdown")

    print(f"Rendering to {output_format} format...")
    from_ast(translated_ast, output_format=output_format, output_path=output_path)

    print(f"✓ Translation complete: {output_path}")


def openai_translate(text: str, target_language: str) -> str:
    """Real OpenAI translation function (requires openai package).

    To use this, install: pip install openai
    Set environment variable: export OPENAI_API_KEY=your_key

    Parameters
    ----------
    text : str
        Text to translate
    target_language : str
        Target language

    Returns
    -------
    str
        Translated text

    """

    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate the following text to {target_language}. "
                    "Preserve all formatting, markdown syntax, and technical terms. "
                    "Return only the translated text, nothing else."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content


def anthropic_translate(text: str, target_language: str) -> str:
    """Real Anthropic translation function (requires anthropic package).

    To use this, install: pip install anthropic
    Set environment variable: export ANTHROPIC_API_KEY=your_key

    Parameters
    ----------
    text : str
        Text to translate
    target_language : str
        Target language

    Returns
    -------
    str
        Translated text

    """

    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Translate the following text to {target_language}. "
                    "Preserve all formatting, markdown syntax, and technical terms. "
                    f"Return only the translated text:\n\n{text}"
                ),
            }
        ],
    )

    return message.content[0].text


def main():
    """Run the translation demo."""

    parser = argparse.ArgumentParser(description="Translate documents using LLM while preserving format")
    parser.add_argument("input", help="Input document path")
    parser.add_argument("output", help="Output document path")
    parser.add_argument("--language", "-l", default="Spanish", help="Target language (default: Spanish)")
    parser.add_argument(
        "--llm", choices=["mock", "openai", "anthropic"], default="mock", help="LLM provider to use (default: mock)"
    )

    args = parser.parse_args()

    # Select LLM client
    llm_clients = {"mock": mock_llm_translate, "openai": openai_translate, "anthropic": anthropic_translate}

    llm_client = llm_clients[args.llm]

    # Check for API keys if using real LLMs
    if args.llm == "openai":
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable not set")
            sys.exit(1)
    elif args.llm == "anthropic":
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)

    # Translate the document
    translate_document(args.input, args.output, args.language, llm_client)


if __name__ == "__main__":
    # Example usage without arguments
    import sys

    if len(sys.argv) == 1:
        print("LLM Translation Demo")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python llm_translation_demo.py input.pdf output.pdf --language Spanish")
        print("  python llm_translation_demo.py input.docx output.docx --language French --llm openai")
        print("  python llm_translation_demo.py input.md output.md --language German --llm anthropic")
        print()
        print("Supported formats: PDF, DOCX, HTML, Markdown, SimpleDoc, and more")
        print()
        print("LLM providers:")
        print("  --llm mock        Demo mode (adds language prefix)")
        print("  --llm openai      Use OpenAI GPT (requires OPENAI_API_KEY)")
        print("  --llm anthropic   Use Anthropic Claude (requires ANTHROPIC_API_KEY)")
        print()
        print("Example with mock LLM:")
        print("  python llm_translation_demo.py document.pdf translated.pdf --language Spanish")
        sys.exit(0)

    main()
