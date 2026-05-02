#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands/edit.py
"""Web-based editor command for all2md CLI.

Launches a tiny local HTTP server hosting Toast UI Editor pre-loaded with the
document's markdown form. Users edit in markdown or WYSIWYG and POST the result
back, choosing target format and path; an existing file is backed up to ``.bak``
before being overwritten.
"""

from __future__ import annotations

import argparse
import http.server
import io
import json
import socketserver
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

from all2md.api import from_ast, to_ast
from all2md.cli.builder import (
    EXIT_ERROR,
    EXIT_FILE_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from all2md.constants import DocumentFormat
from all2md.converter_registry import registry
from all2md.utils.io_utils import backup_file

ASSET_FILES = ("toastui-editor-all.min.js", "toastui-editor.min.css")
ASSET_CONTENT_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}

# Canonical filesystem extension for each target format. Used to suggest a
# default output path when the user switches formats in the dropdown.
FORMAT_EXTENSIONS: Dict[str, str] = {
    "markdown": "md",
    "html": "html",
    "plaintext": "txt",
    "json": "json",
    "yaml": "yaml",
    "csv": "csv",
    "xml": "xml",
    "rst": "rst",
    "asciidoc": "adoc",
    "org": "org",
    "latex": "tex",
    "docx": "docx",
    "odt": "odt",
    "odp": "odp",
    "pptx": "pptx",
    "epub": "epub",
    "pdf": "pdf",
    "ipynb": "ipynb",
    "rtf": "rtf",
}


def _available_target_formats() -> List[Dict[str, str]]:
    """Return target formats whose renderer can actually be loaded.

    Walks ``registry.list_formats()`` and probes each via ``get_renderer``.
    Formats whose optional dependencies aren't installed are dropped so the
    dropdown only shows usable choices. ``markdown`` is always first.
    """
    available: List[Dict[str, str]] = []
    seen: set[str] = set()

    for fmt in sorted(registry.list_formats()):
        if fmt in ("auto", "markdown") or fmt in seen:
            continue
        try:
            registry.get_renderer(fmt)
        except Exception:
            continue
        available.append({"value": fmt, "label": fmt, "extension": FORMAT_EXTENSIONS.get(fmt, fmt)})
        seen.add(fmt)

    available.insert(0, {"value": "markdown", "label": "markdown", "extension": "md"})
    return available


def _build_save_defaults(source_path: Path, source_format: str) -> Tuple[str, str, bool]:
    """Compute the default (target_format, target_path, overwrite) tuple.

    For markdown originals the default is to save back over the file (with a
    .bak); for everything else the default is a sibling ``<stem>.md`` and the
    overwrite checkbox starts unchecked.
    """
    if source_format == "markdown":
        return ("markdown", str(source_path), True)
    sibling = source_path.with_suffix(".md")
    return ("markdown", str(sibling), False)


def _render_editor_page(
    template_path: Path,
    source_path: Path,
    initial_md: str,
    formats: List[Dict[str, str]],
    default_target_format: str,
    default_target_path: str,
    default_overwrite: bool,
) -> str:
    """Render the editor template with embedded JSON state."""
    template = template_path.read_text(encoding="utf-8")
    state = {
        "source_path": str(source_path),
        "initial_md": initial_md,
        "formats": formats,
        "default_target_format": default_target_format,
        "default_target_path": default_target_path,
        "default_overwrite": default_overwrite,
    }
    state_json = json.dumps(state)
    title = f"Editing {source_path.name} - all2md"
    html = template.replace("{TITLE}", title)
    html = html.replace("{INITIAL_STATE_JSON}", state_json)
    return html


def _convert_md_to_target(
    content: str,
    target_format: str,
    output_path: Path,
    source_path: Path | None = None,
) -> None:
    """Re-parse edited markdown and render it to the chosen target format.

    When ``source_path`` is provided and both source and target are docx, the
    original document is used as the rendering template (with its body cleared
    so the AST replaces it). This preserves theme, page setup, headers/
    footers, and custom paragraph styles on round-trip; pass ``source_path=None``
    to fall back to a generic render.
    """
    ast = to_ast(io.BytesIO(content.encode("utf-8")), source_format="markdown")
    kwargs: Dict[str, Any] = {}
    if source_path is not None and target_format == "docx" and source_path.suffix.lower() == ".docx":
        kwargs["template_path"] = str(source_path)
        kwargs["clear_template_body"] = True
    from_ast(ast, cast(DocumentFormat, target_format), output=output_path, **kwargs)


