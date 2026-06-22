#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""HTTP server command for all2md CLI.

This module provides the serve command for hosting documents via HTTP server
with on-demand conversion to HTML. Supports directory listings, multiple
themes, file upload forms, and REST API endpoints for development use.
"""

import argparse
import base64
import errno
import fnmatch
import http.server
import io
import json
import os
import socketserver
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from all2md.api import from_ast, to_ast
from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.cli.commands.shared import has_hidden_component, split_glob_pattern
from all2md.cli.config import apply_config_to_parser
from all2md.converter_registry import registry
from all2md.options.html import HtmlRendererOptions

# Filenames that can stand in for an auto-generated directory listing,
# in descending priority order.
INDEX_FILE_NAMES: Tuple[str, ...] = (
    "index.html",
    "index.htm",
    "index.md",
    "README.md",
    "readme.md",
)


def _get_content_type_for_format(format_name: str) -> str:
    """Get MIME type for a given output format.

    Parameters
    ----------
    format_name : str
        Output format name

    Returns
    -------
    str
        MIME type string

    """
    content_types = {
        "html": "text/html; charset=utf-8",
        "markdown": "text/markdown; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "plaintext": "text/plain; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "json": "application/json",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        "toml": "application/toml",
        "xml": "application/xml",
        "csv": "text/csv; charset=utf-8",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "odt": "application/vnd.oasis.opendocument.text",
        "rtf": "application/rtf",
        "epub": "application/epub+zip",
        "latex": "application/x-latex",
        "tex": "application/x-latex",
        "rst": "text/x-rst; charset=utf-8",
        "asciidoc": "text/asciidoc; charset=utf-8",
        "org": "text/org; charset=utf-8",
    }
    return content_types.get(format_name.lower(), "application/octet-stream")


def _generate_upload_form(theme_path: Path) -> str:
    """Generate HTML upload form with theme styling.

    Parameters
    ----------
    theme_path : Path
        Path to the theme template file

    Returns
    -------
    str
        HTML content for the upload form

    """
    # Get list of supported output formats
    supported_formats = registry.list_formats()
    format_options = ""
    for fmt in sorted(supported_formats):
        if fmt != "auto":  # Skip auto format
            format_options += f'<option value="{fmt}">{fmt}</option>\n'

    # Read theme template
    theme_content = theme_path.read_text(encoding="utf-8")

    # Generate form HTML
    form_html = (
        """
                <h1>Document Converter</h1>
                <p>Upload a document to convert it to another format.</p>

                <form method="POST" enctype="multipart/form-data" style="max-width: 600px; margin: 20px 0;">
                    <div style="margin-bottom: 20px;">
                        <label for="file" style="display: block; margin-bottom: 5px; font-weight: bold;">
                            Select Document:
                        </label>
                        <input type="file" name="file" id="file" required
                       style="display: block; width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 4px;">
                    </div>

                    <div style="margin-bottom: 20px;">
                        <label for="format" style="display: block; margin-bottom: 5px; font-weight: bold;">
                            Output Format:
                        </label>
                        <select name="format" id="format" required
                            style="display: block; width: 100%; padding: 10px; border: 2px solid #ddd;
                            border-radius: 4px;">
                            <option value="html" selected>html</option>
                """
        + format_options
        + """
            </select>
        </div>

        <button type="submit"
                style="padding: 12px 24px; background: #0066cc; color: white; border: none;
                       border-radius: 4px; font-size: 16px; cursor: pointer;">
            Convert Document
        </button>
    </form>

    <div style="margin-top: 40px; padding: 20px; background: #f5f5f5; border-radius: 4px;">
        <h3>Supported Input Formats:</h3>
        <p>PDF, DOCX, PPTX, HTML, Markdown, RTF, ODT, EPUB, and many more...</p>
    </div>
    """
    )

    # Apply theme template
    title = "Upload Document - all2md"
    html = theme_content.replace("{TITLE}", title)
    html = html.replace("{CONTENT}", form_html)

    return html


def _scan_directory_for_documents(
    directory: Path,
    recursive: bool,
    pattern: Optional[str] = None,
    include_hidden: bool = False,
) -> List[Path]:
    """Scan directory for supported document files.

    Parameters
    ----------
    directory : Path
        Directory to scan
    recursive : bool
        Whether to scan subdirectories recursively
    pattern : str, optional
        ``fnmatch`` pattern applied to filenames (e.g. ``*.docx``). When given,
        only matching files are kept (used for glob inputs like ``dir/*.docx``).
    include_hidden : bool
        Whether to include dot-files/dot-folders discovered during the scan.

    Returns
    -------
    list[Path]
        List of supported document file paths

    """
    # Get all files in directory (recursive or not based on flag)
    if recursive:
        files = [f for f in directory.rglob("*") if f.is_file()]
    else:
        files = [f for f in directory.iterdir() if f.is_file()]

    if not include_hidden:
        files = [f for f in files if not has_hidden_component(f, directory)]

    if pattern is not None:
        files = [f for f in files if fnmatch.fnmatch(f.name, pattern)]

    # Filter to only supported formats by checking if they can be parsed
    supported_files = []
    for file in files:
        try:
            registry.detect_format(str(file))
            supported_files.append(file)
        except Exception:
            # Skip unsupported files
            pass

    return supported_files


def _find_index_file(directory: Path) -> Optional[Path]:
    """Return an index file inside ``directory``, if one exists.

    Looks for ``index.html``, ``index.htm``, ``index.md``, ``README.md`` (case-
    insensitive) in descending priority order. Returns ``None`` if no candidate
    is present or the directory cannot be read.
    """
    if not directory.is_dir():
        return None
    try:
        entries = {entry.name.lower(): entry for entry in directory.iterdir() if entry.is_file()}
    except OSError:
        return None
    for candidate in INDEX_FILE_NAMES:
        match = entries.get(candidate.lower())
        if match is not None:
            return match
    return None


def _compute_directory_state(
    base_dir: Path,
    recursive: bool,
    pattern: Optional[str] = None,
    include_hidden: bool = False,
) -> Tuple[List[Path], set, Dict[str, Path], set]:
    """Scan ``base_dir`` and derive everything the serve loop tracks.

    Returns a tuple of ``(files, known_subdirs, file_mapping, signature)``,
    where ``signature`` is a set of ``(path, size, mtime)`` triples used to
    cheaply detect changes between polls.
    """
    files = _scan_directory_for_documents(base_dir, recursive, pattern, include_hidden)
    subdirs: set = set()
    mapping: Dict[str, Path] = {}
    signature: set = set()
    for file in files:
        rel_path = file.relative_to(base_dir)
        parent = str(rel_path.parent).replace("\\", "/")
        if parent == ".":
            parent = ""
        if parent:
            parts = parent.split("/")
            for i in range(len(parts)):
                subdirs.add("/".join(parts[: i + 1]))
        url_path = "/" + quote(str(rel_path).replace("\\", "/"))
        mapping[url_path] = file
        try:
            stat = file.stat()
            signature.add((str(file), stat.st_size, stat.st_mtime))
        except OSError:
            # File vanished or became unreadable between listing and stat;
            # omit it from the change signature.
            pass
    return files, subdirs, mapping, signature


def _generate_directory_index(
    all_files: List[Path],
    theme_path: Path,
    base_dir: Path,
    current_subdir: str = "",
    enable_upload: bool = False,
) -> str:
    """Generate HTML index page for a directory listing.

    Shows only files and immediate subdirectories at the specified level,
    with breadcrumb navigation for parent directories.

    Parameters
    ----------
    all_files : list[Path]
        All supported file paths across all subdirectories
    theme_path : Path
        Path to the theme template file
    base_dir : Path
        Base directory path for computing relative paths
    current_subdir : str
        Relative subdirectory path (e.g., "" for root, "reports/2024" for nested)
    enable_upload : bool
        Whether to show link to upload page (root only)

    Returns
    -------
    str
        HTML content for the index page

    """
    # Read theme template
    theme_content = theme_path.read_text(encoding="utf-8")

    # Filter files to current directory level and find child subdirectories
    current_files: List[Path] = []
    child_dir_names: set[str] = set()

    for file in all_files:
        rel_path = file.relative_to(base_dir)
        parent = str(rel_path.parent).replace("\\", "/")
        if parent == ".":
            parent = ""

        if parent == current_subdir:
            current_files.append(file)
        elif current_subdir:
            prefix = current_subdir + "/"
            if parent.startswith(prefix):
                remainder = parent[len(prefix) :]
                child_dir_names.add(remainder.split("/")[0])
        elif parent:
            child_dir_names.add(parent.split("/")[0])

    # Generate breadcrumbs
    url_path = "/" + current_subdir + "/" if current_subdir else "/"
    breadcrumbs = _generate_breadcrumbs(url_path)

    # Directory display name
    if current_subdir:
        dir_display = current_subdir.split("/")[-1]
    else:
        dir_display = base_dir.name

    # Build content
    content = breadcrumbs
    content += f"<h1>Directory: {dir_display}</h1>"

    # Add upload link if enabled (root only)
    if enable_upload and not current_subdir:
        content += """
        <div style="margin: 20px 0; padding: 15px; background: #e8f4f8;
                    border-left: 4px solid #0066cc; border-radius: 4px;">
            <a href="/upload" style="text-decoration: none; color: #0066cc; font-weight: bold;">
                Upload & Convert Document
            </a>
            <span style="margin-left: 10px; color: #666;">- Convert any document to different format</span>
        </div>
        """

    # Show subdirectories
    if child_dir_names:
        content += "<div style='font-family: monospace;'>"
        content += "<ul style='list-style: none; padding-left: 20px;'>"
        for dir_name in sorted(child_dir_names):
            if current_subdir:
                dir_url = "/" + "/".join(quote(p) for p in current_subdir.split("/")) + "/" + quote(dir_name) + "/"
            else:
                dir_url = "/" + quote(dir_name) + "/"
            content += "<li style='margin: 5px 0;'>"
            content += f"<a href='{dir_url}' style='text-decoration: none; font-size: 1.0em;'>{dir_name}/</a>"
            content += "</li>"
        content += "</ul></div>"

    # Show file count
    content += f"<p>Found {len(current_files)} document(s)"
    if child_dir_names:
        content += f" and {len(child_dir_names)} subdirectory(ies)"
    content += " - click to view:</p>"

    # List files at this level
    if current_files:
        content += "<div style='font-family: monospace;'>"
        content += "<ul style='list-style: none; padding-left: 20px;'>"
        for file in sorted(current_files, key=lambda f: f.name.lower()):
            rel_path = file.relative_to(base_dir)
            url = "/" + quote(str(rel_path).replace("\\", "/"))
            modified_str: Optional[str] = None
            created_str: Optional[str] = None
            try:
                stat_result = file.stat()
                size_str = _format_file_size(stat_result.st_size)
                modified_str = f"modified {_format_timestamp(stat_result.st_mtime)}"
                created_ts = _file_created_timestamp(stat_result)
                if created_ts is not None:
                    created_str = f"created {_format_timestamp(created_ts)}"
            except OSError:
                size_str = "?"
            details = " · ".join(part for part in (size_str, modified_str, created_str) if part)
            content += "<li style='margin: 5px 0;'>"
            content += f"<a href='{url}' style='text-decoration: none; font-size: 1.0em;'>{file.name}</a>"
            content += f" <span style='color: #888; font-size: 0.9em;'>({details})</span>"
            content += "</li>"
        content += "</ul></div>"

    # Apply theme template
    title = f"Directory: {dir_display}"
    html = theme_content.replace("{TITLE}", title)
    html = html.replace("{CONTENT}", content)

    return html


def _format_timestamp(timestamp: float) -> str:
    """Format an epoch timestamp as a compact local ``YYYY-MM-DD HH:MM`` string."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _file_created_timestamp(stat_result: os.stat_result) -> Optional[float]:
    """Best-effort file creation time, or ``None`` when it isn't reliably available.

    Uses ``st_birthtime`` when the platform provides it (macOS, *BSD, and Windows
    on Python 3.12+). On Windows without ``st_birthtime``, ``st_ctime`` is the
    creation time. On Linux ``st_ctime`` is the inode-change time (not creation),
    so we return ``None`` there rather than display a misleading value.
    """
    birthtime = getattr(stat_result, "st_birthtime", None)
    if birthtime is not None:
        return float(birthtime)
    # os.name (not sys.platform) avoids mypy's platform-specific narrowing, which
    # would otherwise flag one branch as unreachable depending on the OS mypy runs on.
    if os.name == "nt":
        return stat_result.st_ctime
    return None


def _bind_http_server(
    host: str, port: int, handler: type[http.server.BaseHTTPRequestHandler]
) -> Tuple["_ThreadingHTTPServer", bool]:
    """Bind the serve HTTP server, falling back to a random free port if taken.

    Returns ``(httpd, fell_back)`` where ``fell_back`` is ``True`` when the
    requested ``port`` was unavailable and the OS assigned a random free port
    (bind to port 0) instead. Re-raises the original ``OSError`` for failures
    other than "address in use".
    """
    try:
        return _ThreadingHTTPServer((host, port), handler), False
    except OSError as e:
        # Treat the port as unavailable when it is already in use (EADDRINUSE) or
        # access is denied (EACCES) -- on Windows, an in-use listening port with
        # SO_REUSEADDR set surfaces as WSAEACCES (WinError 10013) rather than
        # WSAEADDRINUSE (10048), and privileged ports raise EACCES everywhere.
        # In all of these cases, fall back to an OS-assigned free port.
        winerror = getattr(e, "winerror", None)
        if (
            e.errno in (errno.EADDRINUSE, errno.EACCES)
            or winerror in (10048, 10013)
            or "Address already in use" in str(e)
        ):
            return _ThreadingHTTPServer((host, 0), handler), True
        raise


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Parameters
    ----------
    size_bytes : int
        File size in bytes

    Returns
    -------
    str
        Formatted file size string

    """
    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def _generate_breadcrumbs(url_path: str) -> str:
    """Generate HTML breadcrumb navigation for a URL path.

    Parameters
    ----------
    url_path : str
        URL path with unencoded display names (e.g., "/reports/2024/")

    Returns
    -------
    str
        HTML string containing breadcrumb navigation

    """
    parts = [p for p in url_path.strip("/").split("/") if p]

    breadcrumb_style = "padding: 10px 0; margin-bottom: 20px; font-size: 0.9em; border-bottom: 1px solid #eee;"
    separator = ' <span style="color: #999; margin: 0 5px;">&rsaquo;</span> '

    crumbs = ['<a href="/">Home</a>']
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            crumbs.append(f'<span style="color: #666;">{part}</span>')
        else:
            encoded_path = "/" + "/".join(quote(p) for p in parts[: i + 1]) + "/"
            crumbs.append(f'<a href="{encoded_path}">{part}</a>')

    return f'<nav style="{breadcrumb_style}">{separator.join(crumbs)}</nav>'


def _parse_multipart_form_data(body: bytes, content_type: str) -> Dict[str, Any]:
    """Parse multipart/form-data without using deprecated cgi module.

    Parameters
    ----------
    body : bytes
        Raw request body
    content_type : str
        Content-Type header value

    Returns
    -------
    dict
        Dictionary mapping field names to their values or file data.
        File fields return dict with 'filename' and 'data' keys.

    Raises
    ------
    ValueError
        If no boundary found in Content-Type header

    """
    # Extract boundary from content type
    boundary = None
    for ct_part in content_type.split(";"):
        ct_part = ct_part.strip()
        if ct_part.startswith("boundary="):
            boundary = ct_part.split("=", 1)[1]
            # Remove quotes if present
            boundary = boundary.strip('"')
            break

    if not boundary:
        raise ValueError("No boundary found in Content-Type")

    # Split by boundary markers
    boundary_bytes = ("--" + boundary).encode("utf-8")
    parts = body.split(boundary_bytes)

    result: Dict[str, Any] = {}

    for part_bytes in parts:
        # Skip empty parts and end marker
        part_bytes = part_bytes.strip()
        if not part_bytes or part_bytes == b"--":
            continue

        # Split headers from content
        headers_section: bytes
        content: bytes
        if b"\r\n\r\n" in part_bytes:
            headers_section, content = part_bytes.split(b"\r\n\r\n", 1)
        elif b"\n\n" in part_bytes:
            headers_section, content = part_bytes.split(b"\n\n", 1)
        else:
            continue

        # Parse Content-Disposition header
        headers = headers_section.decode("utf-8", errors="ignore")
        field_name = None
        filename = None

        for line in headers.split("\n"):
            line = line.strip()
            if line.lower().startswith("content-disposition:"):
                # Parse field name and filename
                for param in line.split(";"):
                    param = param.strip()
                    if "name=" in param:
                        field_name = param.split("=", 1)[1].strip('"')
                    elif "filename=" in param:
                        filename = param.split("=", 1)[1].strip('"')

        if field_name:
            if filename:
                # File field
                result[field_name] = {"filename": filename, "data": content.rstrip(b"\r\n")}
            else:
                # Text field
                result[field_name] = content.rstrip(b"\r\n").decode("utf-8", errors="ignore")

    return result


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """HTTPServer that handles each request in a daemon thread.

    Daemon threads let the process exit promptly on shutdown even if a
    long-running conversion is still in flight.
    """

    daemon_threads = True
    allow_reuse_address = True


def _create_serve_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``serve`` command.

    Exposed as a factory so ``config generate`` can introspect the command's
    options to emit a ``[serve]`` config-template section.
    """
    parser = argparse.ArgumentParser(
        prog="all2md serve",
        description="Serve document(s) as HTML via HTTP server with theme support.",
    )
    parser.add_argument("input", help="File, directory, or glob pattern (e.g. 'docs/*.pdf') to serve")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to serve on (default: 127.0.0.1)")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively serve subdirectories (for directory input)"
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include dot-files and dot-folders when scanning a directory or glob (skipped by default)",
    )
    parser.add_argument("--toc", action="store_true", help="Include table of contents")
    parser.add_argument("--dark", action="store_true", help="Use dark mode theme")
    parser.add_argument(
        "--theme",
        help="Custom theme template path or built-in theme name (minimal, dark, newspaper, docs, sidebar)",
    )
    parser.add_argument(
        "--browse",
        action="store_true",
        help="Open the served URL in the default web browser once the server starts",
    )
    parser.add_argument(
        "--enable-upload",
        action="store_true",
        help="Enable file upload form at /upload (development only)",
    )
    parser.add_argument(
        "--enable-api",
        action="store_true",
        help="Enable REST API endpoint at /api/convert (development only)",
    )
    parser.add_argument(
        "--max-upload-size",
        type=int,
        default=50,
        help="Maximum upload file size in MB (default: 50)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching - always render fresh content (useful for live editing)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help=(
            "Seconds between directory rescans for live index updates "
            "(directory mode only; set to 0 to disable; default: 2.0)"
        ),
    )
    parser.add_argument(
        "--force-auto-index",
        action="store_true",
        help=(
            "Always use the auto-generated directory listing, even when an "
            "index.html, index.md, or README.md is present in the directory"
        ),
    )
    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [serve] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )
    return parser


def handle_serve_command(args: list[str] | None = None) -> int:  # noqa: C901
    """Handle serve command to serve documents via HTTP server.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'serve')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    parser = _create_serve_parser()

    try:
        # Pre-parse to discover config flags, fold the [serve] config section in as
        # defaults, then parse for real so explicit CLI flags win over config.
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "serve", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    # Resolve the input: a glob pattern, a directory, or a single file.
    # A glob is served as a directory listing restricted to matching files, so
    # live rescans continue to pick up newly added matches.
    serve_pattern: Optional[str] = None
    if any(char in parsed.input for char in "*?["):
        input_path, serve_pattern, glob_recursive = split_glob_pattern(parsed.input)
        if not input_path.is_dir():
            print(f"Error: No directory to serve for pattern: {parsed.input}", file=sys.stderr)
            return EXIT_FILE_ERROR
        if glob_recursive:
            parsed.recursive = True
        # Show the filtered listing, not a hand-authored index in the directory.
        parsed.force_auto_index = True
    else:
        input_path = Path(parsed.input)
        if not input_path.exists():
            print(f"Error: Input path not found: {parsed.input}", file=sys.stderr)
            return EXIT_FILE_ERROR

    # Select theme template
    if parsed.theme:
        # Check if it's a built-in theme name or a custom path
        theme_path = Path(parsed.theme)
        # First check if it's a valid HTML file path
        if theme_path.exists() and theme_path.is_file() and theme_path.suffix == ".html":
            # Use the provided file path
            pass
        else:
            # Try as built-in theme name
            builtin_theme = Path(__file__).parent / "themes" / f"{parsed.theme}.html"
            if builtin_theme.exists():
                theme_path = builtin_theme
            else:
                print(f"Error: Theme not found: {parsed.theme}", file=sys.stderr)
                print("Available built-in themes: minimal, dark, newspaper, docs, sidebar", file=sys.stderr)
                return EXIT_FILE_ERROR
    elif parsed.dark:
        theme_path = Path(__file__).parent / "themes" / "dark.html"
    else:
        theme_path = Path(__file__).parent / "themes" / "minimal.html"

    # Verify theme template exists
    if not theme_path.exists():
        print(f"Error: Theme template not found: {theme_path}", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Determine if input is file or directory (a glob always serves a listing).
    is_directory = serve_pattern is not None or input_path.is_dir()

    # Shared state guarded by state_lock so the polling thread and request
    # handler threads can coexist safely.
    state_lock = threading.Lock()
    file_cache: Dict[str, str] = {}
    index_cache: Dict[str, str] = {}
    file_mapping: Dict[str, Path] = {}
    supported_files: List[Path] = []
    known_subdirs: set = set()
    scan_signature: set = set()

    def _convert_to_html(file_path: Path, breadcrumb_path: Optional[str] = None) -> str:
        """Convert a single document to themed HTML, optionally injecting breadcrumbs."""
        doc = to_ast(str(file_path), attachment_mode="base64")
        doc.metadata["title"] = f"{file_path.name} - all2md"
        html_opts = HtmlRendererOptions(
            template_mode="replace",
            template_file=str(theme_path),
            include_toc=parsed.toc,
            external_links_new_tab=True,
        )
        html_content = from_ast(doc, "html", renderer_options=html_opts)
        if not isinstance(html_content, str):
            raise RuntimeError("Expected string result from HTML rendering")
        if breadcrumb_path:
            breadcrumbs = _generate_breadcrumbs(breadcrumb_path)
            html_content = html_content.replace("<body>", "<body>\n" + breadcrumbs, 1)
        return html_content

    def _rescan_directory(initial: bool = False) -> bool:
        """Rescan the served directory; update state and drop stale caches.

        Returns ``True`` when the file set has actually changed (or on the
        initial scan), ``False`` otherwise.
        """
        if not is_directory:
            return False
        new_files, new_subdirs, new_mapping, new_signature = _compute_directory_state(
            input_path, parsed.recursive, serve_pattern, parsed.include_hidden
        )
        with state_lock:
            if not initial and new_signature == scan_signature:
                return False
            old_url_paths = set(file_mapping.keys())
            scan_signature.clear()
            scan_signature.update(new_signature)
            supported_files[:] = new_files
            known_subdirs.clear()
            known_subdirs.update(new_subdirs)
            file_mapping.clear()
            file_mapping.update(new_mapping)
            # Any cached directory listing might now be stale.
            index_cache.clear()
            # Drop file-cache entries for files that vanished from disk.
            for removed in old_url_paths - set(new_mapping.keys()):
                file_cache.pop(removed, None)
        return True

    # Setup based on input type
    if is_directory:
        print(f"Preparing directory: {input_path.name}")
        _rescan_directory(initial=True)

        # Empty directories are still legitimate if they ship an index.html /
        # index.md / README.md the user wants served.
        if not supported_files and (parsed.force_auto_index or _find_index_file(input_path) is None):
            print(f"Error: No supported document files found in {input_path}", file=sys.stderr)
            return EXIT_ERROR

        mode_str = "recursively" if parsed.recursive else "in directory"
        print(f"Found {len(supported_files)} document(s) {mode_str} - will convert on demand")
    else:
        print(f"Converting {input_path.name}...")
        try:
            html_content = _convert_to_html(input_path)
            with state_lock:
                file_cache["/"] = html_content
                file_mapping["/"] = input_path
        except Exception as e:
            print(f"Error: Could not convert {input_path.name}: {e}", file=sys.stderr)
            return EXIT_ERROR

    def _is_directory_index_path(path: str) -> bool:
        """Return ``True`` when ``path`` addresses a directory listing in directory mode."""
        if not is_directory:
            return False
        if path == "/":
            return True
        subdir = unquote(path.strip("/"))
        with state_lock:
            return subdir in known_subdirs

    def _render_directory_index(path: str) -> Optional[str]:
        """Render the index for ``path``, preferring a hand-authored index file.

        Returns ``None`` if rendering fails outright.
        """
        subdir = unquote(path.strip("/")) if path != "/" else ""
        # Resolve and contain the target directory. ``_is_directory_index_path``
        # already gates callers to known subdirs; re-checking containment here
        # ensures a request path can never resolve outside the served root and
        # lets static analysis see the path is constrained.
        root = input_path.resolve()
        target_dir = (root / subdir).resolve() if subdir else root
        if not (target_dir == root or target_dir.is_relative_to(root)):
            return None

        if not parsed.force_auto_index:
            index_file = _find_index_file(target_dir)
            if index_file is not None:
                breadcrumb_path: Optional[str] = ("/" + subdir + "/") if subdir else None
                try:
                    return _convert_to_html(index_file, breadcrumb_path=breadcrumb_path)
                except Exception as e:
                    # Fall back to the auto-generated listing on failure.
                    print(f"Error rendering index file {index_file}: {e}", file=sys.stderr)

        with state_lock:
            files_snapshot = list(supported_files)
        return _generate_directory_index(
            files_snapshot,
            theme_path,
            input_path,
            current_subdir=subdir,
            enable_upload=parsed.enable_upload,
        )

    # Create custom request handler
    class ServeHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            # Remove query string if present
            path = self.path.split("?")[0]

            # Handle upload form route
            if path == "/upload" and parsed.enable_upload:
                upload_form = _generate_upload_form(theme_path)
                self._send_html(upload_form)
                return

            # Directory index requests (root or known subdirectory)
            if _is_directory_index_path(path):
                cached: Optional[str] = None
                if not parsed.no_cache:
                    with state_lock:
                        cached = index_cache.get(path)
                if cached is not None:
                    self._send_html(cached)
                    return
                # In --no-cache mode the polling thread is off, so force a
                # rescan on root requests to keep the listing fresh.
                if parsed.no_cache and path == "/":
                    _rescan_directory()
                html_content = _render_directory_index(path)
                if html_content is None:
                    self._send_500("Failed to render directory index")
                    return
                if not parsed.no_cache:
                    with state_lock:
                        index_cache[path] = html_content
                self._send_html(html_content)
                return

            # File request
            with state_lock:
                file_path = file_mapping.get(path)
                cached_file: Optional[str] = file_cache.get(path) if file_path else None

            if file_path is None:
                self._send_404()
                return

            if cached_file is not None and not parsed.no_cache:
                self._send_html(cached_file)
                return

            print(f"Converting {file_path.name}...")
            try:
                breadcrumb_path = unquote(path) if is_directory else None
                html_content = _convert_to_html(file_path, breadcrumb_path=breadcrumb_path)
            except Exception as e:
                print(f"Error converting {file_path.name}: {e}", file=sys.stderr)
                self._send_500(f"Error converting document: {e}")
                return

            if not parsed.no_cache:
                with state_lock:
                    file_cache[path] = html_content
            self._send_html(html_content)

        def _send_html(self, html: str) -> None:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def _send_404(self) -> None:
            self.send_response(404)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>404 Not Found</h1><p>The requested document was not found.</p></body></html>"
            )

        def _send_500(self, message: str) -> None:
            self.send_response(500)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            error_html = f"<html><body><h1>500 Internal Server Error</h1><p>{message}</p></body></html>"
            self.wfile.write(error_html.encode("utf-8"))

        def log_message(self, format: str, *args: Any) -> None:
            # Custom logging format
            print(f"[{self.log_date_time_string()}] {format % args}")

        def do_POST(self) -> None:
            # Remove query string if present
            path = self.path.split("?")[0]

            # Handle upload form submission
            if path == "/upload" and parsed.enable_upload:
                self._handle_upload()
                return

            # Handle API conversion
            if path == "/api/convert" and parsed.enable_api:
                self._handle_api_convert()
                return

            # Not found
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            error = {"error": "Not found", "message": "The requested endpoint does not exist"}
            self.wfile.write(json.dumps(error).encode("utf-8"))

        def _handle_upload(self) -> None:
            """Handle file upload from web form."""
            try:
                # Parse multipart form data
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type:
                    self.send_response(400)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    error_html = "<html><body><h1>400 Bad Request</h1><p>Expected multipart/form-data</p></body></html>"
                    self.wfile.write(error_html.encode("utf-8"))
                    return

                # Get content length
                content_length = int(self.headers.get("Content-Length", 0))
                max_size_bytes = parsed.max_upload_size * 1024 * 1024  # Convert MB to bytes

                if content_length > max_size_bytes:
                    self.send_response(413)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    error_html = (
                        f"<html><body><h1>413 Payload Too Large</h1>"
                        f"<p>File size exceeds {parsed.max_upload_size}MB limit</p></body></html>"
                    )
                    self.wfile.write(error_html.encode("utf-8"))
                    return

                # Read and parse form data
                body = self.rfile.read(content_length)
                form_data = _parse_multipart_form_data(body, content_type)

                # Get file and format
                if "file" not in form_data:
                    self.send_response(400)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    error_html = "<html><body><h1>400 Bad Request</h1><p>No file uploaded</p></body></html>"
                    self.wfile.write(error_html.encode("utf-8"))
                    return

                file_item = form_data["file"]
                target_format = form_data.get("format", "html")

                # Extract file data
                if isinstance(file_item, dict) and "data" in file_item:
                    file_data = file_item["data"]
                else:
                    file_data = file_item

                # Convert document
                print(f"Converting uploaded file to {target_format}...")
                doc = to_ast(io.BytesIO(file_data))

                # Convert to target format
                result = from_ast(doc, target_format)

                # Send response with appropriate content type
                content_type = _get_content_type_for_format(target_format)
                self.send_response(200)
                self.send_header("Content-type", content_type)
                self.end_headers()

                if isinstance(result, str):
                    self.wfile.write(result.encode("utf-8"))
                elif isinstance(result, bytes):
                    self.wfile.write(result)

            except Exception as e:
                print(f"Error in upload handler: {e}", file=sys.stderr)
                self.send_response(500)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                error_html = f"<html><body><h1>500 Internal Server Error</h1><p>Error: {e}</p></body></html>"
                self.wfile.write(error_html.encode("utf-8"))

        def _handle_api_convert(self) -> None:
            """Handle API conversion request."""
            try:
                # Parse multipart form data or JSON
                content_type = self.headers.get("Content-Type", "")

                if "multipart/form-data" in content_type:
                    # Get content length and check size
                    content_length = int(self.headers.get("Content-Length", 0))
                    max_size_bytes = parsed.max_upload_size * 1024 * 1024

                    if content_length > max_size_bytes:
                        self.send_response(413)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        error = {
                            "error": "Payload too large",
                            "message": f"File size exceeds {parsed.max_upload_size}MB limit",
                        }
                        self.wfile.write(json.dumps(error).encode("utf-8"))
                        return

                    # Read and parse form data
                    body = self.rfile.read(content_length)
                    form_data = _parse_multipart_form_data(body, content_type)

                    if "file" not in form_data:
                        self.send_response(400)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        error = {"error": "Bad request", "message": "No file provided"}
                        self.wfile.write(json.dumps(error).encode("utf-8"))
                        return

                    file_item = form_data["file"]
                    target_format = form_data.get("format", "html")

                    # Extract file data
                    if isinstance(file_item, dict) and "data" in file_item:
                        file_data = file_item["data"]
                    else:
                        file_data = file_item

                else:
                    # Assume JSON with base64-encoded file
                    content_length = int(self.headers.get("Content-Length", 0))
                    max_size_bytes = parsed.max_upload_size * 1024 * 1024

                    if content_length > max_size_bytes:
                        self.send_response(413)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        error = {
                            "error": "Payload too large",
                            "message": f"Request size exceeds {parsed.max_upload_size}MB limit",
                        }
                        self.wfile.write(json.dumps(error).encode("utf-8"))
                        return

                    json_body = self.rfile.read(content_length).decode("utf-8")
                    data = json.loads(json_body)

                    if "file" not in data:
                        self.send_response(400)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        error = {"error": "Bad request", "message": "No file data provided"}
                        self.wfile.write(json.dumps(error).encode("utf-8"))
                        return

                    # Decode base64 file data
                    file_data = base64.b64decode(data["file"])
                    target_format = data.get("format", "html")

                # Convert document
                print(f"API: Converting to {target_format}...")
                doc = to_ast(io.BytesIO(file_data))
                result = from_ast(doc, target_format)

                # Send response with appropriate content type
                content_type = _get_content_type_for_format(target_format)
                self.send_response(200)
                self.send_header("Content-type", content_type)
                self.end_headers()

                if isinstance(result, str):
                    self.wfile.write(result.encode("utf-8"))
                elif isinstance(result, bytes):
                    self.wfile.write(result)

            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                error = {"error": "Invalid JSON", "message": str(e)}
                self.wfile.write(json.dumps(error).encode("utf-8"))
            except Exception as e:
                print(f"Error in API handler: {e}", file=sys.stderr)
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                error = {"error": "Internal server error", "message": str(e)}
                self.wfile.write(json.dumps(error).encode("utf-8"))

    # Start server. If the requested port is taken, fall back to an OS-assigned
    # random free port instead of giving up (port 8000 is frequently in use).
    try:
        httpd, fell_back = _bind_http_server(parsed.host, parsed.port, ServeHandler)
    except OSError as e:
        print(f"Error: Could not start server: {e}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    # Use the port we actually bound (differs from --port when we fell back).
    bound_port = httpd.server_address[1]
    if fell_back:
        print(f"Port {parsed.port} is unavailable; bound a random free port instead.", file=sys.stderr)

    url = f"http://{parsed.host}:{bound_port}/"
    print(f"\nServing at {url}")

    # Print development warning if upload or API is enabled
    if parsed.enable_upload or parsed.enable_api:
        print("\n" + "=" * 70)
        print("WARNING: Development features enabled")
        print("=" * 70)
        if parsed.enable_upload:
            print(f"  - File upload form: {url}upload")
        if parsed.enable_api:
            print(f"  - REST API endpoint: {url}api/convert")
        print(f"  - Maximum upload size: {parsed.max_upload_size}MB")
        print("\nThis server is for DEVELOPMENT USE ONLY.")
        print("DO NOT expose to untrusted networks or use in production.")
        print("=" * 70 + "\n")

    print("Press Ctrl+C to stop")

    # Open the served URL in the browser when requested (skipped under test mode,
    # matching `all2md view`). Use a loopback host for the browser when bound to a
    # wildcard address, which browsers can't navigate to directly.
    if parsed.browse and not os.environ.get("ALL2MD_TEST_NO_BROWSER"):
        # nosec B104: not binding here -- detecting a wildcard bind host so the
        # browser is pointed at a reachable loopback address instead.
        wildcard_hosts = ("0.0.0.0", "::", "")  # nosec B104
        browse_host = "127.0.0.1" if parsed.host in wildcard_hosts else parsed.host
        browse_url = f"http://{browse_host}:{bound_port}/"
        print(f"Opening {browse_url} in browser...")
        try:
            webbrowser.open(browse_url)
        except Exception as e:  # pragma: no cover - browser launch is best-effort
            print(f"Could not open browser: {e}", file=sys.stderr)

    stop_event = threading.Event()

    # Background polling for live directory updates. Skipped in single-file
    # mode, when polling is disabled, or when caching is off (rescan happens
    # inline on each request anyway).
    poll_thread: Optional[threading.Thread] = None
    if is_directory and parsed.poll_interval > 0 and not parsed.no_cache:

        def _poll_loop() -> None:
            while not stop_event.is_set():
                if stop_event.wait(timeout=parsed.poll_interval):
                    return
                try:
                    if _rescan_directory():
                        with state_lock:
                            count = len(supported_files)
                        print(f"Directory changed: {count} document(s) tracked")
                except Exception as exc:
                    print(f"Directory poll error: {exc}", file=sys.stderr)

        poll_thread = threading.Thread(target=_poll_loop, name="all2md-poll", daemon=True)
        poll_thread.start()

    # Run the server in a background thread so the main thread can react to
    # SIGINT without waiting for the next inbound request to unblock select().
    server_thread = threading.Thread(target=httpd.serve_forever, name="all2md-serve", daemon=True)
    server_thread.start()

    try:
        # stop_event.wait with a periodic timeout keeps Python returning to
        # the interpreter so KeyboardInterrupt can fire on Windows.
        while not stop_event.is_set():
            if stop_event.wait(timeout=0.5):
                break
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
    finally:
        stop_event.set()
        httpd.shutdown()
        httpd.server_close()
        if poll_thread is not None:
            poll_thread.join(timeout=2.0)
        server_thread.join(timeout=5.0)

    return EXIT_SUCCESS
