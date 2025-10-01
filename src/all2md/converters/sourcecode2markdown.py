#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/sourcecode2markdown.py
"""Source code to Markdown conversion module.

This module provides conversion of source code files to Markdown format by
wrapping the content in properly formatted fenced code blocks with language
identifiers. It supports automatic language detection from file extensions
and handles over 200 programming languages and text file formats.

The converter detects the programming language based on file extension and
creates Markdown fenced code blocks with appropriate syntax highlighting
identifiers. This enhances readability when the Markdown is rendered in
systems that support syntax highlighting.

Key Features
------------
- Automatic language detection from file extensions
- Support for 200+ programming languages and file formats
- Proper Markdown fenced code block formatting
- Optional filename inclusion as comment
- Configurable language override
- Preserves original file formatting and structure

Supported Languages
-------------------
The converter supports all major programming languages including:
- Python (.py), JavaScript (.js), TypeScript (.ts)
- C/C++ (.c, .cpp, .h, .hpp), Java (.java)
- Go (.go), Rust (.rs), Swift (.swift)
- HTML (.html), CSS (.css), SCSS (.scss)
- Shell scripts (.sh, .bash), PowerShell (.ps1)
- Configuration files (.yaml, .json, .toml, .ini)
- And many more...

Configuration Options
---------------------
- Language detection control (enable/disable)
- Manual language override
- Filename inclusion in output
- Standard Markdown formatting options

Dependencies
------------
- No external dependencies required
- Uses only Python standard library

Examples
--------
Basic usage with automatic language detection:

    >>> from all2md.converters.sourcecode2markdown import sourcecode_to_markdown
    >>> result = sourcecode_to_markdown('script.py')
    >>> print(result)
    ```python
    def hello_world():
        print("Hello, World!")
    ```

With custom options:

    >>> from all2md.options import SourceCodeOptions
    >>> options = SourceCodeOptions(include_filename=True)
    >>> result = sourcecode_to_markdown('script.py', options=options)
"""

import logging
import os
from pathlib import Path
from typing import IO, Dict, Optional, Union

from all2md.constants import PLAINTEXT_EXTENSIONS
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MarkdownConversionError
from all2md.options import SourceCodeOptions
from all2md.utils.inputs import is_path_like
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled

logger = logging.getLogger(__name__)

# Language mapping for file extensions to GitHub-style language identifiers
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
    ".json": "json",
    ".json5": "json5",
    ".jsonld": "json",
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


def _format_sourcecode_content(
    content: str, language: str, filename: Optional[str] = None, include_filename: bool = False
) -> str:
    """Format source code content as Markdown fenced code block.

    Parameters
    ----------
    content : str
        Source code content
    language : str
        Language identifier for syntax highlighting
    filename : str, optional
        Original filename
    include_filename : bool
        Whether to include filename as comment

    Returns
    -------
    str
        Formatted Markdown with fenced code block
    """
    # Prepare content
    content = content.strip()

    # Add filename comment if requested
    if include_filename and filename:
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

        comment_prefix = comment_styles.get(language, "#")
        comment_suffix = ""

        if comment_prefix in ["<!--", "/*"]:
            comment_suffix = " -->" if comment_prefix == "<!--" else " */"

        filename_comment = f"{comment_prefix} {filename}{comment_suffix}"
        content = f"{filename_comment}\n{content}"

    # Create fenced code block
    return f"```{language}\n{content}\n```"


def sourcecode_to_markdown(
    input: Union[str, Path, IO[bytes], bytes], options: Optional[SourceCodeOptions] = None
) -> str:
    """Convert source code file to Markdown format.

    This function reads a source code file and converts it to a Markdown
    fenced code block with appropriate syntax highlighting language identifier.

    Parameters
    ----------
    input : str, Path, IO[bytes], or bytes
        Input source code file path, file-like object, or raw bytes
    options : SourceCodeOptions, optional
        Configuration options for conversion

    Returns
    -------
    str
        Source code formatted as Markdown fenced code block

    Raises
    ------
    InputError
        If input is invalid or cannot be processed
    MarkdownConversionError
        If conversion fails due to encoding or other issues

    Examples
    --------
    Convert a Python file:

        >>> result = sourcecode_to_markdown('script.py')
        >>> print(result)
        ```python
        def hello():
            print("Hello, World!")
        ```

    With custom options:

        >>> opts = SourceCodeOptions(language_override="text", include_filename=True)
        >>> result = sourcecode_to_markdown('config.conf', options=opts)
    """
    # Use default options if none provided
    if options is None:
        options = SourceCodeOptions()

    # Extract filename for language detection
    filename = None
    if is_path_like(input):
        filename = str(input)
    elif hasattr(input, "name") and input.name:
        filename = input.name

    # Read content based on input type
    try:
        if isinstance(input, (str, Path)):
            # Read from file path
            with open(input, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        elif isinstance(input, bytes):
            # Decode bytes directly
            content = input.decode("utf-8", errors="replace")
        else:
            # Handle file-like object
            if hasattr(input, "read"):
                raw_content = input.read()
                if isinstance(raw_content, bytes):
                    content = raw_content.decode("utf-8", errors="replace")
                else:
                    content = str(raw_content)
            else:
                raise ValueError(f"Unsupported input type: {type(input)}")
    except Exception as e:
        raise MarkdownConversionError(f"Failed to read source code: {e}") from e

    # Use AST-based conversion path
    from all2md.converters.sourcecode2ast import SourceCodeToAstConverter
    from all2md.ast import MarkdownRenderer

    # Convert to AST
    ast_converter = SourceCodeToAstConverter(options=options)
    ast_document = ast_converter.convert_to_ast(content, filename=filename)

    # Render AST to markdown
    from all2md.options import MarkdownOptions
    md_opts = options.markdown_options if options.markdown_options else MarkdownOptions()
    renderer = MarkdownRenderer(md_opts)
    result = renderer.render(ast_document)

    # Create metadata
    metadata = DocumentMetadata(
        title=os.path.basename(filename) if filename else "Source Code",
        language=ast_document.children[0].language if ast_document.children else "text",
        custom={"format": "sourcecode"},
    )

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(result.strip(), metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="sourcecode",
    extensions=PLAINTEXT_EXTENSIONS,  # Use all plaintext extensions
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
    converter_module="all2md.converters.sourcecode2markdown",
    converter_function="sourcecode_to_markdown",
    required_packages=[],  # No external dependencies
    optional_packages=[],
    import_error_message="",  # No dependencies required
    options_class="SourceCodeOptions",
    description="Convert source code files to Markdown with syntax highlighting",
    priority=1,  # Lower priority than specialized converters, higher than txt fallback
)
