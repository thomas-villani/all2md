#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/sourcecode.py
"""Source code to AST converter.

This module provides conversion from source code files to AST representation.
It creates CodeBlock nodes with appropriate language identifiers.

"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import IO, Any, Dict, Optional, Union

from all2md.ast import CodeBlock, Document
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.sourcecode import SourceCodeOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.encoding import normalize_stream_to_text, read_text_with_encoding_detection
from all2md.utils.inputs import is_path_like
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


# Language mapping for file extensions to GitHub-style language identifiers
# Imported from sourcecode2markdown for consistency


class SourceCodeToAstConverter(BaseParser):
    """Convert source code files to AST representation.

    This converter creates a CodeBlock node with the detected language.

    Parameters
    ----------
    options : SourceCodeOptions or None
        Conversion options

    """

    def __init__(self, options: SourceCodeOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the source code parser with options and progress callback."""
        BaseParser._validate_options_type(options, SourceCodeOptions, "sourcecode")
        options = options or SourceCodeOptions()
        super().__init__(options, progress_callback)
        self.options: SourceCodeOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse source code input into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input source code to parse

        Returns
        -------
        Document
            AST Document node with CodeBlock

        Raises
        ------
        ParsingError
            If parsing fails

        """
        # Extract filename for language detection
        filename = None
        if is_path_like(input_data):
            filename = str(input_data)
        elif hasattr(input_data, "name") and input_data.name:
            filename = input_data.name

        # Read content based on input type with encoding detection
        try:
            if isinstance(input_data, (str, Path)):
                # Read from file path
                with open(input_data, "rb") as f:
                    content = read_text_with_encoding_detection(f.read())
            elif isinstance(input_data, bytes):
                # Decode bytes with encoding detection
                content = read_text_with_encoding_detection(input_data)
            elif hasattr(input_data, "read"):
                # Handle file-like object (handles both binary and text mode)
                content = normalize_stream_to_text(input_data)
            else:
                raise ValueError(f"Unsupported input type: {type(input_data)}")
        except Exception as e:
            raise ParsingError(f"Failed to read source code: {e}") from e

        return self.convert_to_ast(content, filename=filename)

    def convert_to_ast(self, content: str, filename: str | None = None, language: str | None = None) -> Document:
        """Convert source code content to AST Document.

        Parameters
        ----------
        content : str
            Source code content
        filename : str | None
            Filename for language detection
        language : str | None
            Override language identifier

        Returns
        -------
        Document
            AST document with CodeBlock node

        """
        # Strip content
        content = content.strip()

        # Determine language
        if language:
            detected_lang = language
            logger.debug(f"Using provided language: {detected_lang}")
        elif self.options.language_override:
            detected_lang = self.options.language_override
            logger.debug(f"Using language override: {detected_lang}")
        elif self.options.detect_language and filename:
            detected_lang = _detect_language_from_extension(filename)
            logger.debug(f"Detected language from extension: {detected_lang}")
        else:
            detected_lang = "text"
            logger.debug("Using default language: text")

        # Add filename comment if requested
        if self.options.include_filename and filename:
            # Get base filename
            base_filename = os.path.basename(filename)

            # Determine comment style
            comment_styles = {
                "python": "#",
                "bash": "#",
                "ruby": "#",
                "perl": "#",
                "yaml": "#",
                "javascript": "//",
                "typescript": "//",
                "java": "//",
                "c": "//",
                "cpp": "//",
                "csharp": "//",
                "go": "//",
                "rust": "//",
                "swift": "//",
                "html": "<!--",
                "xml": "<!--",
                "css": "/*",
                "scss": "/*",
                "less": "/*",
                "sql": "--",
                "lua": "--",
                "haskell": "--",
            }

            comment_prefix = comment_styles.get(detected_lang, "#")
            comment_suffix = ""

            if comment_prefix in ["<!--", "/*"]:
                comment_suffix = " -->" if comment_prefix == "<!--" else " */"

            filename_comment = f"{comment_prefix} {base_filename}{comment_suffix}"
            content = f"{filename_comment}\n{content}"

        # Create CodeBlock node
        code_block = CodeBlock(
            language=detected_lang, content=content, metadata={"filename": filename} if filename else {}
        )

        # Extract and attach metadata
        metadata = self.extract_metadata(None)
        return Document(children=[code_block], metadata=metadata.to_dict())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from source code document.

        Parameters
        ----------
        document : Any
            Source code document (not used)

        Returns
        -------
        DocumentMetadata
            Empty metadata (source code files don't have standard metadata)

        Notes
        -----
        Source code files typically do not contain structured metadata.
        Information like language and filename is handled through the
        conversion options and file context, not as document metadata.

        """
        return DocumentMetadata()


