"""Document manipulation tool implementation for MCP server.

This module implements the edit_document tool that allows LLMs to
manipulate document structure at the AST level with a simplified interface.

Functions
---------
- edit_document_impl: Implementation of edit_document tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging
from typing import Literal

from all2md.api import from_ast, to_ast
from all2md.ast.nodes import Document
from all2md.ast.sections import extract_sections, get_all_sections
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    EditDocumentSimpleInput,
    EditDocumentSimpleOutput,
)
from all2md.mcp.security import MCPSecurityError, validate_read_path

logger = logging.getLogger(__name__)


def _parse_markdown_content(content: str, config: MCPConfig) -> Document:
    """Parse markdown content string to Document AST.

    Parameters
    ----------
    content : str
        Markdown content to parse
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    Document
        Parsed document AST

    Raises
    ------
    TypeError
        If parsing doesn't return a Document

    """
    doc = to_ast(content, source_format="markdown", flavor=config.flavor)
    if not isinstance(doc, Document):
        raise TypeError(f"Expected Document, got {type(doc)}")
    return doc


def _serialize_to_markdown(doc: Document, config: MCPConfig) -> str:
    """Serialize Document AST to markdown string.

    Parameters
    ----------
    doc : Document
        Document AST to serialize
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    str
        Markdown string

    Raises
    ------
    TypeError
        If serialization doesn't return a string

    """
    result = from_ast(doc, target_format="markdown", flavor=config.flavor)
    if not isinstance(result, str):
        raise TypeError(f"Expected str from from_ast, got {type(result)}")
    return result


def _format_target_description(target: str | int) -> str:
    """Format target for user-facing messages.

    Parameters
    ----------
    target : str or int
        Target section (heading text or index)

    Returns
    -------
    str
        Formatted target description

    """
    return f"section #{target}" if isinstance(target, int) else f"section '{target}'"


def _handle_list_sections(doc: Document) -> EditDocumentSimpleOutput:
    """Handle list-sections action.

    Parameters
    ----------
    doc : Document
        Document to list sections from

    Returns
    -------
    EditDocumentSimpleOutput
        Result with section listing

    """
    sections = get_all_sections(doc)
    if sections:
        lines = ["Document Sections:"]
        for idx, section in enumerate(sections):
            indent = "  " * (section.level - 1)
            lines.append(
                f"{indent}[#{idx}] "
                f"{'#' * section.level} {section.get_heading_text()} "
                f"({len(section.content)} nodes)"
            )
        content = "\n".join(lines)
    else:
        content = "No sections found in document."

    return EditDocumentSimpleOutput(success=True, message=f"Found {len(sections)} section(s).", content=content)


def _handle_extract(doc: Document, target: str | int, config: MCPConfig) -> EditDocumentSimpleOutput:
    """Handle extract action.

    Parameters
    ----------
    doc : Document
        Source document
    target : str or int
        Target section to extract
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    EditDocumentSimpleOutput
        Result with extracted section

    """
    section_doc = extract_sections(doc, target, case_sensitive=False, combine=False)
    result_md = _serialize_to_markdown(section_doc, config)
    target_desc = _format_target_description(target)
    return EditDocumentSimpleOutput(success=True, message=f"Successfully extracted {target_desc}.", content=result_md)


def _handle_add(
    doc: Document, target: str | int, content: str, action: str, config: MCPConfig
) -> EditDocumentSimpleOutput:
    """Handle add:before and add:after actions.

    Parameters
    ----------
    doc : Document
        Source document
    target : str or int
        Target section
    content : str
        Content to add
    action : str
        Either "add:before" or "add:after"
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    EditDocumentSimpleOutput
        Result with modified document

    """
    new_doc = _parse_markdown_content(content, config)

    if action == "add:before":
        modified_doc = doc.add_section_before(target, new_doc, case_sensitive=False)
        position_desc = "before"
    else:
        modified_doc = doc.add_section_after(target, new_doc, case_sensitive=False)
        position_desc = "after"

    result_md = _serialize_to_markdown(modified_doc, config)
    target_desc = _format_target_description(target)
    return EditDocumentSimpleOutput(
        success=True, message=f"Successfully added content {position_desc} {target_desc}.", content=result_md
    )


def _handle_remove(doc: Document, target: str | int, config: MCPConfig) -> EditDocumentSimpleOutput:
    """Handle remove action.

    Parameters
    ----------
    doc : Document
        Source document
    target : str or int
        Target section to remove
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    EditDocumentSimpleOutput
        Result with modified document

    """
    modified_doc = doc.remove_section(target, case_sensitive=False)
    result_md = _serialize_to_markdown(modified_doc, config)
    target_desc = _format_target_description(target)
    return EditDocumentSimpleOutput(success=True, message=f"Successfully removed {target_desc}.", content=result_md)


def _handle_replace(doc: Document, target: str | int, content: str, config: MCPConfig) -> EditDocumentSimpleOutput:
    """Handle replace action.

    Parameters
    ----------
    doc : Document
        Source document
    target : str or int
        Target section to replace
    content : str
        Replacement content
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    EditDocumentSimpleOutput
        Result with modified document

    """
    new_doc = _parse_markdown_content(content, config)
    modified_doc = doc.replace_section(target, new_doc, case_sensitive=False)
    result_md = _serialize_to_markdown(modified_doc, config)
    target_desc = _format_target_description(target)
    return EditDocumentSimpleOutput(success=True, message=f"Successfully replaced {target_desc}.", content=result_md)


def _handle_insert(
    doc: Document, target: str | int, content: str, action: str, config: MCPConfig
) -> EditDocumentSimpleOutput:
    """Handle insert:start, insert:end, and insert:after_heading actions.

    Parameters
    ----------
    doc : Document
        Source document
    target : str or int
        Target section
    content : str
        Content to insert
    action : str
        One of "insert:start", "insert:end", or "insert:after_heading"
    config : MCPConfig
        Server configuration (for flavor)

    Returns
    -------
    EditDocumentSimpleOutput
        Result with modified document

    """
    content_doc = _parse_markdown_content(content, config)

    position_map: dict[str, Literal["start", "end", "after_heading"]] = {
        "insert:start": "start",
        "insert:end": "end",
        "insert:after_heading": "after_heading",
    }
    position = position_map[action]

    modified_doc = doc.insert_into_section(
        target,
        content_doc.children,
        position=position,
        case_sensitive=False,
    )

    result_md = _serialize_to_markdown(modified_doc, config)
    target_desc = _format_target_description(target)
    return EditDocumentSimpleOutput(
        success=True, message=f"Successfully inserted content into {target_desc}.", content=result_md
    )


def edit_document_impl(input_data: EditDocumentSimpleInput, config: MCPConfig) -> EditDocumentSimpleOutput:
    """Implement edit_document tool (simplified LLM-friendly interface).

    This function provides a streamlined interface for document manipulation
    with sensible defaults for LLM usage. All errors are caught and returned
    as error messages (no exceptions thrown).

    Parameters
    ----------
    input_data : EditDocumentSimpleInput
        Simplified tool input parameters
    config : MCPConfig
        Server configuration (for allowlists, etc.)

    Returns
    -------
    EditDocumentSimpleOutput
        Operation result with success flag, message, and optional content

    """
    try:
        # Validate action
        valid_actions = {
            "list-sections",
            "extract",
            "add:before",
            "add:after",
            "remove",
            "replace",
            "insert:start",
            "insert:end",
            "insert:after_heading",
        }
        if input_data.action not in valid_actions:
            return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Invalid action: {input_data.action!r}")

        # Parse target (heading text or index notation like "#3")
        target: str | int | None = None
        if input_data.target is not None:
            target_str = input_data.target.strip()
            # Check if it's index notation (e.g., "#3")
            if target_str.startswith("#"):
                try:
                    target = int(target_str[1:])
                except ValueError:
                    return EditDocumentSimpleOutput(
                        success=False,
                        message=f"[ERROR] Invalid target index format: {input_data.target!r}. "
                        "Expected format like '#0', '#1', '#2'.",
                    )
            else:
                target = target_str

        # Validate target is provided when needed
        if input_data.action != "list-sections" and target is None:
            return EditDocumentSimpleOutput(
                success=False,
                message=f"[ERROR] The '{input_data.action}' action requires a target "
                "(heading text or index like '#0').",
            )

        # Validate content is provided when needed
        content_required_actions = {
            "add:before",
            "add:after",
            "replace",
            "insert:start",
            "insert:end",
            "insert:after_heading",
        }
        if input_data.action in content_required_actions and not input_data.content:
            return EditDocumentSimpleOutput(
                success=False, message=f"[ERROR] The '{input_data.action}' action requires content parameter."
            )

        # Validate and load document
        try:
            validated_path = validate_read_path(input_data.doc, config.read_allowlist)
        except MCPSecurityError as e:
            return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Read access denied: {e}")

        logger.info(f"Loading document from: {validated_path}")
        doc = to_ast(validated_path, source_format="markdown", flavor=config.flavor)
        if not isinstance(doc, Document):
            raise TypeError(f"Expected Document from to_ast, got {type(doc)}")

        logger.info(f"Executing action: {input_data.action}")

        # Execute action using dispatch pattern
        if input_data.action == "list-sections":
            return _handle_list_sections(doc)
        elif input_data.action == "extract":
            assert target is not None  # Already validated above
            return _handle_extract(doc, target, config)
        elif input_data.action in ("add:before", "add:after"):
            assert target is not None  # Already validated above
            assert input_data.content is not None  # Already validated above
            return _handle_add(doc, target, input_data.content, input_data.action, config)
        elif input_data.action == "remove":
            assert target is not None  # Already validated above
            return _handle_remove(doc, target, config)
        elif input_data.action == "replace":
            assert target is not None  # Already validated above
            assert input_data.content is not None  # Already validated above
            return _handle_replace(doc, target, input_data.content, config)
        elif input_data.action in ("insert:start", "insert:end", "insert:after_heading"):
            assert target is not None  # Already validated above
            assert input_data.content is not None  # Already validated above
            return _handle_insert(doc, target, input_data.content, input_data.action, config)
        else:
            # Should never reach here due to validation above
            return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Unhandled action: {input_data.action}")

    except ValueError as e:
        # Handle validation errors from AST functions
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Target not found: {error_msg}")
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Invalid input: {error_msg}")

    except MCPSecurityError as e:
        # Handle security violations
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Security violation: {e}")

    except All2MdError as e:
        # Handle document processing errors
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Document processing failed: {e}")

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in edit_document: {e}", exc_info=True)
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Unexpected error: {e}")


__all__ = [
    "edit_document_impl",
]