def handle_edit_command(args: list[str] | None = None) -> int:  # noqa: C901
    """Handle the ``edit`` subcommand."""
    parser = argparse.ArgumentParser(
        prog="all2md edit",
        description="Edit a document in a browser-based editor and save back.",
    )
    parser.add_argument("input", help="File to edit (stdin '-' is not supported)")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind (default: 0 = OS-assigned ephemeral)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open a browser tab",
    )
    parser.add_argument(
        "--default-format",
        help="Pre-select this format in the save dropdown (overrides default)",
    )
    parser.add_argument(
        "--no-preserve-formatting",
        action="store_true",
        help=(
            "When the source and target are both .docx, by default the edited "
            "document inherits the original's theme, page setup, headers/"
            "footers, and custom styles via template-based rendering. Pass "
            "this flag to disable that and render a generic .docx instead."
        ),
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    if parsed.input == "-":
        print(
            "Error: stdin input is not supported by 'edit' (saving back to stdin "
            "is meaningless). Pass a file path instead.",
            file=sys.stderr,
        )
        return EXIT_VALIDATION_ERROR

    input_path = Path(parsed.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {parsed.input}", file=sys.stderr)
        return EXIT_FILE_ERROR
    if not input_path.is_file():
        print(f"Error: Input must be a file, not a directory: {parsed.input}", file=sys.stderr)
        return EXIT_FILE_ERROR

    template_path = Path(__file__).parent / "themes" / "editor.html"
    assets_dir = Path(__file__).parent / "themes" / "assets"
    if not template_path.exists():
        print(f"Error: Editor template missing: {template_path}", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Detect source format and convert to markdown for the editor's initial value.
    try:
        source_format = registry.detect_format(str(input_path))
    except Exception as exc:
        print(f"Error: Could not detect format of {input_path.name}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(f"Loading {input_path.name} ({source_format})...")
    try:
        ast = to_ast(str(input_path), attachment_mode="base64")
        initial_md = from_ast(ast, "markdown")
    except Exception as exc:
        print(f"Error: Could not convert {input_path.name} to markdown: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if not isinstance(initial_md, str):
        print("Error: Markdown renderer did not return a string", file=sys.stderr)
        return EXIT_ERROR

    formats = _available_target_formats()
    default_format, default_path, default_overwrite = _build_save_defaults(input_path, source_format)
    if parsed.default_format:
        if any(f["value"] == parsed.default_format for f in formats):
            default_format = parsed.default_format
            ext = FORMAT_EXTENSIONS.get(default_format, default_format)
            default_path = str(input_path.with_suffix("." + ext))
            default_overwrite = Path(default_path) == input_path
        else:
            print(
                f"Warning: --default-format '{parsed.default_format}' is not " f"available; using '{default_format}'",
                file=sys.stderr,
            )

    page_html = _render_editor_page(
        template_path,
        input_path,
        initial_md,
        formats,
        default_format,
        default_path,
        default_overwrite,
    )

    class EditHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send_text(200, page_html, "text/html; charset=utf-8")
                return
            if path.startswith("/assets/"):
                self._serve_asset(path[len("/assets/") :])
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/save":
                self._handle_save()
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:
            print(f"[{self.log_date_time_string()}] {format % args}")

        def _send_text(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            self._send_text(status, json.dumps(payload), "application/json")

        def _serve_asset(self, name: str) -> None:
            if name not in ASSET_FILES:
                self._send_json(404, {"ok": False, "error": "asset not found"})
                return
            asset_path = assets_dir / name
            if not asset_path.is_file():
                self._send_json(404, {"ok": False, "error": "asset not found"})
                return
            ctype = ASSET_CONTENT_TYPES.get(asset_path.suffix, "application/octet-stream")
            self._send_bytes(200, asset_path.read_bytes(), ctype)

        def _handle_save(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8") if length else ""
                data = json.loads(body) if body else {}
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json(400, {"ok": False, "error": f"invalid JSON: {exc}"})
                return

            content = data.get("content")
            target_format = data.get("target_format")
            target_path_raw = data.get("target_path")
            overwrite = bool(data.get("overwrite", False))

            if (
                not isinstance(content, str)
                or not isinstance(target_format, str)
                or not isinstance(target_path_raw, str)
            ):
                self._send_json(
                    400,
                    {"ok": False, "error": "content, target_format, and target_path are required"},
                )
                return

            if not any(f["value"] == target_format for f in formats):
                self._send_json(
                    400,
                    {"ok": False, "error": f"format '{target_format}' is not available"},
                )
                return

            target_path = Path(target_path_raw)
            if not target_path.is_absolute():
                target_path = (input_path.parent / target_path).resolve()
            else:
                target_path = target_path.resolve()

            if target_path.exists() and not overwrite:
                self._send_json(
                    409,
                    {
                        "ok": False,
                        "error": (f"{target_path} already exists; tick 'Overwrite' " "or choose a different path."),
                    },
                )
                return

            backup_path = backup_file(target_path) if overwrite else None

            preserve_source = input_path if not parsed.no_preserve_formatting and source_format == "docx" else None
            try:
                _convert_md_to_target(content, target_format, target_path, source_path=preserve_source)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": f"save failed: {exc}"})
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "written": str(target_path),
                    "backup": str(backup_path) if backup_path else None,
                },
            )

    try:
        with socketserver.TCPServer((parsed.host, parsed.port), EditHandler) as httpd:
            chosen_port = httpd.server_address[1]
            url = f"http://{parsed.host}:{chosen_port}/"
            print(f"\nEditing at {url}")
            print("Press Ctrl+C to stop")
            if not parsed.no_browser:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\nShutting down editor...")
                return EXIT_SUCCESS
            return EXIT_SUCCESS
    except OSError as exc:
        if "Address already in use" in str(exc) or getattr(exc, "errno", None) == 98:
            print(f"Error: Port {parsed.port} is already in use", file=sys.stderr)
        else:
            print(f"Error: Could not start server: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
