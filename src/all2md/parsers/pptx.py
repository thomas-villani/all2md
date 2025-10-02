#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/pptx.py
"""PPTX to AST converter.

This module provides conversion from Microsoft PowerPoint presentations to AST representation.
It replaces direct markdown string generation with structured AST building,
enabling multiple rendering strategies and improved testability.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Union

from all2md import DependencyError, PptxOptions
from all2md.exceptions import ZipFileSecurityError, InputError
from all2md.parsers.pptx2markdown import logger
from all2md.utils.inputs import validate_and_convert_input, parse_page_ranges, format_special_text
from all2md.utils.security import validate_zip_archive

if TYPE_CHECKING:
    from pptx.presentation import Presentation
    from pptx.shapes.base import BaseShape
    from pptx.text.text import TextFrame

from all2md.ast import (
    Document,
    Emphasis,
    Heading,
    Image,
    List,
    ListItem,
    Node,
    Paragraph as AstParagraph,
    Strong,
    Table as AstTable,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.utils.attachments import process_attachment, extract_pptx_image_data, create_attachment_sequencer, \
    generate_attachment_filename
from all2md.converter_metadata import ConverterMetadata
from all2md.options import PptxOptions
from all2md.parsers.base import BaseParser
from all2md.utils.metadata import OFFICE_FIELD_MAPPING, DocumentMetadata, map_properties_to_metadata

logger = logging.getLogger(__name__)



class PptxToAstConverter(BaseParser):
    """Convert PPTX to AST representation.

    This converter parses PowerPoint presentations using python-pptx and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : PptxOptions or None, default = None
        Conversion options

    """

    def __init__(
        self,
        options: PptxOptions | None = None
    ):
        options = options or PptxOptions()
        super().__init__(options)
        self.options: PptxOptions = options
        
        self._current_slide_num = 0
        self._base_filename = "presentation"
        self._attachment_sequencer = create_attachment_sequencer()


    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse PPTX input into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The PPTX document to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw PPTX bytes

        Returns
        -------
        Document
            AST Document node representing the parsed PPTX structure

        Raises
        ------
        MarkdownConversionError
            If parsing fails due to invalid format or corruption
        DependencyError
            If python-pptx is not installed

        """
        try:
            from pptx import Presentation
            from pptx.presentation import Presentation as PresentationType

        except ImportError as e:
            raise DependencyError(
                converter_name="pptx",
                missing_packages=[("python-pptx", ">=1.0.2")],
            ) from e

        # Validate and convert input
        try:

            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "pptx.Presentation objects"]
            )

            # Validate ZIP archive security for file-based inputs
            if input_type in ("path", "file") and not isinstance(doc_input, PresentationType):
                validate_zip_archive(doc_input if input_type == "path" else input_data)

            # Open presentation based on input type
            if input_type == "object" and isinstance(doc_input, PresentationType):
                prs = doc_input
            else:
                prs = Presentation(doc_input)

        except ZipFileSecurityError:
            raise

        except Exception as e:
            raise InputError(
                f"Failed to open PPTX presentation: {e!r}",
                parameter_name="input_data",
                parameter_value=input_data,
                original_error=e
            ) from e

        # Extract base filename for standardized attachment naming
        if input_type == "path" and isinstance(doc_input, (str, Path)):
            self._base_filename = Path(doc_input).stem
        else:
            self._base_filename = "presentation"

        # Convert PPTX to AST
        return self.convert_to_ast(prs)

    def convert_to_ast(self, prs: "Presentation") -> Document:
        """Convert PPTX presentation to AST Document.

        Parameters
        ----------
        prs : Presentation
            PPTX presentation to convert

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        # Determine which slides to process
        all_slides = list(prs.slides)
        total_slides = len(all_slides)

        if self.options.slides:
            # Parse slide range specification
            slide_indices = parse_page_ranges(self.options.slides, total_slides)
        else:
            # Process all slides
            slide_indices = list(range(total_slides))

        # Process selected slides
        for idx in slide_indices:
            slide = all_slides[idx]
            self._current_slide_num = idx + 1  # 1-based for display
            slide_nodes = self._process_slide_to_ast(slide)
            if slide_nodes:
                children.extend(slide_nodes)

                # Add slide separator (thematic break) after every slide
                children.append(ThematicBreak())

        # Extract and attach metadata
        metadata = self.extract_metadata(prs)
        return Document(children=children, metadata=metadata.to_dict())

    def _process_slide_to_ast(self, slide: Any) -> list[Node]:
        """Process a PPTX slide to AST nodes.

        Parameters
        ----------
        slide : Slide
            PPTX slide to process

        Returns
        -------
        list of Node
            List of AST nodes representing the slide

        """
        nodes: list[Node] = []

        # Process slide title if present and enabled
        if self.options.include_titles_as_h2 and slide.shapes.title and slide.shapes.title.text.strip():
            title_text = slide.shapes.title.text.strip()
            if self.options.include_slide_numbers:
                title_text = f"Slide {self._current_slide_num}: {title_text}"

            # Slide titles are level 2 headings
            nodes.append(Heading(level=2, content=[Text(content=title_text)]))

        # Process all shapes in the slide
        for shape in slide.shapes:
            # Skip the title shape if it was already processed as a heading
            if self.options.include_titles_as_h2 and shape == slide.shapes.title:
                continue

            shape_nodes = self._process_shape_to_ast(shape)
            if shape_nodes:
                if isinstance(shape_nodes, list):
                    nodes.extend(shape_nodes)
                else:
                    nodes.append(shape_nodes)

        return nodes

    def _process_shape_to_ast(self, shape: "BaseShape") -> Node | list[Node] | None:
        """Process a PPTX shape to AST nodes.

        Parameters
        ----------
        shape : BaseShape
            PPTX shape to process

        Returns
        -------
        Node, list of Node, or None
            Resulting AST node(s)

        """
        # Check if shape has text_frame
        if hasattr(shape, "text_frame") and shape.text_frame:
            return self._process_text_frame_to_ast(shape.text_frame)

        # Check if shape is a table
        if hasattr(shape, "table"):
            return self._process_table_to_ast(shape.table)

        # Check if shape is an image
        if hasattr(shape, "image"):
            return self._process_image_to_ast(shape)

        from pptx.shapes.graphfrm import GraphicFrame
        if isinstance(shape, GraphicFrame) and hasattr(shape, "chart"):
            return self._process_chart_to_ast(shape.chart)

        # For other shapes, skip or handle as needed
        return None

    def _process_chart_to_ast(self, chart) -> AstTable | None:
        """Process a PPTX chart to AST Table node.

        Parameters
        ----------
        chart : Chart
            PPTX chart to convert

        Returns
        -------
        AstTable or None
            Table node representing chart data

        """
        from pptx.enum.chart import XL_CHART_TYPE

        # Check if this is a scatter plot (XY chart)
        try:
            chart_type = chart.chart_type
            is_scatter = chart_type == XL_CHART_TYPE.XY_SCATTER
        except Exception:
            is_scatter = False

        if is_scatter:
            # Process scatter plot as X/Y table
            return self._process_scatter_chart_to_table(chart)
        else:
            # Process standard chart as category/series table
            return self._process_standard_chart_to_table(chart)

    def _process_scatter_chart_to_table(self, chart) -> AstTable | None:
        """Process scatter plot to AST Table with X/Y rows.

        For each series, creates two rows (X and Y values) with point numbers as columns.

        Parameters
        ----------
        chart : Chart
            PPTX scatter chart

        Returns
        -------
        AstTable or None
            Table with X/Y rows for each series

        """
        all_rows: list[TableRow] = []
        max_points = 0

        # First pass: collect all series data and determine max points
        series_data: list[tuple[str, list[float], list[float]]] = []

        for series in chart.series:
            try:
                x_values: list[float] = []
                y_values: list[float] = []

                # Try to extract X and Y values from series XML
                if hasattr(series, '_element'):
                    element = series._element
                    ns = {'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart'}

                    # Extract X values
                    x_val_ref = element.find('.//c:xVal', ns)
                    if x_val_ref is not None:
                        num_cache = x_val_ref.find('.//c:numCache', ns)
                        if num_cache is not None:
                            pt_elements = num_cache.findall('.//c:pt', ns)
                            for pt in pt_elements:
                                v_element = pt.find('c:v', ns)
                                if v_element is not None and v_element.text:
                                    x_values.append(float(v_element.text))

                    # Extract Y values
                    y_val_ref = element.find('.//c:yVal', ns)
                    if y_val_ref is not None:
                        num_cache = y_val_ref.find('.//c:numCache', ns)
                        if num_cache is not None:
                            pt_elements = num_cache.findall('.//c:pt', ns)
                            for pt in pt_elements:
                                v_element = pt.find('c:v', ns)
                                if v_element is not None and v_element.text:
                                    y_values.append(float(v_element.text))

                # Only add if we have both X and Y values of equal length
                if x_values and y_values and len(x_values) == len(y_values):
                    series_data.append((series.name or "Series", x_values, y_values))
                    max_points = max(max_points, len(x_values))
                elif hasattr(series, 'values') and series.values:
                    # Fallback: use Y values only with sequential X values
                    y_values = list(series.values)
                    x_values = list(range(len(y_values)))
                    series_data.append((series.name or "Series", x_values, y_values))
                    max_points = max(max_points, len(y_values))

            except Exception:
                # Skip series that can't be processed
                continue

        if not series_data:
            return None

        # Create header row with point numbers
        header_cells = [TableCell(content=[Text(content="Series")])]
        for i in range(max_points):
            header_cells.append(TableCell(content=[Text(content=f"Point {i+1}")]))
        header_row = TableRow(cells=header_cells, is_header=True)

        # Create data rows (X and Y for each series)
        for series_name, x_values, y_values in series_data:
            # X row
            x_cells = [TableCell(content=[Text(content=f"{series_name} X")])]
            for val in x_values:
                x_cells.append(TableCell(content=[Text(content=str(val))]))
            all_rows.append(TableRow(cells=x_cells))

            # Y row
            y_cells = [TableCell(content=[Text(content=f"{series_name} Y")])]
            for val in y_values:
                y_cells.append(TableCell(content=[Text(content=str(val))]))
            all_rows.append(TableRow(cells=y_cells))

        return AstTable(header=header_row, rows=all_rows)

    def _process_standard_chart_to_table(self, chart) -> AstTable | None:
        """Process standard chart (bar, column, line, pie) to AST Table.

        Creates table with categories as columns and series as rows.

        Parameters
        ----------
        chart : Chart
            PPTX chart (non-scatter)

        Returns
        -------
        AstTable or None
            Table with categories as headers and series as rows

        """
        # Extract categories (x-axis)
        categories: list[str] = []
        try:
            if hasattr(chart, 'plots') and chart.plots:
                categories = [
                    cat.label if hasattr(cat, "label") else str(cat)
                    for cat in chart.plots[0].categories
                    if hasattr(cat, "label") or cat
                ]
        except Exception:
            pass

        # Extract series data
        series_rows: list[tuple[str, list[Any]]] = []
        for series in chart.series:
            try:
                if hasattr(series, 'values') and series.values:
                    values = list(series.values)
                    series_name = series.name or "Series"
                    series_rows.append((series_name, values))
            except Exception:
                # Skip series that can't be processed
                continue

        if not series_rows:
            return None

        # Determine number of columns from data
        num_cols = max(len(values) for _, values in series_rows) if series_rows else 0

        if num_cols == 0:
            return None

        # Create header row
        header_cells = [TableCell(content=[Text(content="Category")])]
        if categories and len(categories) == num_cols:
            # Use actual category names
            for cat in categories:
                header_cells.append(TableCell(content=[Text(content=str(cat))]))
        else:
            # Use generic column numbers
            for i in range(num_cols):
                header_cells.append(TableCell(content=[Text(content=f"Col {i+1}")]))

        header_row = TableRow(cells=header_cells, is_header=True)

        # Create data rows for each series
        data_rows: list[TableRow] = []
        for series_name, values in series_rows:
            row_cells = [TableCell(content=[Text(content=series_name)])]
            for val in values:
                # Convert value to string, handling None
                val_str = str(val) if val is not None else ""
                row_cells.append(TableCell(content=[Text(content=val_str)]))
            data_rows.append(TableRow(cells=row_cells))

        return AstTable(header=header_row, rows=data_rows)

    def _process_text_frame_to_ast(self, frame: "TextFrame") -> list[Node] | None:
        """Process a text frame to AST nodes.

        Parameters
        ----------
        frame : TextFrame
            Text frame to process

        Returns
        -------
        list of Node or None
            List of AST nodes (paragraphs, lists, etc.)

        """

        nodes: list[Node] = []
        slide_context = _analyze_slide_context(frame)

        # Track list accumulation
        current_list: List | None = None
        current_list_type: str | None = None

        for paragraph in frame.paragraphs:
            if not paragraph.text.strip():
                continue

            # Detect if this is a list item
            is_list_item, list_type = _detect_list_item(paragraph, slide_context)

            if is_list_item:
                # Check if we need to start a new list or continue current
                if current_list is None or current_list_type != list_type:
                    # Finalize previous list
                    if current_list:
                        nodes.append(current_list)

                    # Start new list
                    current_list_type = list_type
                    current_list = List(ordered=(list_type == "number"), items=[], tight=True)

                # Add item to current list
                item_content = self._process_paragraph_runs_to_inline(paragraph)
                if item_content:
                    list_item = ListItem(children=[AstParagraph(content=item_content)])
                    current_list.items.append(list_item)
            else:
                # Not a list item - finalize any current list
                if current_list:
                    nodes.append(current_list)
                    current_list = None
                    current_list_type = None

                # Process as regular paragraph
                para_content = self._process_paragraph_runs_to_inline(paragraph)
                if para_content:
                    nodes.append(AstParagraph(content=para_content))

        # Finalize any remaining list
        if current_list:
            nodes.append(current_list)

        return nodes if nodes else None

    def _process_paragraph_runs_to_inline(self, paragraph: Any) -> list[Node]:
        """Process paragraph runs to inline AST nodes.

        Parameters
        ----------
        paragraph : Paragraph
            Paragraph containing runs

        Returns
        -------
        list of Node
            List of inline AST nodes

        """
        result: list[Node] = []

        # Group runs by formatting to avoid excessive nesting
        grouped_runs: list[tuple[str, tuple[bool, bool, bool] | None]] = []
        current_text: list[str] = []
        current_format: tuple[bool, bool, bool] | None = None

        for run in paragraph.runs:
            text = run.text
            if not text.strip():  # Skip empty runs
                continue

            # Get formatting key (bold, italic, underline)
            format_key = (
                run.font.bold or False,
                run.font.italic or False,
                run.font.underline or False,
            )

            # Start new group if format changes
            if format_key != current_format:
                if current_text:
                    # Join with single space and strip
                    grouped_runs.append((" ".join(current_text).strip(), current_format))
                    current_text = []
                current_format = format_key

            current_text.append(text.strip())

        # Add final group
        if current_text:
            grouped_runs.append((" ".join(current_text).strip(), current_format))

        # Convert groups to AST nodes
        for text, format_key in grouped_runs:
            if not text:
                continue

            # Build inline nodes with formatting
            inline_node: Node = Text(content=text)

            if format_key:
                # Apply formatting layers from innermost to outermost
                if format_key[2]:  # underline
                    inline_node = Underline(content=[inline_node])
                if format_key[0]:  # bold
                    inline_node = Strong(content=[inline_node])
                if format_key[1]:  # italic
                    inline_node = Emphasis(content=[inline_node])

            result.append(inline_node)

        return result

    def _process_table_to_ast(self, table: Any) -> AstTable | None:
        """Process a PPTX table to AST Table node.

        Parameters
        ----------
        table : Table
            PPTX table to convert

        Returns
        -------
        AstTable or None
            Table node if table has content

        """
        if len(table.rows) == 0:
            return None

        # First row is header
        header_cells: list[TableCell] = []
        for cell in table.rows[0].cells:
            if cell.text_frame:
                cell_content = self._process_paragraph_runs_to_inline_simple(cell.text_frame)
                header_cells.append(TableCell(content=cell_content))
            else:
                header_cells.append(TableCell(content=[]))

        header_row = TableRow(cells=header_cells, is_header=True)

        # Data rows (skip first row which is header)
        data_rows: list[TableRow] = []
        for i, row in enumerate(table.rows):
            if i == 0:
                continue  # Skip header row
            row_cells: list[TableCell] = []
            for cell in row.cells:
                if cell.text_frame:
                    cell_content = self._process_paragraph_runs_to_inline_simple(cell.text_frame)
                    row_cells.append(TableCell(content=cell_content))
                else:
                    row_cells.append(TableCell(content=[]))
            data_rows.append(TableRow(cells=row_cells))

        return AstTable(header=header_row, rows=data_rows)

    def _process_paragraph_runs_to_inline_simple(self, frame: "TextFrame") -> list[Node]:
        """Process all paragraphs in a text frame to inline nodes (for tables).

        Parameters
        ----------
        frame : TextFrame
            Text frame to process

        Returns
        -------
        list of Node
            List of inline nodes

        """
        result: list[Node] = []

        for paragraph in frame.paragraphs:
            para_inlines = self._process_paragraph_runs_to_inline(paragraph)
            result.extend(para_inlines)

            # Add space between paragraphs (except last)
            if paragraph != frame.paragraphs[-1]:
                result.append(Text(content=" "))

        return result

    def _process_image_to_ast(self, shape: Any) -> Image | None:
        """Process an image shape to AST Image node.

        Parameters
        ----------
        shape : Shape
            Image shape to process

        Returns
        -------
        Image or None
            Image node if image can be processed

        """

        try:
            # Extract image data
            image_data, extension = extract_pptx_image_data(shape)

            if not image_data:
                return None

            # Use sequencer if available
            if self._attachment_sequencer:
                image_filename, _ = self._attachment_sequencer(
                    base_stem=self._base_filename,
                    format_type="general",
                    extension=extension or "png"
                )
            else:
                image_filename = generate_attachment_filename(
                    base_stem=self._base_filename,
                    format_type="general",
                    sequence_num=self._current_slide_num,
                    extension=extension or "png"
                )

            # Process attachment
            processed_image = process_attachment(
                attachment_data=image_data,
                attachment_name=image_filename,
                alt_text="image",
                attachment_mode=self.options.attachment_mode,
                attachment_output_dir=self.options.attachment_output_dir,
                attachment_base_url=self.options.attachment_base_url,
                is_image=True,
                alt_text_mode=self.options.alt_text_mode,
            )

            # Parse the markdown image string
            match = re.match(r'^!\[([^]]*)](?:\(([^)]+)\))?$', processed_image)
            if match:
                alt_text = match.group(1)
                url = match.group(2) or ""
                return Image(url=url, alt_text=alt_text, title=None)

        except Exception as e:
            logger.debug(f"Failed to process image: {e}")
            return None

        return None

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from PPTX presentation.

        Parameters
        ----------
        document : Presentation
            python-pptx Presentation object

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        if not hasattr(document, 'core_properties'):
            metadata = DocumentMetadata()
        else:
            props = document.core_properties
            # Use the utility function for standard metadata extraction
            metadata = map_properties_to_metadata(props, OFFICE_FIELD_MAPPING)

            # Add PPTX-specific custom metadata
            custom_properties = ['last_modified_by', 'revision', 'comments']
            for prop_name in custom_properties:
                if hasattr(props, prop_name):
                    value = getattr(props, prop_name)
                    if value:
                        metadata.custom[prop_name] = value

        # Add slide count as custom metadata
        try:
            metadata.custom['slide_count'] = len(document.slides)
        except Exception:
            pass

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pptx",
    extensions=[".pptx"],
    mime_types=["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    parser_class=PptxToAstConverter,
    renderer_class=None,
    required_packages=[("python-pptx", "pptx", "")],
    import_error_message="PPTX conversion requires 'python-pptx'. Install with: pip install python-pptx",
    options_class=PptxOptions,
    description="Convert PowerPoint presentations to Markdown",
    priority=7
)


def _detect_list_formatting_xml(paragraph: Any) -> tuple[str | None, str | None]:
    """Detect list formatting using XML element inspection.

    Parameters
    ----------
    paragraph : Any
        The paragraph object to inspect

    Returns
    -------
    tuple[str | None, str | None]
        (list_type, list_style) where list_type is "bullet" or "number"
    """
    try:
        # Access paragraph properties XML element
        if not hasattr(paragraph, '_p') or paragraph._p is None:
            return None, None

        pPr = paragraph._p.pPr
        if pPr is None:
            return None, None

        # Check for bullet character element
        bu_char = pPr.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}buChar')
        if bu_char is not None:
            char = bu_char.get('char', '•')
            return "bullet", char

        # Check for auto numbering element
        bu_auto_num = pPr.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}buAutoNum')
        if bu_auto_num is not None:
            num_type = bu_auto_num.get('type', 'arabicPeriod')
            return "number", num_type

        # Check for bullet font (indicates some form of bullet formatting)
        bu_font = pPr.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}buFont')
        if bu_font is not None:
            return "bullet", "default"

    except Exception:
        # Fall back gracefully if XML parsing fails
        pass

    return None, None


def _detect_list_item(paragraph: Any, slide_context: dict | None = None) -> tuple[bool, str]:
    """Detect if a paragraph is a list item and determine the list type.

    Uses XML-based detection first, then falls back to heuristics.

    Parameters
    ----------
    paragraph : Any
        The paragraph object to analyze
    slide_context : dict, optional
        Context about the slide to help with detection

    Returns
    -------
    tuple[bool, str]
        (is_list_item, list_type) where list_type is "bullet" or "number"
    """
    # First try XML-based detection for proper list formatting
    xml_list_type, xml_list_style = _detect_list_formatting_xml(paragraph)
    if xml_list_type:
        return True, xml_list_type

    # Fall back to level-based detection
    if not hasattr(paragraph, 'level') or paragraph.level is None:
        return False, "bullet"

    level = paragraph.level
    if level > 0:
        # Use slide context to help determine list type for indented items
        if slide_context and slide_context.get('has_numbered_list', False):
            return True, "number"
        return True, "bullet"

    # For level 0, use heuristics as last resort
    text = paragraph.text.strip() if hasattr(paragraph, 'text') else ""
    if not text:
        return False, "bullet"

    # Check for explicit numbered list patterns in text
    if re.match(r'^\d+[\.\)]\s', text):
        return True, "number"

    # Check if this looks like a numbered list item based on context
    if (slide_context and slide_context.get('has_numbered_list', False) and
        ('item' in text.lower() or 'first' in text.lower() or
         'second' in text.lower() or 'third' in text.lower())):
        return True, "number"

    # Use heuristics for bullet lists - shorter text that doesn't look like a title/header
    words = text.split()
    if len(words) <= 8 and not text.endswith(('.', '!', '?', ':')):
        # Additional checks to avoid false positives
        if not (text.lower().startswith(('slide', 'title', 'chapter')) or
                len(words) <= 3 and text.istitle()):
            return True, "bullet"

    return False, "bullet"


def _analyze_slide_context(frame: Any) -> dict:
    """Analyze the text frame to understand the slide context for better list detection.

    Parameters
    ----------
    frame : Any
        The text frame to analyze

    Returns
    -------
    dict
        Context information about the slide
    """
    context = {
        'has_numbered_list': False,
        'paragraph_count': 0,
        'max_level': 0
    }

    for paragraph in frame.paragraphs:
        if not paragraph.text.strip():
            continue

        context['paragraph_count'] += 1

        # Track maximum indentation level
        level = getattr(paragraph, 'level', 0) or 0
        context['max_level'] = max(context['max_level'], level)

        # Check if any paragraph looks like a numbered list
        text = paragraph.text.strip()
        if (re.match(r'^\d+[\.\)]\s', text) or
            'numbered' in text.lower() or
            'first item' in text.lower() or
            'second item' in text.lower() or
            'third item' in text.lower()):
            context['has_numbered_list'] = True

    return context


