#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""HTTP server command for all2md CLI.

This module provides the serve command for hosting documents via HTTP server
with on-demand conversion to HTML. Supports directory listings, multiple
themes, file upload forms, and REST API endpoints for development use.
"""
import argparse
import base64
import http.server
import io
import json
import socketserver
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

from all2md.api import from_ast, to_ast
from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.converter_registry import registry
from all2md.options.html import HtmlRendererOptions


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
                        style="display: block; width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 4px;">
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


def _scan_directory_for_documents(directory: Path, recursive: bool) -> List[Path]:
    """Scan directory for supported document files.

    Parameters
    ----------
    directory : Path
        Directory to scan
    recursive : bool
        Whether to scan subdirectories recursively

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


def _generate_directory_index(
    files: List[Path], directory_name: str, theme_path: Path, base_dir: Path, enable_upload: bool = False
) -> str:
    """Generate HTML index page for directory listing.

    Parameters
    ----------
    files : list[Path]
        List of file paths to include in index
    directory_name : str
        Name of the directory being served
    theme_path : Path
        Path to the theme template file
    base_dir : Path
        Base directory path for computing relative paths
    enable_upload : bool
        Whether to show link to upload page

    Returns
    -------
    str
        HTML content for the index page

    """
    # Read theme template
    theme_content = theme_path.read_text(encoding="utf-8")

    # Group files by directory
    files_by_dir: Dict[str, List[Path]] = {}
    for file in files:
        rel_path = file.relative_to(base_dir)
        parent = str(rel_path.parent) if rel_path.parent != Path(".") else ""
        if parent not in files_by_dir:
            files_by_dir[parent] = []
        files_by_dir[parent].append(file)

    # Generate file list HTML with directory structure
    file_list_html = "<div style='font-family: monospace;'>"

    # Sort directories (root first, then alphabetically)
    sorted_dirs = sorted(files_by_dir.keys(), key=lambda d: ("" if d == "" else "z" + d))

    for dir_path in sorted_dirs:
        dir_files = files_by_dir[dir_path]

        # Show directory header if not root
        if dir_path:
            file_list_html += "<div style='margin-top: 20px; margin-bottom: 10px;'>"
            file_list_html += f"<strong style='font-size: 1.1em;'>{dir_path}/</strong>"
            file_list_html += "</div>"

        # List files in this directory
        file_list_html += "<ul style='list-style: none; padding-left: 20px;'>"
        for file in sorted(dir_files, key=lambda f: f.name.lower()):
            rel_path = file.relative_to(base_dir)
            url = quote(str(rel_path).replace("\\", "/"))
            file_size = file.stat().st_size
            size_str = _format_file_size(file_size)
            file_list_html += "<li style='margin: 5px 0;'>"
            file_list_html += f"<a href='/{url}' style='text-decoration: none; font-size: 1.0em;'>{file.name}</a>"
            file_list_html += f" <span style='color: #888; font-size: 0.9em;'>({size_str})</span>"
            file_list_html += "</li>"
        file_list_html += "</ul>"

    file_list_html += "</div>"

    # Content with file list
    content = f"<h1>Document Directory: {directory_name}</h1>"

    # Add upload link if enabled
    if enable_upload:
        content += """
        <div style="margin: 20px 0; padding: 15px; background: #e8f4f8;
                    border-left: 4px solid #0066cc; border-radius: 4px;">
            <a href="/upload" style="text-decoration: none; color: #0066cc; font-weight: bold;">
                Upload & Convert Document
            </a>
            <span style="margin-left: 10px; color: #666;">- Convert any document to different format</span>
        </div>
        """

    content += f"<p>Found {len(files)} document(s) - click to view:</p>"
    content += file_list_html

    # Apply theme template
    title = f"Directory: {directory_name}"
    html = theme_content.replace("{TITLE}", title)
    html = html.replace("{CONTENT}", content)

    return html


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
    parser = argparse.ArgumentParser(
        prog="all2md serve",
        description="Serve document(s) as HTML via HTTP server with theme support.",
    )
    parser.add_argument("input", help="File or directory to serve")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to serve on (default: 127.0.0.1)")
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively serve subdirectories (for directory input)"
    )
    parser.add_argument("--toc", action="store_true", help="Include table of contents")
    parser.add_argument("--dark", action="store_true", help="Use dark mode theme")
    parser.add_argument(
        "--theme",
        help="Custom theme template path or built-in theme name (minimal, dark, newspaper, docs, sidebar)",
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

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    # Validate input exists
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

    # Determine if input is file or directory
    is_directory = input_path.is_dir()

    # Content cache: maps URL path to HTML content
    content_cache: Dict[str, str] = {}
    # File mapping: maps URL path to actual file path (for lazy loading)
    file_mapping: Dict[str, Path] = {}

    # Setup based on input type
    if is_directory:
        print(f"Preparing directory: {input_path.name}")

        # Scan directory for supported documents
        supported_files = _scan_directory_for_documents(input_path, parsed.recursive)

        if not supported_files:
            print(f"Error: No supported document files found in {input_path}", file=sys.stderr)
            return EXIT_ERROR

        mode_str = "recursively" if parsed.recursive else "in directory"
        print(f"Found {len(supported_files)} document(s) {mode_str} - will convert on demand")

        # Generate directory index page (only pre-cached content)
        index_html = _generate_directory_index(
            supported_files, input_path.name, theme_path, input_path, parsed.enable_upload
        )
        content_cache["/"] = index_html

        # Create file mapping for lazy loading (using relative paths)
        for file in supported_files:
            # Get relative path from base directory
            rel_path = file.relative_to(input_path)
            # Convert to URL path (using forward slashes)
            url_path = "/" + quote(str(rel_path).replace("\\", "/"))
            file_mapping[url_path] = file
    else:
        print(f"Converting {input_path.name}...")
        try:
            doc = to_ast(str(input_path), attachment_mode="base64")
            doc.metadata["title"] = f"{input_path.name} - all2md"

            html_opts = HtmlRendererOptions(
                template_mode="replace",
                template_file=str(theme_path),
                include_toc=parsed.toc,
            )
            html_content = from_ast(doc, "html", renderer_options=html_opts)

            if not isinstance(html_content, str):
                raise RuntimeError("Expected string result from HTML rendering")

            content_cache["/"] = html_content
        except Exception as e:
            print(f"Error: Could not convert {input_path.name}: {e}", file=sys.stderr)
            return EXIT_ERROR

    # Create custom request handler
    class ServeHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            # Remove query string if present
            path = self.path.split("?")[0]

            # Handle upload form route
            if path == "/upload" and parsed.enable_upload:
                upload_form = _generate_upload_form(theme_path)
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(upload_form.encode("utf-8"))
                return

            # Check if already cached (skip cache if --no-cache is enabled)
            if not parsed.no_cache and path in content_cache:
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content_cache[path].encode("utf-8"))
                return

            # Handle directory index regeneration when --no-cache is enabled
            if parsed.no_cache and path == "/" and is_directory:
                # Rescan directory and regenerate index
                supported_files = _scan_directory_for_documents(input_path, parsed.recursive)
                index_html = _generate_directory_index(
                    supported_files, input_path.name, theme_path, input_path, parsed.enable_upload
                )
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(index_html.encode("utf-8"))
                return

            # Handle single file re-conversion when --no-cache is enabled
            if parsed.no_cache and path == "/" and not is_directory:
                try:
                    doc = to_ast(str(input_path), attachment_mode="base64")
                    doc.metadata["title"] = f"{input_path.name} - all2md"
                    html_opts = HtmlRendererOptions(
                        template_mode="replace",
                        template_file=str(theme_path),
                        include_toc=parsed.toc,
                    )
                    html_content = from_ast(doc, "html", renderer_options=html_opts)
                    if not isinstance(html_content, str):
                        raise RuntimeError("Expected string result from HTML rendering")
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html_content.encode("utf-8"))
                    return
                except Exception as e:
                    print(f"Error: Could not convert {input_path.name}: {e}", file=sys.stderr)
                    self.send_response(500)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    error_html = f"<html><body><h1>Error</h1><p>{e}</p></body></html>"
                    self.wfile.write(error_html.encode("utf-8"))
                    return

            # Check if we can lazy-load this file
            if path in file_mapping:
                file_path = file_mapping[path]
                print(f"Converting {file_path.name}...")

                try:
                    # Convert document on demand
                    doc = to_ast(str(file_path), attachment_mode="base64")
                    doc.metadata["title"] = f"{file_path.name} - all2md"

                    html_opts = HtmlRendererOptions(
                        template_mode="replace",
                        template_file=str(theme_path),
                        include_toc=parsed.toc,
                    )
                    html_content = from_ast(doc, "html", renderer_options=html_opts)

                    if not isinstance(html_content, str):
                        raise RuntimeError("Expected string result from HTML rendering")

                    # Cache for future requests (unless --no-cache is enabled)
                    if not parsed.no_cache:
                        content_cache[path] = html_content

                    # Serve the converted content
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html_content.encode("utf-8"))
                    return

                except Exception as e:
                    # Conversion error - send 500
                    print(f"Error converting {file_path.name}: {e}", file=sys.stderr)
                    self.send_response(500)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    error_html = (
                        f"<html><body><h1>500 Internal Server Error</h1>"
                        f"<p>Error converting document: {e}</p></body></html>"
                    )
                    self.wfile.write(error_html.encode("utf-8"))
                    return

            # Not found
            self.send_response(404)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            error_html = "<html><body><h1>404 Not Found</h1><p>The requested document was not found.</p></body></html>"
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

    # Start server
    try:
        with socketserver.TCPServer((parsed.host, parsed.port), ServeHandler) as httpd:
            url = f"http://{parsed.host}:{parsed.port}/"
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

            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\nShutting down server...")
                return EXIT_SUCCESS

            # If serve_forever exits normally (shouldn't happen), exit successfully
            return EXIT_SUCCESS
    except OSError as e:
        if e.errno == 98 or "Address already in use" in str(e):
            print(f"Error: Port {parsed.port} is already in use", file=sys.stderr)
        else:
            print(f"Error: Could not start server: {e}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
