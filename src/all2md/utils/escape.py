#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/escape.py
"""Format-specific text escaping utilities.

This module provides escape functions for various markup formats to ensure
special characters are properly handled in rendered output.

"""

from __future__ import annotations

import html


def escape_asciidoc(text: str) -> str:
    r"""Escape special AsciiDoc characters in text content.

    AsciiDoc has many special characters that need escaping when they
    appear in regular text content to prevent unintended formatting.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        Escaped text safe for AsciiDoc

    Examples
    --------
        >>> escape_asciidoc("Text with [brackets] and *stars*")
        'Text with \\[brackets\\] and \\*stars\\*'

    """
    if not text:
        return text

    # Characters that need escaping in AsciiDoc text:
    # [ ] - For attribute lists and cross-references
    # * _ - For emphasis/strong
    # ` - For inline code
    # + - For passthrough
    # # - For headers (at line start, but safer to escape)
    # | - For tables
    # : - For definition lists and block attributes
    special_chars = {
        "[": r"\[",
        "]": r"\]",
        "*": r"\*",
        "_": r"\_",
        "`": r"\`",
        "+": r"\+",
        "#": r"\#",
        "|": r"\|",
        ":": r"\:",
    }

    result = text
    for char, escaped in special_chars.items():
        result = result.replace(char, escaped)

    return result


def escape_asciidoc_attribute(text: str) -> str:
    r"""Escape text for use in AsciiDoc attribute values.

    Attribute values have additional escaping requirements beyond
    regular text content.

    Parameters
    ----------
    text : str
        Text to escape for attribute value

    Returns
    -------
    str
        Escaped text safe for AsciiDoc attributes

    Examples
    --------
        >>> escape_asciidoc_attribute('Title: A "Special" Document')
        'Title: A \\"Special\\" Document'

    """
    if not text:
        return text

    # For attributes, escape quotes and newlines
    result = text.replace("\\", "\\\\")  # Escape backslashes first
    result = result.replace('"', '\\"')
    result = result.replace("\n", "\\n")
    result = result.replace("\r", "\\r")

    return result


def escape_rst(text: str) -> str:
    r"""Escape special reStructuredText characters.

    RST uses backslash escaping for its special characters.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        Escaped text safe for RST

    Examples
    --------
        >>> escape_rst("Text with *emphasis* and `code`")
        'Text with \\*emphasis\\* and \\`code\\`'

    """
    if not text:
        return text

    # RST special characters that need escaping:
    # * _ - For emphasis/strong
    # ` - For interpreted text and inline literals
    # [ ] - For footnotes and citations
    # < > - For embedded URIs
    # | - For substitution references
    # : - For field lists (at line start, but safer to escape)
    special_chars = {
        "*": r"\*",
        "_": r"\_",
        "`": r"\`",
        "[": r"\[",
        "]": r"\]",
        "<": r"\<",
        ">": r"\>",
        "|": r"\|",
        ":": r"\:",
    }

    result = text
    for char, escaped in special_chars.items():
        result = result.replace(char, escaped)

    return result


def escape_markdown_context_aware(text: str, context: str = "text") -> str:
    r"""Escape markdown with context awareness.

    Different contexts require different escaping strategies.

    Parameters
    ----------
    text : str
        Text to escape
    context : {'text', 'table', 'link', 'image_alt'}, default = 'text'
        Context where text will be used

    Returns
    -------
    str
        Escaped text

    Examples
    --------
        >>> escape_markdown_context_aware("Text with [brackets]", "text")
        'Text with \\[brackets\\]'
        >>> escape_markdown_context_aware("Cell | with | pipes", "table")
        'Cell \\| with \\| pipes'

    """
    if not text:
        return text

    if context == "table":
        # In table cells, pipes must be escaped
        return text.replace("|", r"\|")

    elif context == "link":
        # In link text, escape square brackets
        result = text.replace("[", r"\[")
        result = result.replace("]", r"\]")
        return result

    elif context == "image_alt":
        # In image alt text, escape square brackets
        result = text.replace("[", r"\[")
        result = result.replace("]", r"\]")
        return result

    else:  # context == "text" or default
        # General text - escape common markdown special characters
        # These can trigger unintended formatting:
        # \ - Escape character itself
        # ` - Code
        # * - Emphasis/strong/list
        # _ - Emphasis/strong
        # { } - Sometimes used in extensions
        # [ ] - Links
        # # - Headers
        # We're conservative here; context-specific escaping is better
        # but this provides a baseline
        special_chars = r"\`*_{}[]#"
        result = ""
        for char in text:
            if char in special_chars:
                result += "\\" + char
            else:
                result += char
        return result


def escape_inline_code(code: str, delimiter: str = "`") -> tuple[str, str]:
    """Escape inline code and determine appropriate delimiter.

    Handles cases where code contains the delimiter character by
    using a longer delimiter sequence or different delimiter.

    Parameters
    ----------
    code : str
        Code content to escape
    delimiter : str, default = '`'
        Preferred delimiter character

    Returns
    -------
    tuple[str, str]
        (escaped_code, delimiter_to_use)

    Examples
    --------
        >>> escape_inline_code("simple code", "`")
        ('simple code', '`')
        >>> escape_inline_code("code with ` backtick", "`")
        ('code with ` backtick', '``')

    """
    if not code:
        return code, delimiter

    # Count consecutive delimiters in code
    max_consecutive = 0
    current_consecutive = 0

    for char in code:
        if char == delimiter:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0

    if max_consecutive == 0:
        # No delimiters in code, use single delimiter
        return code, delimiter

    # Use one more delimiter than the longest sequence in code
    delimiter_count = max_consecutive + 1
    final_delimiter = delimiter * delimiter_count

    # If code starts/ends with delimiter char, add spaces
    if code.startswith(delimiter) or code.endswith(delimiter):
        code = " " + code + " "

    return code, final_delimiter


