"""Document manipulation tool implementation for MCP server.

This module implements the edit_document tool that allows LLMs to
manipulate document structure at the AST level with a simplified interface.

Functions
---------
- edit_document_impl: Implementation of edit_document tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging

from all2md import from_ast, to_ast
from all2md.ast.document_utils import (
    add_section_after,
    add_section_before,
    extract_section,
    get_all_sections,
    insert_into_section,
    remove_section,
    replace_section,
)
from all2md.ast.nodes import Document
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    EditDocumentSimpleInput,
    EditDocumentSimpleOutput,
)
from all2md.mcp.security import MCPSecurityError, validate_read_path

logger = logging.getLogger(__name__)


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
        doc = to_ast(validated_path, source_format="markdown", flavor="gfm")
        if not isinstance(doc, Document):
            raise TypeError(f"Expected Document from to_ast, got {type(doc)}")

        logger.info(f"Executing action: {input_data.action}")

        # Execute action
        if input_data.action == "list-sections":
            # List all sections with metadata
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

        elif input_data.action == "extract":
            # Extract a specific section
            assert target is not None  # Already validated above
            section_doc = extract_section(doc, target, case_sensitive=False)

            # Serialize to markdown
            result_md = from_ast(section_doc, target_format="markdown", flavor="gfm")
            if not isinstance(result_md, str):
                raise TypeError(f"Expected str from from_ast, got {type(result_md)}")

            target_desc = f"section #{target}" if isinstance(target, int) else f"section '{target}'"
            return EditDocumentSimpleOutput(
                success=True, message=f"Successfully extracted {target_desc}.", content=result_md
            )

        elif input_data.action in ("add:before", "add:after"):
            # Add a new section before or after target
            assert target is not None  # Already validated above
            assert input_data.content is not None  # Already validated above

            # Parse content as markdown to create new section
            new_doc = to_ast(input_data.content, source_format="markdown", flavor="gfm")
            if not isinstance(new_doc, Document):
                raise TypeError(f"Expected Document, got {type(new_doc)}")

            # Add section
            if input_data.action == "add:before":
                modified_doc = add_section_before(doc, target, new_doc, case_sensitive=False)
                position_desc = "before"
            else:
                modified_doc = add_section_after(doc, target, new_doc, case_sensitive=False)
                position_desc = "after"

            # Serialize to markdown
            result_md = from_ast(modified_doc, target_format="markdown", flavor="gfm")
            if not isinstance(result_md, str):
                raise TypeError(f"Expected str from from_ast, got {type(result_md)}")

            target_desc = f"section #{target}" if isinstance(target, int) else f"section '{target}'"
            return EditDocumentSimpleOutput(
                success=True, message=f"Successfully added content {position_desc} {target_desc}.", content=result_md
            )

        elif input_data.action == "remove":
            # Remove a section
            assert target is not None  # Already validated above
            modified_doc = remove_section(doc, target, case_sensitive=False)

            # Serialize to markdown
            result_md = from_ast(modified_doc, target_format="markdown", flavor="gfm")
            if not isinstance(result_md, str):
                raise TypeError(f"Expected str from from_ast, got {type(result_md)}")

            target_desc = f"section #{target}" if isinstance(target, int) else f"section '{target}'"
            return EditDocumentSimpleOutput(
                success=True, message=f"Successfully removed {target_desc}.", content=result_md
            )

        elif input_data.action == "replace":
            # Replace a section with new content
            assert target is not None  # Already validated above
            assert input_data.content is not None  # Already validated above

            # Parse content as markdown
            new_doc = to_ast(input_data.content, source_format="markdown", flavor="gfm")
            if not isinstance(new_doc, Document):
                raise TypeError(f"Expected Document, got {type(new_doc)}")

            modified_doc = replace_section(doc, target, new_doc, case_sensitive=False)

            # Serialize to markdown
            result_md = from_ast(modified_doc, target_format="markdown", flavor="gfm")
            if not isinstance(result_md, str):
                raise TypeError(f"Expected str from from_ast, got {type(result_md)}")

            target_desc = f"section #{target}" if isinstance(target, int) else f"section '{target}'"
            return EditDocumentSimpleOutput(
                success=True, message=f"Successfully replaced {target_desc}.", content=result_md
            )

        elif input_data.action in ("insert:start", "insert:end", "insert:after_heading"):
            # Insert content into a section
            assert target is not None  # Already validated above
            assert input_data.content is not None  # Already validated above

            # Parse content as markdown
            content_doc = to_ast(input_data.content, source_format="markdown", flavor="gfm")
            if not isinstance(content_doc, Document):
                raise TypeError(f"Expected Document, got {type(content_doc)}")

            # Map action to position
            position_map = {"insert:start": "start", "insert:end": "end", "insert:after_heading": "after_heading"}
            position = position_map[input_data.action]

            modified_doc = insert_into_section(
                doc, target, content_doc.children, position=position, case_sensitive=False  # type: ignore[arg-type]
            )

            # Serialize to markdown
            result_md = from_ast(modified_doc, target_format="markdown", flavor="gfm")
            if not isinstance(result_md, str):
                raise TypeError(f"Expected str from from_ast, got {type(result_md)}")

            target_desc = f"section #{target}" if isinstance(target, int) else f"section '{target}'"
            return EditDocumentSimpleOutput(
                success=True, message=f"Successfully inserted content into {target_desc}.", content=result_md
            )

        else:
            # Should never reach here due to validation above
            return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Unhandled action: {input_data.action}")

    except ValueError as e:
        # Handle validation errors from AST functions
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Target not found: {error_msg}")
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Invalid input: {error_msg}")

    except All2MdError as e:
        # Handle document processing errors
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Document processing failed: {e}")

    except MCPSecurityError as e:
        # Handle security violations
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Security violation: {e}")

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in edit_document: {e}", exc_info=True)
        return EditDocumentSimpleOutput(success=False, message=f"[ERROR] Unexpected error: {e}")


__all__ = [
    "edit_document_impl",
]
