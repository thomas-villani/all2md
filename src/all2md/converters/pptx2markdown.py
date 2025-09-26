"""PowerPoint presentation to Markdown conversion module.

This module provides functionality to extract content from Microsoft PowerPoint
presentations (PPTX format) and convert it to structured Markdown. It processes
slides individually, extracting text content, formatting, tables, and embedded
images while preserving the logical structure and hierarchy of the presentation.

The converter analyzes each slide's layout and content, handling various slide
elements including title text, body content, tables, charts, and embedded media.
Special attention is paid to maintaining the presentation's logical flow and
structure in the resulting Markdown format.

Key Features
------------
- Slide-by-slide content extraction and conversion
- Text formatting preservation (bold, italic, lists)
- Table extraction with proper Markdown table formatting
- Image embedding as base64 data URIs
- Chart and graphic frame handling
- Hierarchical content structure preservation
- Bullet point and numbering conversion
- Slide title and content separation

Supported Elements
------------------
- Text content with formatting (bold, italic, underline)
- Slide titles and subtitles
- Bulleted and numbered lists with indentation
- Tables with cell content and structure
- Images and graphics (embedded as base64)
- Charts and diagrams (metadata extraction)
- Text boxes and content placeholders

Processing Features
-------------------
- Automatic slide numbering and separation
- Paragraph-level formatting detection
- List indentation and nesting preservation
- Image format detection and encoding
- Error handling for corrupted or complex elements
- Logging for debugging and issue tracking

Dependencies
------------
- python-pptx: For PowerPoint file parsing and content extraction
- imghdr: For image format detection
- base64: For image encoding
- logging: For debug and error reporting

Examples
--------
Basic presentation conversion:

    >>> from all2md.converters.pptx2markdown import pptx_to_markdown
    >>> with open('presentation.pptx', 'rb') as f:
    ...     markdown = pptx_to_markdown(f)
    >>> print(markdown)

Note
----
Requires python-pptx package. Complex animations, transitions, and some
advanced PowerPoint features will be omitted in the conversion process.
The focus is on extracting textual and structural content.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#
import logging
from pathlib import Path
from typing import IO, Any, Union

from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.graphfrm import GraphicFrame
from pptx.util import Inches

from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MarkdownConversionError
from all2md.options import PptxOptions
from all2md.utils.attachments import extract_pptx_image_data, generate_attachment_filename, process_attachment
from all2md.utils.inputs import format_special_text, validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled
from all2md.utils.security import validate_zip_archive

logger = logging.getLogger(__name__)


def _process_paragraph_format(paragraph: Any) -> list[tuple[str, str]]:
    """Extract formatting information from a paragraph."""
    formats = []
    if paragraph.level:  # Handle indentation levels
        formats.append(("  " * paragraph.level, ""))
    return formats


def _process_run_format(run: Any, text: str = "", md_options=None) -> str:
    """Apply formatting to text run based on font properties."""
    content = text

    # Apply bold and italic formatting with standard markdown
    if run.font.bold:
        content = f"**{content}**"
    if run.font.italic:
        content = f"*{content}*"

    # Apply underline formatting using format_special_text
    if run.font.underline:
        underline_mode = md_options.underline_mode if md_options else "html"
        content = format_special_text(content, "underline", underline_mode)

    return content


def _process_text_frame(frame: Any, md_options=None) -> str:
    """Convert a text frame to markdown, preserving formatting."""
    lines = []

    for paragraph in frame.paragraphs:
        if not paragraph.text.strip():
            continue

        para_formats = _process_paragraph_format(paragraph)
        text_parts = []

        for run in paragraph.runs:
            text = run.text.strip()
            if not text:
                continue

            # Apply run-level formatting using the updated function
            text = _process_run_format(run, text, md_options)
            text_parts.append(text)

        # Combine runs and apply paragraph-level formatting
        if text_parts:
            line = " ".join(text_parts)
            for start, end in para_formats:
                line = f"{start}{line}{end}"
            lines.append(line)

    return "\n".join(lines)


def _process_table(table: Any, md_options=None) -> str:
    """Convert a table shape to markdown format."""
    markdown_rows = []

    # Process headers
    if table.rows:
        header_cells = []
        for cell in table.rows[0].cells:
            cell_text = _process_text_frame(cell.text_frame, md_options)
            header_cells.append(cell_text.replace("\n", " "))

        markdown_rows.append("| " + " | ".join(header_cells) + " |")
        markdown_rows.append("| " + " | ".join(["---"] * len(header_cells)) + " |")

        first = False
        # Process data rows
        for row in table.rows:
            if not first:
                first = True
                continue
            row_cells = []
            for cell in row.cells:
                cell_text = _process_text_frame(cell.text_frame, md_options)
                row_cells.append(cell_text.replace("\n", " "))
            markdown_rows.append("| " + " | ".join(row_cells) + " |")

    return "\n".join(markdown_rows)


def _process_shape(
        shape: Any, options: PptxOptions, base_filename: str = "presentation", slide_num: int = 1,
        img_counter: dict | None = None
        ) -> str | None:
    """Process a single shape and convert to markdown."""
    if img_counter is None:
        img_counter = {}

    # Handle text boxes and other shapes with text
    if shape.has_text_frame:
        md_options = options.markdown_options if options else None
        return _process_text_frame(shape.text_frame, md_options)

    # Handle tables
    elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
        md_options = options.markdown_options if options else None
        return _process_table(shape.table, md_options)

    # Handle pictures
    elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        # Extract image data if needed
        if options.attachment_mode != "skip":
            image_data = extract_pptx_image_data(shape)
        else:
            logger.info(f"Skipping image in slide {slide_num} (attachment_mode=skip): {shape.alt_text or 'image'}")
            image_data = None
        if image_data and not isinstance(image_data, bytes):
            image_data = None
        alt_text = shape.alt_text or "image"
        # Get next sequence number for this slide
        slide_key = f"slide_{slide_num}"
        img_counter[slide_key] = img_counter.get(slide_key, 0) + 1
        sequence_num = img_counter[slide_key]

        image_filename = generate_attachment_filename(
            base_stem=base_filename,
            format_type="pptx",
            slide_num=slide_num,
            sequence_num=sequence_num,
            extension="png"
        )

        # Process image using unified attachment handling
        return process_attachment(
            attachment_data=image_data,
            attachment_name=image_filename,
            alt_text=alt_text,
            attachment_mode=options.attachment_mode,
            attachment_output_dir=options.attachment_output_dir,
            attachment_base_url=options.attachment_base_url,
            is_image=True,
        )

    # Handle charts (convert to tables if possible)
    elif isinstance(shape, GraphicFrame) and hasattr(shape, "chart"):
        chart = shape.chart
        # Basic chart data extraction
        data_rows = []

        # Check if this is a scatter plot (XY chart)
        try:
            chart_type = chart.chart_type
            is_scatter = chart_type == XL_CHART_TYPE.XY_SCATTER
        except Exception:
            is_scatter = False

        if is_scatter:
            # For scatter plots, extract X,Y pairs from XML
            for series in chart.series:
                try:
                    x_values = []
                    y_values = []

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

                    # Create table with X,Y pairs if we found both
                    if x_values and y_values and len(x_values) == len(y_values):
                        data_rows.append(f"| {series.name} X | " + " | ".join(str(x) for x in x_values) + " |")
                        data_rows.append(f"| {series.name} Y | " + " | ".join(str(y) for y in y_values) + " |")
                        if len(data_rows) >= 2 and "---" not in data_rows[-2]:
                            data_rows.insert(-2, "| --- | " + " | ".join(["---"] * len(x_values)) + " |")
                    else:
                        # Fallback to just Y values
                        values = list(series.values)
                        data_rows.append(f"| {series.name} | " + " | ".join(str(val) for val in values) + " |")
                except Exception:
                    # Fallback to basic series processing
                    values = list(series.values)
                    data_rows.append(f"| {series.name} | " + " | ".join(str(val) for val in values) + " |")
        else:
            # Standard chart processing
            # Extract categories (x-axis)
            try:
                categories = [cat.label for cat in chart.plots[0].categories if hasattr(cat, "label")]
                if categories:
                    data_rows.append("| Category | " + " | ".join(str(cat) for cat in categories) + " |")
                    data_rows.append("| --- | " + " | ".join(["---"] * len(categories)) + " |")
            except Exception:
                pass

            # Extract series data
            for series in chart.series:
                try:
                    values = list(series.values)
                    data_rows.append(f"| {series.name} | " + " | ".join(str(val) for val in values) + " |")
                except Exception:
                    # Skip series that can't be processed
                    continue

        return "\n".join(data_rows) if data_rows else f"Chart: {getattr(chart, 'chart_title', 'Untitled Chart')}"

    # Log unsupported shape types
    shape_type_name = getattr(shape.shape_type, 'name', 'UNKNOWN') if hasattr(shape, 'shape_type') else 'UNKNOWN'
    logger.debug(f"Unsupported shape type skipped: {shape_type_name}")
    return None


def extract_pptx_metadata(prs: Presentation) -> DocumentMetadata:
    """Extract metadata from PPTX presentation.

    Parameters
    ----------
    prs : Presentation
        python-pptx Presentation object

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Access core properties
    if hasattr(prs, 'core_properties'):
        props = prs.core_properties

        # Extract standard properties
        metadata.title = props.title if hasattr(props, 'title') and props.title else None
        metadata.author = props.author if hasattr(props, 'author') and props.author else None
        metadata.subject = props.subject if hasattr(props, 'subject') and props.subject else None
        metadata.category = props.category if hasattr(props, 'category') and props.category else None
        metadata.language = props.language if hasattr(props, 'language') and props.language else None

        # Handle keywords
        if hasattr(props, 'keywords') and props.keywords:
            if isinstance(props.keywords, str):
                import re
                metadata.keywords = [k.strip() for k in re.split('[,;]', props.keywords) if k.strip()]
            elif isinstance(props.keywords, list):
                metadata.keywords = props.keywords

        # Handle dates
        if hasattr(props, 'created') and props.created:
            metadata.creation_date = props.created
        if hasattr(props, 'modified') and props.modified:
            metadata.modification_date = props.modified

        # Additional PPTX-specific metadata
        if hasattr(props, 'last_modified_by') and props.last_modified_by:
            metadata.custom['last_modified_by'] = props.last_modified_by
        if hasattr(props, 'revision') and props.revision:
            metadata.custom['revision'] = props.revision
        if hasattr(props, 'comments') and props.comments:
            metadata.custom['comments'] = props.comments

        # Add slide count as custom metadata
        try:
            metadata.custom['slide_count'] = len(prs.slides)
        except Exception:
            pass

    return metadata


