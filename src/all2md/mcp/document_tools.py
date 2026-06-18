"""Document manipulation tool implementation for MCP server.

This module implements the edit_document tool that applies a batch of edits to
a document at the AST level and writes the result back to disk in place.

Functions
---------
- edit_document_impl: Implementation of edit_document tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging
from typing import Any

from all2md.api import from_ast, to_ast
from all2md.ast.nodes import Document
from all2md.ast.sections import extract_sections, get_all_sections
from all2md.constants import DocumentFormat
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    EditDocumentInput,
    EditDocumentOutput,
    EditOperation,
    EditResultItem,
)
from all2md.mcp.security import (
    MCPSecurityError,
    resolve_workspace_path,
    secure_open_for_write,
    validate_read_path,
    validate_write_path,
)

logger = logging.getLogger(__name__)

# Actions that change the document (and therefore trigger a write-back).
_MUTATING_ACTIONS = {
    "add:before",
    "add:after",
    "remove",
    "replace",
    "insert:start",
    "insert:end",
    "insert:after_heading",
}

_CONTENT_REQUIRED_ACTIONS = {
    "add:before",
    "add:after",
    "replace",
    "insert:start",
    "insert:end",
    "insert:after_heading",
}

# Map a source file extension to the renderable target format used for in-place
# write-back. PDF is intentionally excluded: re-rendering reflows the entire
# document, which is too destructive for an in-place edit. Extensions absent
# here cannot be persisted in place; the agent is told to export instead.
_WRITABLE_FORMAT_BY_EXT: dict[str, DocumentFormat] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".mkd": "markdown",
    ".txt": "markdown",
    ".html": "html",
    ".htm": "html",
    ".docx": "docx",
    ".pptx": "pptx",
    ".rst": "rst",
    ".epub": "epub",
}

# Formats rendered as bytes (vs. text) by from_ast.
_BINARY_FORMATS = {"docx", "pptx", "epub", "pdf"}


def _parse_markdown_content(content: str, config: MCPConfig) -> Document:
    """Parse markdown content string to a Document AST."""
    doc = to_ast(content, source_format="markdown", flavor=config.flavor)
    if not isinstance(doc, Document):
        raise TypeError(f"Expected Document, got {type(doc)}")
    return doc


def _serialize_to_markdown(doc: Document, config: MCPConfig) -> str:
    """Serialize a Document AST to a markdown string."""
    result = from_ast(doc, target_format="markdown", flavor=config.flavor)
    if not isinstance(result, str):
        raise TypeError(f"Expected str from from_ast, got {type(result)}")
    return result


def _format_target_description(target: str | int) -> str:
    """Format a target for user-facing messages."""
    return f"section #{target}" if isinstance(target, int) else f"section '{target}'"


def _list_sections_text(doc: Document) -> str:
    """Render a human-readable listing of a document's sections."""
    sections = get_all_sections(doc)
    if not sections:
        return "No sections found in document."
    lines = ["Document Sections:"]
    for idx, section in enumerate(sections):
        indent = "  " * (section.level - 1)
        lines.append(
            f"{indent}[#{idx}] {'#' * section.level} {section.get_heading_text()} ({len(section.content)} nodes)"
        )
    return "\n".join(lines)


def _parse_target(raw: str | None) -> str | int | None:
    """Parse a target into heading text or a zero-based index (``#N``)."""
    if raw is None:
        return None
    s = raw.strip()
    if s.startswith("#"):
        try:
            return int(s[1:])
        except ValueError as e:
            raise ValueError(f"Invalid target index format: {raw!r}. Expected '#0', '#1', '#2', etc.") from e
    return s


def _validate_op(op: EditOperation) -> tuple[str, str | int | None, str | None]:
    """Validate a single edit operation, returning (action, target, content)."""
    valid_actions = {"list-sections", "extract", *_MUTATING_ACTIONS}
    if op.action not in valid_actions:
        raise ValueError(f"Invalid action: {op.action!r}")

    target = _parse_target(op.target)
    if op.action != "list-sections" and target is None:
        raise ValueError(f"The {op.action!r} action requires a target (heading text or index like '#0').")

    if op.action in _CONTENT_REQUIRED_ACTIONS and not op.content:
        raise ValueError(f"The {op.action!r} action requires a content parameter.")

    return op.action, target, op.content


def _safe_region(doc: Document, target: str | int, config: MCPConfig) -> str | None:
    """Return the markdown for ``target`` after an edit, or None if unavailable."""
    try:
        section_doc = extract_sections(doc, target, case_sensitive=False, combine=False)
        return _serialize_to_markdown(section_doc, config)
    except Exception:  # noqa: BLE001 - region is best-effort, never fatal
        return None