# Converter metadata for registration
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    # Python
    ".py": "python",
    ".pyx": "python",
    ".pyi": "python",
    # JavaScript/TypeScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    # Web technologies
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    # C/C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",
    # Java/JVM languages
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".groovy": "groovy",
    # C#/.NET
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vbnet",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Swift
    ".swift": "swift",
    # Objective-C (Note: .m handled specially due to MATLAB conflict)
    ".m": "objective-c",
    ".mm": "objective-cpp",
    # PHP
    ".php": "php",
    # Ruby
    ".rb": "ruby",
    ".gemspec": "ruby",
    ".rake": "ruby",
    # Shell scripting
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".fish": "fish",
    ".csh": "csh",
    ".ksh": "ksh",
    ".ps1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    # Lua
    ".lua": "lua",
    # Perl
    ".pl": "perl",
    ".pm": "perl",
    # R
    ".r": "r",
    # Haskell
    ".hs": "haskell",
    # Erlang/Elixir
    ".erl": "erlang",
    ".hrl": "erlang",
    ".ex": "elixir",
    ".exs": "elixir",
    # Lisp family
    ".lisp": "lisp",
    ".el": "elisp",
    ".clj": "clojure",
    # Functional languages
    ".elm": "elm",
    ".ml": "ocaml",
    ".f": "fortran",
    ".f90": "fortran",
    ".f95": "fortran",
    ".for": "fortran",
    # Data/Config formats
    # Note: .json removed - use .ast.json for AST files, regular .json files are data not documents
    ".json5": "json5",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".conf": "ini",
    ".cfg": "ini",
    ".properties": "properties",
    # Markup
    ".xml": "xml",
    ".xsd": "xml",
    ".wsdl": "xml",
    ".svg": "xml",
    ".rss": "xml",
    ".atom": "xml",
    ".plist": "xml",
    ".xaml": "xml",
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".mkd": "markdown",
    ".mkdn": "markdown",
    ".mdwn": "markdown",
    ".mdx": "mdx",
    ".rst": "rst",
    ".textile": "textile",
    ".adoc": "asciidoc",
    ".asciidoc": "asciidoc",
    # SQL
    ".sql": "sql",
    # Docker
    ".dockerfile": "dockerfile",
    # GraphQL
    ".graphql": "graphql",
    ".gql": "graphql",
    # Protocol Buffers
    ".proto": "protobuf",
    # Terraform
    ".tf": "hcl",
    ".hcl": "hcl",
    # Nix
    ".nix": "nix",
    # Vim
    ".vim": "vim",
    # Git
    ".gitignore": "gitignore",
    ".gitattributes": "gitattributes",
    # Others
    ".tex": "latex",
    ".bib": "bibtex",
    ".diff": "diff",
    ".patch": "diff",
    ".log": "log",
}
CONVERTER_METADATA = ConverterMetadata(
    format_name="sourcecode",
    extensions=list(EXTENSION_TO_LANGUAGE.keys()),
    mime_types=[
        "text/plain",
        "text/x-python",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++src",
        "text/x-csharp",
        "text/x-javascript",
        "text/x-typescript",
        "text/x-go",
        "text/x-rust",
        "text/x-swift",
        "text/x-php",
        "text/x-ruby",
        "text/x-perl",
        "text/x-shellscript",
        "text/x-sql",
        "application/x-javascript",
        "application/javascript",
        "application/typescript",
        "application/x-python-code",
        "application/x-java-source",
        "application/x-csh",
        "application/x-sh",
        "application/x-shellscript",
    ],
    magic_bytes=[],  # No specific magic bytes - rely on extension detection
    parser_class=SourceCodeToAstConverter,
    renderer_class=None,
    parser_required_packages=[],  # No external dependencies
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",  # No dependencies required
    parser_options_class=SourceCodeOptions,
    renderer_options_class=None,
    description="Convert source code files to Markdown with syntax highlighting",
    priority=1,  # Lower priority than specialized parsers, higher than txt fallback
)


def _detect_language_from_extension(filename: str) -> str:
    """Detect programming language from file extension.

    Parameters
    ----------
    filename : str
        Filename or path to analyze

    Returns
    -------
    str
        Language identifier for syntax highlighting, defaults to 'text'

    """
    if not filename:
        return "text"

    # Get file extension (lowercase)
    _, ext = os.path.splitext(filename.lower())

    # Handle special cases
    basename = os.path.basename(filename).lower()

    # Special files without extensions
    special_files = {
        "dockerfile": "dockerfile",
        "jenkinsfile": "groovy",
        "makefile": "makefile",
        "rakefile": "ruby",
        "gemfile": "ruby",
        "vagrantfile": "ruby",
        "cmakelists.txt": "cmake",
    }

    if basename in special_files:
        return special_files[basename]

    # Handle .m extension ambiguity (Objective-C vs MATLAB)
    if ext == ".m":
        # Simple heuristic: if filename contains "matlab" or common MATLAB patterns, use matlab
        if "matlab" in basename or basename.startswith("script") or basename.startswith("function"):
            return "matlab"
        else:
            return "objective-c"

    # Look up extension in mapping
    return EXTENSION_TO_LANGUAGE.get(ext, "text")
