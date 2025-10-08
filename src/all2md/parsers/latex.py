#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/latex.py
"""LaTeX to AST converter.

This module provides conversion from LaTeX documents to AST representation
using the pylatexenc library for parsing. It enables bidirectional transformation
by parsing LaTeX into the same AST structure used for other formats.

"""

from __future__ import annotations

import re
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strong,
    Subscript,
    Superscript,
    Table,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options import LatexParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata


class LatexParser(BaseParser):
    r"""Convert LaTeX to AST representation.

    This parser implements a LaTeX parser that converts LaTeX documents
    into the all2md AST format. It uses pylatexenc library for parsing
    LaTeX syntax and converts common LaTeX commands to AST nodes.

    Parameters
    ----------
    options : LatexParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = LatexParser()
        >>> doc = parser.parse("\section{Title}\n\nThis is \textbf{bold}.")

    With options:

        >>> options = LatexParserOptions(parse_math=True)
        >>> parser = LatexParser(options)
        >>> doc = parser.parse(latex_text)

    """

    def __init__(
        self,
        options: LatexParserOptions | None = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the LaTeX parser."""
        options = options or LatexParserOptions()
        super().__init__(options, progress_callback)
        self.options: LatexParserOptions = options
        self.document_metadata: dict[str, Any] = {}

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse LaTeX input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            LaTeX input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw LaTeX bytes
            - LaTeX string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails

        """
        # Load content
        content = self._load_content(input_data)

        # Emit progress event
        self._emit_progress("started", "Parsing LaTeX", current=0, total=100)

        # Parse metadata from preamble if enabled
        if self.options.parse_preamble:
            content, metadata = self._extract_preamble_metadata(content)
            self.document_metadata = metadata

        self._emit_progress("preamble_parsed", "Preamble parsed", current=20, total=100)

        # Try to import pylatexenc
        try:
            from pylatexenc.latexwalker import LatexWalker
        except ImportError as e:
            raise ParsingError(
                "LaTeX parsing requires the 'pylatexenc' package. "
                "Install it with: pip install pylatexenc"
            ) from e

        # Parse LaTeX using pylatexenc
        try:
            walker = LatexWalker(content)
            nodelist, pos, length = walker.get_latex_nodes()
        except Exception as e:
            if self.options.strict_mode:
                raise ParsingError(f"Failed to parse LaTeX: {e}") from e
            # In non-strict mode, try to parse as plain text
            nodelist = []

        self._emit_progress("latex_parsed", "LaTeX structure parsed", current=50, total=100)

        # Convert LaTeX AST to our AST
        children = []
        for node in nodelist:
            ast_nodes = self._convert_node(node)
            if ast_nodes:
                if isinstance(ast_nodes, list):
                    children.extend(ast_nodes)
                else:
                    children.append(ast_nodes)

        # Extract metadata
        doc_metadata: DocumentMetadata = self.extract_metadata(content)
        # Merge with preamble metadata
        metadata_dict = doc_metadata.to_dict()
        metadata_dict.update(self.document_metadata)

        self._emit_progress("finished", "Parsing complete", current=100, total=100)

        return Document(children=children, metadata=metadata_dict)

    def _load_content(self, input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load LaTeX content from various input types.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            LaTeX content as string

        """
        if isinstance(input_data, bytes):
            return input_data.decode(self.options.encoding, errors="replace")
        elif isinstance(input_data, Path):
            return input_data.read_text(encoding=self.options.encoding)
        elif isinstance(input_data, str):
            # Could be file path or content
            path = Path(input_data)
            if path.exists() and path.is_file():
                return path.read_text(encoding=self.options.encoding)
            else:
                # Assume it's content
                return input_data
        else:
            # File-like object
            input_data.seek(0)
            content_bytes = input_data.read()
            return content_bytes.decode(self.options.encoding, errors="replace")

    def _extract_preamble_metadata(self, content: str) -> tuple[str, dict[str, Any]]:
        """Extract metadata from LaTeX preamble.

        Parameters
        ----------
        content : str
            LaTeX content

        Returns
        -------
        tuple[str, dict]
            Content without preamble commands, and metadata dict

        """
        metadata: dict[str, Any] = {}

        # Extract title
        title_match = re.search(r'\\title\{([^}]+)\}', content)
        if title_match:
            metadata['title'] = title_match.group(1).strip()

        # Extract author
        author_match = re.search(r'\\author\{([^}]+)\}', content)
        if author_match:
            metadata['author'] = author_match.group(1).strip()

        # Extract date
        date_match = re.search(r'\\date\{([^}]+)\}', content)
        if date_match:
            date_str = date_match.group(1).strip()
            if date_str and date_str != r'\today':
                metadata['date'] = date_str

        return content, metadata

    def _convert_node(self, node: Any) -> Node | list[Node] | None:
        """Convert a pylatexenc node to AST node(s).

        Parameters
        ----------
        node : Any
            pylatexenc node

        Returns
        -------
        Node, list[Node], or None
            Converted AST node(s)

        """
        try:
            from pylatexenc.latexwalker import (
                LatexCharsNode,
                LatexCommentNode,
                LatexEnvironmentNode,
                LatexGroupNode,
                LatexMacroNode,
                LatexMathNode,
            )
        except ImportError:
            return None

        # Handle different node types
        if isinstance(node, LatexCharsNode):
            return self._convert_chars_node(node)
        elif isinstance(node, LatexMacroNode):
            return self._convert_macro_node(node)
        elif isinstance(node, LatexEnvironmentNode):
            return self._convert_environment_node(node)
        elif isinstance(node, LatexGroupNode):
            return self._convert_group_node(node)
        elif isinstance(node, LatexMathNode):
            return self._convert_math_node(node)
        elif isinstance(node, LatexCommentNode):
            if self.options.preserve_comments:
                # Store comment in metadata (could extend AST to support comments)
                return None
            return None
        else:
            # Unknown node type - try to extract text
            return None

    def _convert_chars_node(self, node: Any) -> Text | None:
        """Convert a LaTeX chars node to Text.

        Parameters
        ----------
        node : LatexCharsNode
            LaTeX chars node

        Returns
        -------
        Text or None
            Text node

        """
        content = node.chars.strip()
        if content:
            return Text(content=content)
        return None

    def _convert_macro_node(self, node: Any) -> Node | list[Node] | None:
        """Convert a LaTeX macro node to AST node(s).

        Parameters
        ----------
        node : LatexMacroNode
            LaTeX macro node

        Returns
        -------
        Node, list[Node], or None
            Converted AST node(s)

        """
        macro_name = node.macroname

        # Sectioning commands
        if macro_name in ('section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph'):
            return self._convert_section(node)

        # Text formatting
        elif macro_name in ('textbf', 'textit', 'texttt', 'emph', 'underline', 'textsuperscript', 'textsubscript'):
            return self._convert_formatting(node)

        # Line break
        elif macro_name in ('\\', 'newline', 'linebreak'):
            return LineBreak(soft=False)

        # Horizontal rule
        elif macro_name == 'hrule':
            return ThematicBreak()

        # Title, author, date (metadata - skip in body)
        elif macro_name in ('title', 'author', 'date', 'maketitle'):
            return None

        # Itemize/enumerate handled in environment
        # Unknown macro
        else:
            # Try to extract argument text
            if node.nodeargd and hasattr(node.nodeargd, 'argnlist'):
                arg_nodes = []
                for arg in node.nodeargd.argnlist:
                    if arg and hasattr(arg, 'nodelist'):
                        for child in arg.nodelist:
                            converted = self._convert_node(child)
                            if converted:
                                if isinstance(converted, list):
                                    arg_nodes.extend(converted)
                                else:
                                    arg_nodes.append(converted)
                if arg_nodes:
                    return arg_nodes
            return None

    def _convert_section(self, node: Any) -> Heading:
        """Convert a LaTeX section command to Heading.

        Parameters
        ----------
        node : LatexMacroNode
            Section macro node

        Returns
        -------
        Heading
            Heading node

        """
        # Map LaTeX sections to heading levels
        level_map = {
            'section': 1,
            'subsection': 2,
            'subsubsection': 3,
            'paragraph': 4,
            'subparagraph': 5,
        }
        level = level_map.get(node.macroname, 1)

        # Extract content from first argument
        content_nodes: list[Node] = []

        # Try different ways to access the argument
        if node.nodeargd:
            # Try accessing via argnlist
            if hasattr(node.nodeargd, 'argnlist') and node.nodeargd.argnlist:
                first_arg = node.nodeargd.argnlist[0]
                if first_arg:
                    # Try nodelist
                    if hasattr(first_arg, 'nodelist') and first_arg.nodelist:
                        for child in first_arg.nodelist:
                            converted = self._convert_node(child)
                            if converted:
                                if isinstance(converted, list):
                                    content_nodes.extend(converted)
                                else:
                                    content_nodes.append(converted)

                    # Try latex_verbatim
                    if not content_nodes and hasattr(first_arg, 'latex_verbatim'):
                        text = first_arg.latex_verbatim().strip()
                        if text:
                            content_nodes.append(Text(content=text))

            # Try accessing via argspec attribute
            elif hasattr(node.nodeargd, 'argspec') and hasattr(node.nodeargd, 'arguments_spec_list'):
                # This is for newer versions of pylatexenc
                for arg_spec in node.nodeargd.arguments_spec_list:
                    if hasattr(arg_spec, 'nodelist') and arg_spec.nodelist:
                        for child in arg_spec.nodelist:
                            converted = self._convert_node(child)
                            if converted:
                                if isinstance(converted, list):
                                    content_nodes.extend(converted)
                                else:
                                    content_nodes.append(converted)
                        break  # Only process first argument

        # Fallback: try to get text from the whole node
        if not content_nodes:
            try:
                # Get the LaTeX source and extract text between braces
                if hasattr(node, 'latex_verbatim'):
                    latex_str = node.latex_verbatim()
                    # Extract text between first { and }
                    match = re.search(r'\{([^}]+)\}', latex_str)
                    if match:
                        text = match.group(1).strip()
                        if text:
                            content_nodes.append(Text(content=text))
            except Exception:
                pass

        return Heading(level=level, content=content_nodes)

    def _convert_formatting(self, node: Any) -> Node | list[Node]:
        """Convert LaTeX formatting command to AST node.

        Parameters
        ----------
        node : LatexMacroNode
            Formatting macro node

        Returns
        -------
        Node or list[Node]
            Formatted node

        """
        macro_name = node.macroname

        # Extract content from first argument
        content_nodes: list[Node] = []
        if node.nodeargd:
            if hasattr(node.nodeargd, 'argnlist') and node.nodeargd.argnlist:
                first_arg = node.nodeargd.argnlist[0]
                if first_arg:
                    if hasattr(first_arg, 'nodelist') and first_arg.nodelist:
                        for child in first_arg.nodelist:
                            converted = self._convert_node(child)
                            if converted:
                                if isinstance(converted, list):
                                    content_nodes.extend(converted)
                                else:
                                    content_nodes.append(converted)

                    # Try latex_verbatim if nodelist didn't work
                    if not content_nodes and hasattr(first_arg, 'latex_verbatim'):
                        text = first_arg.latex_verbatim().strip()
                        if text:
                            content_nodes.append(Text(content=text))

        # Fallback: try to get text from the whole node
        if not content_nodes:
            try:
                if hasattr(node, 'latex_verbatim'):
                    latex_str = node.latex_verbatim()
                    # Extract text between first { and }
                    match = re.search(r'\{([^}]+)\}', latex_str)
                    if match:
                        text = match.group(1).strip()
                        if text:
                            content_nodes.append(Text(content=text))
            except Exception:
                pass

        # Map to appropriate node type
        if macro_name == 'textbf':
            return Strong(content=content_nodes)
        elif macro_name in ('textit', 'emph'):
            return Emphasis(content=content_nodes)
        elif macro_name == 'texttt':
            # Convert to inline code
            text_content = self._extract_text(content_nodes)
            if not text_content:
                text_content = ""
            return Code(content=text_content)
        elif macro_name == 'underline':
            return Underline(content=content_nodes)
        elif macro_name == 'textsuperscript':
            return Superscript(content=content_nodes)
        elif macro_name == 'textsubscript':
            return Subscript(content=content_nodes)
        else:
            return content_nodes

    def _convert_environment_node(self, node: Any) -> Node | list[Node] | None:
        """Convert a LaTeX environment node to AST node(s).

        Parameters
        ----------
        node : LatexEnvironmentNode
            Environment node

        Returns
        -------
        Node, list[Node], or None
            Converted AST node(s)

        """
        env_name = node.environmentname

        # Math environments
        if env_name in ('equation', 'align', 'displaymath', 'eqnarray'):
            return self._convert_math_environment(node)

        # Lists
        elif env_name == 'itemize':
            return self._convert_itemize(node)
        elif env_name == 'enumerate':
            return self._convert_enumerate(node)

        # Quote environments
        elif env_name in ('quote', 'quotation'):
            return self._convert_quote(node)

        # Verbatim (code block)
        elif env_name == 'verbatim':
            return self._convert_verbatim(node)

        # Table
        elif env_name == 'tabular':
            return self._convert_tabular(node)

        # Figure (contains image)
        elif env_name == 'figure':
            return self._convert_figure(node)

        # Unknown environment - extract content
        else:
            if hasattr(node, 'nodelist'):
                children = []
                for child in node.nodelist:
                    converted = self._convert_node(child)
                    if converted:
                        if isinstance(converted, list):
                            children.extend(converted)
                        else:
                            children.append(converted)
                return children
            return None

    def _convert_math_environment(self, node: Any) -> MathBlock:
        """Convert math environment to MathBlock.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Math environment node

        Returns
        -------
        MathBlock
            Math block node

        """
        # Extract raw LaTeX content
        if hasattr(node, 'nodelist'):
            content = self._extract_raw_latex(node.nodelist)
        else:
            content = ""

        return MathBlock(content=content, notation="latex")

    def _convert_math_node(self, node: Any) -> MathInline | MathBlock:
        """Convert inline/display math to AST math node.

        Parameters
        ----------
        node : LatexMathNode
            Math node

        Returns
        -------
        MathInline or MathBlock
            Math node

        """
        # Extract math content
        if hasattr(node, 'nodelist'):
            content = self._extract_raw_latex(node.nodelist)
        else:
            content = node.latex_verbatim() if hasattr(node, 'latex_verbatim') else ""

        # Determine if inline or display mode
        if hasattr(node, 'displaytype') and node.displaytype == 'display':
            return MathBlock(content=content, notation="latex")
        else:
            return MathInline(content=content, notation="latex")

    def _convert_itemize(self, node: Any) -> List:
        """Convert itemize environment to List.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Itemize environment node

        Returns
        -------
        List
            List node

        """
        items = []
        if hasattr(node, 'nodelist'):
            for child in node.nodelist:
                if hasattr(child, 'macroname') and child.macroname == 'item':
                    item_nodes = []
                    # Get content after \item
                    if hasattr(child, 'nodeargd') and hasattr(child.nodeargd, 'argnlist'):
                        for arg in child.nodeargd.argnlist:
                            if arg and hasattr(arg, 'nodelist'):
                                for item_child in arg.nodelist:
                                    converted = self._convert_node(item_child)
                                    if converted:
                                        if isinstance(converted, list):
                                            item_nodes.extend(converted)
                                        else:
                                            item_nodes.append(converted)

                    # Wrap in paragraph if not empty
                    if item_nodes:
                        all_inline = all(
                            isinstance(n, (Text, Strong, Emphasis, Code, Link, Image)) for n in item_nodes
                        )
                        content = item_nodes if all_inline else [Text(content=self._extract_text(item_nodes))]
                        para = Paragraph(content=content)
                        items.append(ListItem(children=[para]))

        return List(ordered=False, items=items)

    def _convert_enumerate(self, node: Any) -> List:
        """Convert enumerate environment to ordered List.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Enumerate environment node

        Returns
        -------
        List
            Ordered list node

        """
        items = []
        if hasattr(node, 'nodelist'):
            for child in node.nodelist:
                if hasattr(child, 'macroname') and child.macroname == 'item':
                    item_nodes = []
                    # Get content after \item
                    if hasattr(child, 'nodeargd') and hasattr(child.nodeargd, 'argnlist'):
                        for arg in child.nodeargd.argnlist:
                            if arg and hasattr(arg, 'nodelist'):
                                for item_child in arg.nodelist:
                                    converted = self._convert_node(item_child)
                                    if converted:
                                        if isinstance(converted, list):
                                            item_nodes.extend(converted)
                                        else:
                                            item_nodes.append(converted)

                    # Wrap in paragraph
                    if item_nodes:
                        all_inline = all(
                            isinstance(n, (Text, Strong, Emphasis, Code, Link, Image)) for n in item_nodes
                        )
                        content = item_nodes if all_inline else [Text(content=self._extract_text(item_nodes))]
                        para = Paragraph(content=content)
                        items.append(ListItem(children=[para]))

        return List(ordered=True, items=items)

    def _convert_quote(self, node: Any) -> BlockQuote:
        """Convert quote environment to BlockQuote.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Quote environment node

        Returns
        -------
        BlockQuote
            Block quote node

        """
        children = []
        if hasattr(node, 'nodelist'):
            for child in node.nodelist:
                converted = self._convert_node(child)
                if converted:
                    if isinstance(converted, list):
                        children.extend(converted)
                    else:
                        children.append(converted)

        # Group inline nodes into paragraphs
        grouped_children = self._group_inline_nodes(children)
        return BlockQuote(children=grouped_children)

    def _convert_verbatim(self, node: Any) -> CodeBlock:
        """Convert verbatim environment to CodeBlock.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Verbatim environment node

        Returns
        -------
        CodeBlock
            Code block node

        """
        # Extract raw content - verbatim should preserve everything
        content = ""

        # Try to get raw content directly
        if hasattr(node, 'latex_verbatim'):
            try:
                full_text = node.latex_verbatim()
                # Extract content between \begin{verbatim} and \end{verbatim}
                match = re.search(r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}', full_text, re.DOTALL)
                if match:
                    content = match.group(1)
                    # Remove leading/trailing newlines but preserve internal formatting
                    content = content.strip('\n')
            except Exception:
                pass

        # Fallback to nodelist
        if not content and hasattr(node, 'nodelist'):
            content = self._extract_raw_latex(node.nodelist)

        return CodeBlock(content=content)

    def _convert_tabular(self, node: Any) -> Table | None:
        """Convert tabular environment to Table.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Tabular environment node

        Returns
        -------
        Table or None
            Table node

        """
        # Basic table parsing - this is simplified
        # A full implementation would parse table structure from LaTeX
        # For now, return None and let it be handled as text
        # Full table parsing would require more sophisticated LaTeX parsing
        return None

    def _convert_figure(self, node: Any) -> Image | None:
        """Convert figure environment to Image.

        Parameters
        ----------
        node : LatexEnvironmentNode
            Figure environment node

        Returns
        -------
        Image or None
            Image node

        """
        # Look for \includegraphics command
        if hasattr(node, 'nodelist'):
            for child in node.nodelist:
                if hasattr(child, 'macroname') and child.macroname == 'includegraphics':
                    # Extract image path from argument
                    if hasattr(child, 'nodeargd') and hasattr(child.nodeargd, 'argnlist'):
                        for arg in child.nodeargd.argnlist:
                            if arg and hasattr(arg, 'nodelist'):
                                path = self._extract_text(self._convert_group_node(arg))
                                if path:
                                    return Image(url=path, alt_text="")

        return None

    def _convert_group_node(self, node: Any) -> list[Node]:
        """Convert a LaTeX group node to list of AST nodes.

        Parameters
        ----------
        node : LatexGroupNode
            Group node

        Returns
        -------
        list[Node]
            List of AST nodes

        """
        children = []
        if hasattr(node, 'nodelist'):
            for child in node.nodelist:
                converted = self._convert_node(child)
                if converted:
                    if isinstance(converted, list):
                        children.extend(converted)
                    else:
                        children.append(converted)
        return children

    def _extract_text(self, nodes: Node | list[Node]) -> str:
        """Extract plain text from AST nodes.

        Parameters
        ----------
        nodes : Node or list[Node]
            AST node(s)

        Returns
        -------
        str
            Extracted text

        """
        if not nodes:
            return ""

        if isinstance(nodes, Text):
            return nodes.content
        elif isinstance(nodes, (Strong, Emphasis, Underline, Superscript, Subscript)):
            return self._extract_text(nodes.content)
        elif isinstance(nodes, Code):
            return nodes.content
        elif isinstance(nodes, list):
            return " ".join(self._extract_text(n) for n in nodes)
        else:
            return ""

    def _extract_raw_latex(self, nodelist: list[Any]) -> str:
        """Extract raw LaTeX content from node list.

        Parameters
        ----------
        nodelist : list
            List of LaTeX nodes

        Returns
        -------
        str
            Raw LaTeX content

        """
        parts = []
        for node in nodelist:
            if hasattr(node, 'latex_verbatim'):
                parts.append(node.latex_verbatim())
            elif hasattr(node, 'chars'):
                parts.append(node.chars)
        return "".join(parts)

    def _group_inline_nodes(self, nodes: list[Node]) -> list[Node]:
        """Group consecutive inline nodes into paragraphs.

        Parameters
        ----------
        nodes : list[Node]
            List of nodes

        Returns
        -------
        list[Node]
            List with inline nodes grouped into paragraphs

        """
        grouped: list[Node] = []
        current_inline: list[Node] = []

        inline_types = (Text, Strong, Emphasis, Code, Link, Image, Underline, Superscript, Subscript, MathInline)

        for node in nodes:
            if isinstance(node, inline_types):
                current_inline.append(node)
            else:
                # Flush current inline nodes as paragraph
                if current_inline:
                    grouped.append(Paragraph(content=current_inline))
                    current_inline = []
                grouped.append(node)

        # Flush remaining inline nodes
        if current_inline:
            grouped.append(Paragraph(content=current_inline))

        return grouped

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from LaTeX document.

        Parameters
        ----------
        document : Any
            Document content or AST

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Use metadata extracted from preamble
        if 'title' in self.document_metadata:
            metadata.title = self.document_metadata['title']
        if 'author' in self.document_metadata:
            metadata.author = self.document_metadata['author']
        if 'date' in self.document_metadata:
            # Store in custom field as LaTeX date is freeform
            metadata.custom['date'] = self.document_metadata['date']

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="latex",
    extensions=[".tex", ".latex"],
    mime_types=["text/x-tex", "application/x-tex", "application/x-latex"],
    magic_bytes=[],  # LaTeX is plain text, no magic bytes
    parser_class="LatexParser",
    renderer_class="all2md.renderers.latex.LatexRenderer",
    renders_as_string=True,
    parser_required_packages=[("pylatexenc", "pylatexenc", "2.10")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="LaTeX parsing requires the 'pylatexenc' package. Install it with: pip install pylatexenc",
    parser_options_class="LatexParserOptions",
    renderer_options_class="LatexOptions",
    description="Parse and render LaTeX format",
    priority=10
)