def _apply_edit(doc: Document, op: EditOperation, config: MCPConfig) -> tuple[Document, str | None, str]:
    """Apply a single edit, returning (modified_doc, edited_region, message).

    Read-only actions return ``doc`` unchanged. Raises on any failure so the
    caller can abort the batch atomically.
    """
    action, target, content = _validate_op(op)

    if action == "list-sections":
        return doc, _list_sections_text(doc), f"Listed {len(get_all_sections(doc))} section(s)."

    if action == "extract":
        assert target is not None
        region = _serialize_to_markdown(extract_sections(doc, target, case_sensitive=False, combine=False), config)
        return doc, region, f"Extracted {_format_target_description(target)}."

    assert target is not None

    if action in ("add:before", "add:after"):
        assert content is not None
        new_doc = _parse_markdown_content(content, config)
        if action == "add:before":
            modified = doc.add_section_before(target, new_doc, case_sensitive=False)
            where = "before"
        else:
            modified = doc.add_section_after(target, new_doc, case_sensitive=False)
            where = "after"
        return modified, content.strip(), f"Added section {where} {_format_target_description(target)}."

    if action == "remove":
        modified = doc.remove_section(target, case_sensitive=False)
        return modified, None, f"Removed {_format_target_description(target)}."

    if action == "replace":
        assert content is not None
        new_doc = _parse_markdown_content(content, config)
        modified = doc.replace_section(target, new_doc, case_sensitive=False)
        return modified, _safe_region(modified, target, config), f"Replaced {_format_target_description(target)}."

    # insert:start / insert:end / insert:after_heading
    assert content is not None
    content_doc = _parse_markdown_content(content, config)
    position_map = {"insert:start": "start", "insert:end": "end", "insert:after_heading": "after_heading"}
    modified = doc.insert_into_section(
        target,
        content_doc.children,
        position=position_map[action],  # type: ignore[arg-type]
        case_sensitive=False,
    )
    edited = _safe_region(modified, target, config)
    return modified, edited, f"Inserted content into {_format_target_description(target)}."


def _format_error(e: Exception) -> str:
    """Build a clear, LLM-friendly error message for a failed edit."""
    msg = str(e)
    if isinstance(e, ValueError) and "not found" in msg.lower():
        return f"Target not found: {msg}"
    if isinstance(e, MCPSecurityError):
        return f"Security violation: {msg}"
    return msg


def _normalize_edits(raw_edits: Any) -> list[EditOperation] | None:
    """Coerce incoming edits (EditOperation or dict) into EditOperation list.

    Returns None if any item has an unrecognized shape.
    """
    normalized: list[EditOperation] = []
    for item in raw_edits or []:
        if isinstance(item, EditOperation):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(
                EditOperation(
                    action=item.get("action"),  # type: ignore[arg-type]
                    target=item.get("target"),
                    content=item.get("content"),
                )
            )
        else:
            return None
    return normalized