def pptx_to_markdown(input_data: Union[str, Path, IO[bytes]], options: PptxOptions | None = None) -> str:
    """Convert a PowerPoint presentation to Markdown format.

    Parameters
    ----------
    input_data : str, Path, or IO[bytes]
        The PowerPoint file to convert as a file path or binary file object
    options : PptxOptions | None, default None
        The options for extraction.

    Returns
    -------
    str
        The presentation content in Markdown format
    """
    # Handle backward compatibility and merge options
    if options is None:
        options = PptxOptions()

    # Validate and convert input
    try:
        from pptx.presentation import Presentation as PresentationType

        doc_input, input_type = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like", "pptx.Presentation objects"]
        )

        # Validate ZIP archive security for file-based inputs
        if input_type in ("path", "file") and not isinstance(doc_input, PresentationType):
            try:
                validate_zip_archive(doc_input if input_type == "path" else input_data)
            except Exception as e:
                raise MarkdownConversionError(
                    f"PPTX archive failed security validation: {str(e)}",
                    conversion_stage="archive_validation",
                    original_error=e
                ) from e

        # Open presentation based on input type
        if input_type == "object" and isinstance(doc_input, PresentationType):
            prs = doc_input
        else:
            prs = Presentation(doc_input)

    except Exception as e:
        if "python-pptx" in str(e).lower() or "pptx" in str(e).lower():
            raise MarkdownConversionError(
                "python-pptx library is required for PPTX conversion. Install with: pip install python-pptx",
                conversion_stage="dependency_check",
                original_error=e,
            ) from e
        else:
            raise MarkdownConversionError(
                f"Failed to open PPTX presentation: {str(e)}", conversion_stage="document_opening", original_error=e
            ) from e

    # Extract base filename for standardized attachment naming
    if input_type == "path" and isinstance(doc_input, (str, Path)):
        base_filename = Path(doc_input).stem
    else:
        # For non-file inputs, use a default name
        base_filename = "presentation"

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_pptx_metadata(prs)

    # Get Markdown options (create default if not provided) - currently not used in processing
    # md_options = options.markdown_options or MarkdownOptions()

    markdown_content = []
    img_counter = {}  # Track image sequences across slides

    for i, slide in enumerate(prs.slides, 1):
        slide_content = []

        # Process slide title if present
        if slide.shapes.title:
            title_text = _process_text_frame(slide.shapes.title.text_frame, options.markdown_options)
            if options.slide_numbers:
                slide_content.append(f"# Slide {i}: {title_text.strip()}\n")
            else:
                slide_content.append(f"# {title_text.strip()}\n")

        # Process all shapes in the slide
        for shape in slide.shapes:
            shape_content = _process_shape(shape, options, base_filename, i, img_counter)
            if shape_content:
                slide_content.append(shape_content + "\n")

        # Add slide content with spacing
        if slide_content:
            markdown_content.extend(slide_content)
            markdown_content.append("\n---\n")  # Add separator between slides

    result = "\n".join(markdown_content).strip()

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(result, metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pptx",
    extensions=[".pptx"],
    mime_types=["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.converters.pptx2markdown",
    converter_function="pptx_to_markdown",
    required_packages=[("python-pptx", "")],
    import_error_message="PPTX conversion requires 'python-pptx'. Install with: pip install python-pptx",
    options_class="PptxOptions",
    description="Convert PowerPoint presentations to Markdown",
    priority=7
)


def create_test_presentation() -> Any:
    """Create a test PowerPoint presentation with various elements."""
    prs = Presentation()

    # Title slide
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = title_slide.shapes.title
    subtitle = title_slide.placeholders[1]

    title.text = "Test PowerPoint Presentation"
    subtitle.text = "For Markdown Conversion Testing"

    # Content slide with bullet points
    bullet_slide = prs.slides.add_slide(prs.slide_layouts[1])
    shapes = bullet_slide.shapes

    title = shapes.title
    title.text = "Bullet Points Test"

    body = shapes.placeholders[1]
    tf = body.text_frame

    p = tf.add_paragraph()
    p.text = "First Level Bullet"
    p.level = 0

    p = tf.add_paragraph()
    p.text = "Second Level Bullet"
    p.level = 1

    # Slide with table
    table_slide = prs.slides.add_slide(prs.slide_layouts[1])
    shapes = table_slide.shapes

    title = shapes.title
    title.text = "Table Test"

    rows, cols = 3, 3
    left = top = width = height = Inches(2.0)
    table = shapes.add_table(rows, cols, left, top, width, height).table

    # Add header row
    for i in range(cols):
        cell = table.cell(0, i)
        cell.text = f"Header {i + 1}"

    # Add data rows
    for row in range(1, rows):
        for col in range(cols):
            cell = table.cell(row, col)
            cell.text = f"Cell {row},{col}"

    return prs
