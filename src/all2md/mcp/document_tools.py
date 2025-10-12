"""Document manipulation tool implementation for MCP server.

This module implements the edit_document_ast tool that allows LLMs to
manipulate document structure at the AST level. It supports operations like:
- Listing and extracting sections
- Adding, removing, and replacing sections
- Inserting content into sections
- Generating table of contents
- Splitting documents by sections

Functions
---------
- edit_document_ast_impl: Implementation of edit_document_ast tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import base64
import logging
from pathlib import Path
from typing import Any, cast

from all2md import from_ast, from_markdown, to_ast
from all2md.ast.document_utils import (
    add_section_after,
    add_section_before,
    extract_section,
    generate_toc,
    get_all_sections,
    insert_into_section,
    remove_section,
    replace_section,
    split_by_sections,
)
from all2md.ast.nodes import Document
from all2md.ast.serialization import ast_to_json, json_to_ast
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    EditDocumentInput,
    EditDocumentOutput,
    SectionInfo,
)
from all2md.mcp.security import validate_read_path, validate_write_path

logger = logging.getLogger(__name__)


def _load_source_document(
    input_data: EditDocumentInput,
    config: MCPConfig
) -> Document:
    """Load source document from path or content.

    Parameters
    ----------
    input_data : EditDocumentInput
        Tool input with source specification
    config : MCPConfig
        Server configuration for path validation

    Returns
    -------
    Document
        Loaded AST document

    Raises
    ------
    ValueError
        If source is invalid or mutually exclusive inputs provided
    MCPSecurityError
        If path validation fails
    All2MdError
        If loading fails

    """
    # Validate mutually exclusive inputs
    if input_data.source_path and input_data.source_content:
        raise ValueError("Cannot specify both source_path and source_content")

    if not input_data.source_path and not input_data.source_content:
        raise ValueError("Must specify either source_path or source_content")

    # Prepare source
    if input_data.source_path:
        # Validate read access
        validated_path = validate_read_path(
            input_data.source_path,
            config.read_allowlist
        )
        logger.info(f"Loading document from: {validated_path}")

        # Load based on source_format
        if input_data.source_format == "markdown":
            loaded_doc = to_ast(
                validated_path,
                source_format="markdown",
                flavor=input_data.flavor
            )
            if not isinstance(loaded_doc, Document):
                raise TypeError(f"Expected Document from to_ast, got {type(loaded_doc)}")
            doc = loaded_doc
        elif input_data.source_format == "ast_json":
            # Read JSON file and parse to AST
            json_content = validated_path.read_text(encoding='utf-8')
            loaded_node = json_to_ast(json_content)
            if not isinstance(loaded_node, Document):
                raise TypeError(f"Expected Document from json_to_ast, got {type(loaded_node)}")
            doc = loaded_node
        else:
            raise ValueError(f"Unsupported source_format: {input_data.source_format}")

    else:
        # Handle inline content
        if not input_data.source_content:
            raise ValueError("source_content cannot be empty")

        encoding = input_data.content_encoding or "plain"

        if encoding == "base64":
            # Decode base64 content
            try:
                content_bytes = base64.b64decode(input_data.source_content)
                content_str = content_bytes.decode('utf-8')
            except Exception as e:
                raise ValueError(f"Invalid base64 encoding or UTF-8 content: {e}") from e
        else:
            # Plain text content
            content_str = input_data.source_content

        # Parse based on source_format
        if input_data.source_format == "markdown":
            # Use to_ast for markdown content (from_markdown with target_format="ast" returns JSON string)
            loaded_doc = to_ast(
                content_str,
                source_format="markdown",
                flavor=input_data.flavor
            )
            if not isinstance(loaded_doc, Document):
                raise TypeError(f"Expected Document from to_ast, got {type(loaded_doc)}")
            doc = loaded_doc
        elif input_data.source_format == "ast_json":
            loaded_node = json_to_ast(content_str)
            if not isinstance(loaded_node, Document):
                raise TypeError(f"Expected Document from json_to_ast, got {type(loaded_node)}")
            doc = loaded_node
        else:
            raise ValueError(f"Unsupported source_format: {input_data.source_format}")

    return doc


def _serialize_document(
    doc: Document,
    output_format: str,
    flavor: str | None
) -> str:
    """Serialize document to string format.

    Parameters
    ----------
    doc : Document
        AST document to serialize
    output_format : str
        Output format ("markdown" or "ast_json")
    flavor : str | None
        Markdown flavor for markdown output

    Returns
    -------
    str
        Serialized document

    """
    if output_format == "markdown":
        result = from_ast(
            doc,
            target_format="markdown",
            flavor=flavor
        )
        if not isinstance(result, str):
            raise TypeError(f"Expected string, got {type(result)}")
        return result
    elif output_format == "ast_json":
        return ast_to_json(doc)
    else:
        raise ValueError(f"Unsupported output_format: {output_format}")


def _write_output(
    content: str,
    output_path: str,
    config: MCPConfig
) -> Path:
    """Write output content to file.

    Parameters
    ----------
    content : str
        Content to write
    output_path : str
        Destination path
    config : MCPConfig
        Server configuration for path validation

    Returns
    -------
    Path
        Validated output path where content was written

    Raises
    ------
    MCPSecurityError
        If path validation fails

    """
    validated_path = validate_write_path(output_path, config.write_allowlist)
    validated_path.write_text(content, encoding='utf-8')
    logger.info(f"Wrote output to: {validated_path}")
    return validated_path


def edit_document_ast_impl(
    input_data: EditDocumentInput,
    config: MCPConfig
) -> EditDocumentOutput:
    """Implement edit_document_ast tool.

    Parameters
    ----------
    input_data : EditDocumentInput
        Tool input parameters
    config : MCPConfig
        Server configuration (for allowlists, etc.)

    Returns
    -------
    EditDocumentOutput
        Operation result with modified content or section info

    Raises
    ------
    MCPSecurityError
        If security validation fails
    All2MdError
        If document manipulation fails
    ValueError
        If operation parameters are invalid

    """
    warnings: list[str] = []
    sections_modified = 0

    try:
        # Load source document
        doc = _load_source_document(input_data, config)
        logger.info(f"Loaded document with {len(doc.children)} nodes")

        # Route operation
        operation = input_data.operation
        logger.info(f"Executing operation: {operation}")

        if operation == "list_sections":
            # List all sections with metadata
            sections = get_all_sections(doc)
            section_infos = [
                SectionInfo(
                    index=idx,
                    heading_text=section.get_heading_text(),
                    level=section.level,
                    content_nodes=len(section.content),
                    start_index=section.start_index,
                    end_index=section.end_index
                )
                for idx, section in enumerate(sections)
            ]

            return EditDocumentOutput(
                sections=section_infos,
                section_count=len(sections),
                warnings=warnings
            )

        elif operation == "get_section":
            # Extract a specific section
            target = _resolve_target(input_data)
            section_doc = extract_section(
                doc,
                target,
                case_sensitive=input_data.case_sensitive
            )
            sections_modified = 1

            # Serialize and optionally write
            content = _serialize_document(
                section_doc,
                input_data.output_format,
                input_data.flavor
            )

            if input_data.output_path:
                output_path_obj = _write_output(content, input_data.output_path, config)
                return EditDocumentOutput(
                    output_path=str(output_path_obj),
                    sections_modified=sections_modified,
                    warnings=warnings
                )
            else:
                return EditDocumentOutput(
                    content=content,
                    sections_modified=sections_modified,
                    warnings=warnings
                )

        elif operation == "add_section":
            # Add a new section before or after target
            target = _resolve_target(input_data)
            position = input_data.position or "after"

            if not input_data.content:
                raise ValueError("content is required for add_section operation")

            # Parse content as markdown to create new section
            new_doc = to_ast(
                input_data.content,
                source_format="markdown",
                flavor=input_data.flavor
            )
            if not isinstance(new_doc, Document):
                raise TypeError(f"Expected Document, got {type(new_doc)}")

            # Add section
            if position == "before":
                modified_doc = add_section_before(
                    doc,
                    target,
                    new_doc,
                    case_sensitive=input_data.case_sensitive
                )
            elif position == "after":
                modified_doc = add_section_after(
                    doc,
                    target,
                    new_doc,
                    case_sensitive=input_data.case_sensitive
                )
            else:
                raise ValueError(f"Invalid position for add_section: {position}")

            sections_modified = 1

        elif operation == "remove_section":
            # Remove a section
            target = _resolve_target(input_data)
            modified_doc = remove_section(
                doc,
                target,
                case_sensitive=input_data.case_sensitive
            )
            sections_modified = 1

        elif operation == "replace_section":
            # Replace a section with new content
            target = _resolve_target(input_data)

            if not input_data.content:
                raise ValueError("content is required for replace_section operation")

            # Parse content as markdown
            new_doc = to_ast(
                input_data.content,
                source_format="markdown",
                flavor=input_data.flavor
            )
            if not isinstance(new_doc, Document):
                raise TypeError(f"Expected Document, got {type(new_doc)}")

            modified_doc = replace_section(
                doc,
                target,
                new_doc,
                case_sensitive=input_data.case_sensitive
            )
            sections_modified = 1

        elif operation == "insert_content":
            # Insert content into a section
            target = _resolve_target(input_data)
            position = input_data.position or "end"

            if not input_data.content:
                raise ValueError("content is required for insert_content operation")

            # Parse content as markdown
            content_doc = to_ast(
                input_data.content,
                source_format="markdown",
                flavor=input_data.flavor
            )
            if not isinstance(content_doc, Document):
                raise TypeError(f"Expected Document, got {type(content_doc)}")

            # Validate position for insert_into_section
            if position not in ("start", "end", "after_heading"):
                raise ValueError(
                    f"Invalid position for insert_content: {position}. "
                    "Must be 'start', 'end', or 'after_heading'."
                )

            modified_doc = insert_into_section(
                doc,
                target,
                content_doc.children,
                position=cast(Any, position),
                case_sensitive=input_data.case_sensitive
            )
            sections_modified = 1

        elif operation == "generate_toc":
            # Generate table of contents
            toc_str = generate_toc(
                doc,
                max_level=input_data.max_toc_level,
                style=input_data.toc_style
            )

            # For non-markdown styles, convert List node to markdown
            if not isinstance(toc_str, str):
                # It's a List node, render to markdown
                from all2md.ast.nodes import Document as ASTDocument
                toc_doc = ASTDocument(children=[toc_str])
                toc_str = _serialize_document(
                    toc_doc,
                    "markdown",
                    input_data.flavor
                )

            # Return TOC content directly (not full document)
            if input_data.output_path:
                output_path_obj = _write_output(toc_str, input_data.output_path, config)
                return EditDocumentOutput(
                    output_path=str(output_path_obj),
                    warnings=warnings
                )
            else:
                return EditDocumentOutput(
                    content=toc_str,
                    warnings=warnings
                )

        elif operation == "split_document":
            # Split document by sections
            section_docs = split_by_sections(doc, include_preamble=True)

            # Serialize each section
            split_contents = []
            for section_doc in section_docs:
                section_content = _serialize_document(
                    section_doc,
                    input_data.output_format,
                    input_data.flavor
                )
                split_contents.append(section_content)

            sections_modified = len(section_docs)

            # For split_document, we return all sections as a single string
            # separated by markdown thematic breaks
            combined_content = "\n\n---\n\n".join(split_contents)

            if input_data.output_path:
                # Write combined output
                output_path_obj = _write_output(
                    combined_content,
                    input_data.output_path,
                    config
                )
                return EditDocumentOutput(
                    output_path=str(output_path_obj),
                    sections_modified=sections_modified,
                    warnings=warnings
                )
            else:
                return EditDocumentOutput(
                    content=combined_content,
                    sections_modified=sections_modified,
                    warnings=warnings
                )

        else:
            raise ValueError(f"Unknown operation: {operation}")

        # For operations that modify the document, serialize and return
        if operation in ("add_section", "remove_section", "replace_section", "insert_content"):
            content = _serialize_document(
                modified_doc,
                input_data.output_format,
                input_data.flavor
            )

            if input_data.output_path:
                output_path_obj = _write_output(content, input_data.output_path, config)
                return EditDocumentOutput(
                    output_path=str(output_path_obj),
                    sections_modified=sections_modified,
                    warnings=warnings
                )
            else:
                return EditDocumentOutput(
                    content=content,
                    sections_modified=sections_modified,
                    warnings=warnings
                )

        # Should not reach here
        raise ValueError(f"Operation {operation} did not return a result")

    except (All2MdError, ValueError) as e:
        # Let All2MdError and ValueError pass through without wrapping
        logger.error(f"Document operation failed: {e}")
        raise
    except MCPSecurityError as e:
        # Let security errors pass through
        logger.error(f"Security violation: {e}")
        raise
    except Exception as e:
        # Only wrap truly unexpected exceptions
        logger.error(f"Unexpected error during document operation: {e}")
        raise All2MdError(f"Document operation failed: {e}") from e


def _resolve_target(input_data: EditDocumentInput) -> str | int:
    """Resolve target from input data.

    Parameters
    ----------
    input_data : EditDocumentInput
        Input with target_heading or target_index

    Returns
    -------
    str or int
        Resolved target

    Raises
    ------
    ValueError
        If no target is specified or both are specified

    """
    if input_data.target_heading and input_data.target_index is not None:
        raise ValueError("Cannot specify both target_heading and target_index")

    if input_data.target_heading:
        return input_data.target_heading
    elif input_data.target_index is not None:
        return input_data.target_index
    else:
        raise ValueError("Must specify either target_heading or target_index")


__all__ = [
    "edit_document_ast_impl",
]