def edit_document_impl(input_data: EditDocumentInput, config: MCPConfig) -> EditDocumentOutput:
    """Implement the edit_document tool (batch, atomic, in-place).

    Applies the batch of edits to a single parse of the document. The batch is
    atomic: if any edit fails, none are persisted. When the batch contains a
    mutating action, the modified document is written back to disk in its
    original format (the file must be within the write allowlist). Mutating
    results echo only the edited region, not the whole document.

    Parameters
    ----------
    input_data : EditDocumentInput
        Tool input (document path and ordered edits).
    config : MCPConfig
        Server configuration (allowlists, flavor).

    Returns
    -------
    EditDocumentOutput
        Per-edit results, write confirmation, and any warnings.

    """
    edits = _normalize_edits(input_data.edits)
    if edits is None:
        return EditDocumentOutput(success=False, warnings=["One or more edits had an unrecognized shape."])
    if not edits:
        return EditDocumentOutput(success=False, warnings=["No edits provided."])

    # Resolve (workspace-relative allowed) and validate read access.
    resolved = resolve_workspace_path(input_data.doc, config.read_allowlist, must_exist=True)
    if resolved is None:
        searched = ", ".join(str(d) for d in (config.read_allowlist or [])) or "(no read folders configured)"
        return EditDocumentOutput(
            success=False,
            warnings=[f"File not found: {input_data.doc!r}. Looked relative to the workspace folder(s): {searched}."],
        )
    try:
        read_path = validate_read_path(resolved, config.read_allowlist)
    except MCPSecurityError as e:
        return EditDocumentOutput(success=False, warnings=[f"Read access denied: {e}"])

    mutating = any(op.action in _MUTATING_ACTIONS for op in edits)

    # For mutating batches, confirm we can persist this file before doing work.
    write_path = None
    out_format: DocumentFormat | None = None
    if mutating:
        try:
            write_path = validate_write_path(read_path, config.write_allowlist)
        except MCPSecurityError as e:
            return EditDocumentOutput(
                success=False,
                warnings=[f"Cannot edit in place: {e}. The file may be in a read-only folder."],
            )
        ext = read_path.suffix.lower()
        out_format = _WRITABLE_FORMAT_BY_EXT.get(ext)
        if out_format is None:
            return EditDocumentOutput(
                success=False,
                warnings=[
                    f"edit_document cannot write changes back to '{ext or read_path.name}' files in place. "
                    "Supported in-place formats: .md, .html, .docx, .pptx, .rst, .epub. "
                    "Use save_document_from_markdown to export to another format instead."
                ],
            )

    # Parse the document once (format auto-detected from the file).
    try:
        doc = to_ast(read_path, source_format="auto", flavor=config.flavor)
        if not isinstance(doc, Document):
            raise TypeError(f"Expected Document from to_ast, got {type(doc)}")
    except All2MdError as e:
        return EditDocumentOutput(success=False, warnings=[f"Could not read document: {e}"])

    source_path_attr = getattr(doc, "source_path", None)

    # Apply edits in order to an in-memory copy; persist only if all succeed.
    results: list[EditResultItem] = []
    current = doc
    failed_index: int | None = None
    for i, op in enumerate(edits):
        try:
            current, region, message = _apply_edit(current, op, config)
            results.append(
                EditResultItem(
                    index=i, action=op.action, target=op.target, success=True, message=message, edited_region=region
                )
            )
        except (ValueError, MCPSecurityError, All2MdError, TypeError) as e:
            results.append(
                EditResultItem(index=i, action=op.action, target=op.target, success=False, message=_format_error(e))
            )
            failed_index = i
            break

    if failed_index is not None:
        for j in range(failed_index + 1, len(edits)):
            op = edits[j]
            results.append(
                EditResultItem(
                    index=j,
                    action=op.action,
                    target=op.target,
                    success=False,
                    message="Not applied (atomic batch aborted).",
                )
            )
        return EditDocumentOutput(
            success=False,
            disk_written=False,
            results=results,
            warnings=[f"Batch aborted at edit #{failed_index}; no changes were written."],
        )

    # All edits succeeded. Persist if the batch changed anything.
    warnings: list[str] = []
    disk_written = False
    output_path: str | None = None
    if mutating and out_format is not None and write_path is not None:
        # Preserve the original source path so docx round-trips can template.
        if source_path_attr is not None and getattr(current, "source_path", None) is None:
            try:
                current.source_path = source_path_attr  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
        try:
            rendered = from_ast(
                current,
                target_format=out_format,
                flavor=config.flavor,
                preserve_formatting=(out_format == "docx"),
            )
        except All2MdError as e:
            return EditDocumentOutput(
                success=False,
                disk_written=False,
                results=results,
                warnings=[f"Edits applied in memory but rendering to {out_format} failed: {e}"],
            )

        data = rendered.encode("utf-8") if isinstance(rendered, str) else rendered
        if not isinstance(data, (bytes, bytearray)):
            return EditDocumentOutput(
                success=False,
                results=results,
                warnings=[f"Unexpected render output type for {out_format}: {type(data)}."],
            )
        try:
            handle = secure_open_for_write(write_path)
            try:
                handle.write(bytes(data))
            finally:
                handle.close()
        except (OSError, MCPSecurityError) as e:
            return EditDocumentOutput(
                success=False,
                disk_written=False,
                results=results,
                warnings=[f"Edits applied in memory but writing to disk failed: {e}"],
            )

        disk_written = True
        output_path = str(write_path)
        logger.info(f"edit_document wrote {len(edits)} edit(s) to: {output_path}")
        if out_format in _BINARY_FORMATS:
            warnings.append(
                f"{out_format.upper()} was re-rendered from the edited content; "
                "some fine-grained formatting may differ from the original."
            )

    return EditDocumentOutput(
        success=True,
        disk_written=disk_written,
        output_path=output_path,
        results=results,
        warnings=warnings,
    )


__all__ = [
    "edit_document_impl",
]