def escape_mediawiki(text: str) -> str:
    """Escape special MediaWiki characters (minimal/experimental implementation).

    WARNING: This is a minimal implementation. MediaWiki markup has complex
    escaping rules, and this function currently performs no actual escaping.

    MediaWiki is generally lenient with special characters in plain text contexts.
    The main characters that can cause formatting issues are:
    - '' (two apostrophes) for italic
    - ''' (three apostrophes) for bold
    - [[ and ]] for links
    - {{ and }} for templates

    However, in most plain text contexts (like within <code> tags or table cells),
    MediaWiki handles these gracefully without explicit escaping.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        Text (currently unchanged - passes through as-is)

    Examples
    --------
        >>> escape_mediawiki("Text with ''quotes''")
        "Text with ''quotes''"
        >>> escape_mediawiki("Normal text")
        'Normal text'

    Notes
    -----
    This function is marked as experimental because:
    - MediaWiki's escaping rules are context-dependent
    - Most text renders correctly without escaping in the contexts where this is used
    - Full escaping would require <nowiki> tags, which may not be appropriate in all contexts

    If you need robust MediaWiki escaping, consider using <nowiki> tags explicitly
    or HTML entities for special characters.

    """
    if not text:
        return text

    # MediaWiki is lenient in most contexts, so we pass text through as-is
    # Future enhancement: Could implement <nowiki> wrapping for problematic sequences
    return text


def escape_dokuwiki(text: str, context: str = "text") -> str:
    r"""Escape special DokuWiki characters in text content.

    DokuWiki uses several special character sequences for formatting.
    This function escapes them to prevent unintended formatting.

    Parameters
    ----------
    text : str
        Text to escape
    context : {'text', 'table', 'link', 'code'}, default = 'text'
        Context where text will be used. Different contexts have different
        escaping requirements:
        - 'text': Regular paragraph text (escape all special sequences)
        - 'table': Table cell content (escape | and ^ additionally)
        - 'link': Link text or URL (escape brackets)
        - 'code': Code context (minimal escaping, preserve literal characters)

    Returns
    -------
    str
        Escaped text safe for DokuWiki rendering

    Examples
    --------
    Escape formatting characters:
        >>> escape_dokuwiki("Text with **bold** and //italic//")
        'Text with \\*\\*bold\\*\\* and \\/\\/italic\\/\\/'

    Table context:
        >>> escape_dokuwiki("Cell | with | pipes", context="table")
        'Cell \\| with \\| pipes'

    Code context (minimal escaping):
        >>> escape_dokuwiki("code_example()", context="code")
        'code_example()'

    Notes
    -----
    DokuWiki special sequences that need escaping:
    - ** for bold
    - // for italic
    - __ for underline
    - '' for monospace (two single quotes)
    - [[ and ]] for links
    - {{ and }} for images
    - \\\\ for line breaks (four backslashes in source become two in display)
    - | and ^ for tables
    - \\ at end of line for forced line break

    In DokuWiki, backslash is used as the escape character. To display
    a literal special character, prefix it with backslash.

    """
    if not text:
        return text

    # Code context: minimal escaping, preserve most characters literally
    if context == "code":
        # In code context, only escape the backslash itself
        return text.replace("\\", "\\\\")

    # Link context: only escape brackets
    if context == "link":
        result = text.replace("[", r"\[")
        result = result.replace("]", r"\]")
        return result

    # Table context: escape table delimiters and all text formatting
    if context == "table":
        # Start with text escaping
        result = text
        # Escape backslashes first to avoid double-escaping
        result = result.replace("\\", "\\\\")
        # Escape table-specific characters
        result = result.replace("|", r"\|")
        result = result.replace("^", r"\^")
        # Escape formatting characters
        result = result.replace("*", r"\*")
        result = result.replace("/", r"\/")
        result = result.replace("_", r"\_")
        result = result.replace("'", r"\'")
        result = result.replace("[", r"\[")
        result = result.replace("]", r"\]")
        result = result.replace("{", r"\{")
        result = result.replace("}", r"\}")
        return result

    # Default text context: escape all DokuWiki special characters
    result = text
    # Escape backslashes first to avoid double-escaping
    result = result.replace("\\", "\\\\")
    # Escape formatting characters
    result = result.replace("*", r"\*")
    result = result.replace("/", r"\/")
    result = result.replace("_", r"\_")
    result = result.replace("'", r"\'")
    # Escape link/image brackets
    result = result.replace("[", r"\[")
    result = result.replace("]", r"\]")
    result = result.replace("{", r"\{")
    result = result.replace("}", r"\}")

    return result


def escape_html_entities(text: str) -> str:
    """Escape HTML special characters to entities.

    Used when embedding text in HTML contexts. This function uses Python's
    built-in html.escape() for standard HTML5 entity encoding.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        Text with HTML entities

    Examples
    --------
        >>> escape_html_entities("<script>alert('XSS')</script>")
        '&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;'

    Notes
    -----
    This function escapes the following characters:
    - & -> &amp;
    - < -> &lt;
    - > -> &gt;
    - " -> &quot;
    - ' -> &#x27; (HTML5 standard)

    """
    if not text:
        return text

    return html.escape(text, quote=True)
