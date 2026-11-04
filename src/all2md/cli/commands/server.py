#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""The local HTTP server behind ``all2md view DIR``.

:func:`run_server` serves a folder or a glob's matches as themed HTML, converting each
document on demand, with a listing that follows the folder.
"""

import argparse
import errno
import fnmatch
import http.server
import os
import socketserver
import sys
import threading
import webbrowser
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from all2md.api import from_ast, library_injected_options, to_ast
from all2md.cli import window
from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.cli.commands.shared import has_hidden_component, split_glob_pattern
from all2md.cli.commands.web_assets import ThemeError, inject_web_assets, inline_local_images, resolve_theme
from all2md.cli.config import load_config_with_priority
from all2md.converter_registry import registry
from all2md.options.html import HtmlRendererOptions
from all2md.utils.html_utils import escape_html

# Filenames that can stand in for an auto-generated directory listing,
# in descending priority order.
INDEX_FILE_NAMES: tuple[str, ...] = (
    "index.html",
    "index.htm",
    "index.md",
    "README.md",
    "readme.md",
)


def _scan_directory_for_documents(
    directory: Path,
    recursive: bool,
    pattern: str | None = None,
    include_hidden: bool = False,
) -> list[Path]:
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


def _find_index_file(directory: Path) -> Path | None:
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
    pattern: str | None = None,
    include_hidden: bool = False,
) -> tuple[list[Path], set, dict[str, Path], set]:
    """Scan ``base_dir`` and derive everything the serve loop tracks.

    Returns a tuple of ``(files, known_subdirs, file_mapping, signature)``,
    where ``signature`` is a set of ``(path, size, mtime)`` triples used to
    cheaply detect changes between polls.
    """
    files = _scan_directory_for_documents(base_dir, recursive, pattern, include_hidden)
    subdirs: set = set()
    mapping: dict[str, Path] = {}
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


# Scoped styling + behaviour for the auto-generated directory index. Class-prefixed so
# it overrides a theme's generic table/list rules without leaking into document pages.
_INDEX_STYLE = """<style>
.a2m-toolbar { display: flex; gap: .5rem; margin: 1rem 0; }
.a2m-view-btn { cursor: pointer; padding: .35rem .8rem; border: 1px solid currentColor;
    border-radius: 6px; background: transparent; color: inherit; font: inherit; opacity: .55; }
.a2m-view-btn.active { opacity: 1; font-weight: 600; }
.file-table { width: 100%; border-collapse: collapse; margin: 0; }
.file-table th, .file-table td { text-align: left; padding: .4rem .75rem;
    border-bottom: 1px solid rgba(128,128,128,.25); white-space: nowrap; }
.file-table th { font-weight: 600; }
.file-table td:first-child, .file-table th:first-child { white-space: normal; width: 100%; }
.file-table .num { font-variant-numeric: tabular-nums; }
.file-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: .75rem; }
.file-card { display: block; padding: .75rem 1rem; border: 1px solid rgba(128,128,128,.3);
    border-radius: 8px; text-decoration: none; color: inherit; }
.file-card:hover { border-color: currentColor; }
.file-card-name { font-weight: 600; word-break: break-word; }
.file-card-meta { opacity: .7; font-size: .85em; margin-top: .3rem; }
.a2m-subdirs { list-style: none; padding-left: 0; margin: 1rem 0; }
.a2m-subdirs li { margin: .3rem 0; }
.a2m-listing[data-view="table"] .file-cards { display: none; }
.a2m-listing[data-view="cards"] .file-table { display: none; }
</style>"""

# Toggles the listing between table and card view, remembering the choice per browser.
_INDEX_SCRIPT = """<script>
(function () {
    var root = document.currentScript.parentNode;
    var listing = root.querySelector('.a2m-listing');
    var btns = root.querySelectorAll('.a2m-view-btn');
    var KEY = 'all2md-index-view';
    function apply(v) {
        if (v !== 'cards') { v = 'table'; }
        listing.setAttribute('data-view', v);
        btns.forEach(function (b) { b.classList.toggle('active', b.dataset.view === v); });
        try { localStorage.setItem(KEY, v); } catch (e) {}
    }
    btns.forEach(function (b) { b.addEventListener('click', function () { apply(b.dataset.view); }); });
    var saved = 'table';
    try { saved = localStorage.getItem(KEY) || 'table'; } catch (e) {}
    apply(saved);
})();
</script>"""


def _generate_directory_index(
    all_files: list[Path],
    theme_path: Path,
    base_dir: Path,
    current_subdir: str = "",
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

    Returns
    -------
    str
        HTML content for the index page

    """
    # Read theme template
    theme_content = theme_path.read_text(encoding="utf-8")

    # Filter files to current directory level and find child subdirectories
    current_files: list[Path] = []
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
    content += _INDEX_STYLE
    content += f"<h1>Directory: {escape_html(dir_display)}</h1>"

    # Show subdirectories
    if child_dir_names:
        content += "<ul class='a2m-subdirs'>"
        for dir_name in sorted(child_dir_names):
            if current_subdir:
                dir_url = "/" + "/".join(quote(p) for p in current_subdir.split("/")) + "/" + quote(dir_name) + "/"
            else:
                dir_url = "/" + quote(dir_name) + "/"
            content += f"<li><a href='{dir_url}'>&#128193; {escape_html(dir_name)}/</a></li>"
        content += "</ul>"

    # Show file count. The listing only ever contains files the registry can convert
    # (see _scan_directory_for_documents), so every row here is viewable.
    content += f"<p>Found {len(current_files)} document(s)"
    if child_dir_names:
        content += f" and {len(child_dir_names)} subdirectory(ies)"
    content += ":</p>"

    # List files at this level as an aligned table plus a card grid; a toggle picks
    # which is shown (default table, remembered in localStorage).
    if current_files:
        rows = ""
        cards = ""
        for file in sorted(current_files, key=lambda f: f.name.lower()):
            rel_path = file.relative_to(base_dir)
            url = "/" + quote(str(rel_path).replace("\\", "/"))
            name = escape_html(file.name)
            size_str = "?"
            modified_str = "—"
            created_str = "—"
            try:
                stat_result = file.stat()
                size_str = _format_file_size(stat_result.st_size)
                modified_str = _format_timestamp(stat_result.st_mtime)
                created_ts = _file_created_timestamp(stat_result)
                if created_ts is not None:
                    created_str = _format_timestamp(created_ts)
            except OSError:
                # File vanished or became unreadable between listing and stat;
                # keep the "?"/"—" placeholders rather than dropping the row.
                pass
            rows += (
                f"<tr><td><a href='{url}'>{name}</a></td>"
                f"<td class='num'>{size_str}</td>"
                f"<td class='num'>{modified_str}</td>"
                f"<td class='num'>{created_str}</td></tr>"
            )
            meta = " · ".join(
                part for part in (size_str, f"modified {modified_str}", f"created {created_str}") if "—" not in part
            )
            cards += (
                f"<a class='file-card' href='{url}'>"
                f"<div class='file-card-name'>{name}</div>"
                f"<div class='file-card-meta'>{meta}</div></a>"
            )
        content += "<div class='a2m-toolbar'>"
        content += "<button type='button' class='a2m-view-btn' data-view='table'>Table</button>"
        content += "<button type='button' class='a2m-view-btn' data-view='cards'>Cards</button>"
        content += "</div>"
        content += "<div class='a2m-listing' data-view='table'>"
        content += (
            "<table class='file-table'><thead><tr>"
            "<th>Name</th><th>Size</th><th>Modified</th><th>Created</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )
        content += f"<div class='file-cards'>{cards}</div>"
        content += "</div>"
        content += _INDEX_SCRIPT

    # Apply theme template
    title = f"Directory: {dir_display}"
    html = theme_content.replace("{TITLE}", title)
    html = html.replace("{CONTENT}", content)

    return html


def _file_stamp(path: Path) -> tuple[int, int] | None:
    """Return what identifies this version of a file (size, modified time), or None if it is gone."""
    try:
        stat_result = path.stat()
    except OSError:
        return None
    return stat_result.st_size, stat_result.st_mtime_ns


def _format_timestamp(timestamp: float) -> str:
    """Format an epoch timestamp as a compact local ``YYYY-MM-DD HH:MM`` string."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _file_created_timestamp(stat_result: os.stat_result) -> float | None:
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
) -> tuple["_ThreadingHTTPServer", bool]:
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


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """HTTPServer that handles each request in a daemon thread.

    Daemon threads let the process exit promptly on shutdown even if a
    long-running conversion is still in flight.
    """

    daemon_threads = True
    allow_reuse_address = True


@dataclass
class ServeSettings:
    """What :func:`run_server` serves and how; ``view`` builds one from its flags.

    ``input`` is a directory or a glob pattern. ``index_page`` shows a folder's
    ``index.html``, ``index.md`` or ``README.md`` in place of the generated listing.
    ``browse`` opens the page in a browser tab, ``window`` in a native window, which
    stops the server when it closes.
    """

    input: str
    host: str = "127.0.0.1"
    port: int = 8000
    recursive: bool = False
    include_hidden: bool = False
    index_page: bool = False
    toc: bool = False
    dark: bool = False
    theme: str | None = None
    no_mermaid: bool = False
    no_syntax_highlight: bool = False
    browse: bool = False
    window: bool = False
    poll_interval: float = 2.0
    config: str | None = None
    no_config: bool = False

    @classmethod
    def from_namespace(cls, namespace: argparse.Namespace, **overrides: Any) -> "ServeSettings":
        """Take each field a parsed command line has, then apply ``overrides``."""
        values = {f.name: getattr(namespace, f.name) for f in fields(cls) if hasattr(namespace, f.name)}
        values.update(overrides)
        return cls(**values)


def run_server(settings: ServeSettings) -> int:  # noqa: C901
    """Serve a folder or a glob's matches as themed HTML until stopped.

    Documents convert on demand and are cached until the file changes; a folder's
    listing follows the files on disk. Returns the exit code.
    """
    # Converter options from the config file (e.g. [pdf], [html], top-level keys)
    # so a single config drives `all2md` and `view` identically.
    from all2md.cli.processors import load_converter_config_options, prepare_options_for_execution

    converter_options = load_converter_config_options(explicit_path=settings.config, no_config=settings.no_config)

    # Resolve the input: a glob pattern or a directory.
    # A glob is served as a directory listing restricted to matching files, so
    # live rescans continue to pick up newly added matches.
    serve_pattern: str | None = None
    if any(char in settings.input for char in "*?["):
        input_path, serve_pattern, glob_recursive = split_glob_pattern(settings.input)
        if not input_path.is_dir():
            print(f"Error: No directory to serve for pattern: {settings.input}", file=sys.stderr)
            return EXIT_FILE_ERROR
        if glob_recursive:
            settings.recursive = True
        # Show the filtered listing, not a hand-authored index in the directory.
        settings.index_page = False
    else:
        input_path = Path(settings.input)
        if not input_path.is_dir():
            print(f"Error: Not a folder: {settings.input}", file=sys.stderr)
            return EXIT_FILE_ERROR

    # Select theme template (built-in name, .html/.css path, or [themes] config name).
    theme_config = {} if settings.no_config else load_config_with_priority(explicit_path=settings.config)
    try:
        theme_path = resolve_theme(settings.theme, dark=settings.dark, config=theme_config)
    except ThemeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    if not theme_path.exists():
        print(f"Error: Theme template not found: {theme_path}", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Whether to serve the dark variant of the highlight.js / mermaid themes.
    is_dark = settings.dark or settings.theme == "dark"

    served_root = input_path.resolve()

    # Shared state guarded by state_lock so the polling thread and request
    # handler threads can coexist safely.
    state_lock = threading.Lock()
    file_cache: dict[str, tuple[tuple[int, int], str]] = {}  # URL path -> (file stamp, page)
    index_cache: dict[str, str] = {}
    file_mapping: dict[str, Path] = {}
    supported_files: list[Path] = []
    known_subdirs: set = set()
    scan_signature: set = set()

    def _convert_to_html(file_path: Path, breadcrumb_path: str | None = None) -> str:
        """Convert a single document to themed HTML, optionally injecting breadcrumbs."""
        # Apply config-supplied converter options for the detected format, but
        # force base64 attachments: images must be inlined to render in-browser.
        # Formats without attachments (markdown, plain text) drop the option, and
        # since we added it, not the user, the drop must not warn.
        to_ast_kwargs = prepare_options_for_execution(converter_options, file_path, "auto")
        to_ast_kwargs["attachment_mode"] = "base64"
        with library_injected_options("attachment_mode"):
            doc = to_ast(str(file_path), **to_ast_kwargs)
        # The page lives at a URL, not beside its source, so images named by path are
        # embedded; only ones inside the served folder, which is all a visitor may read.
        inline_local_images(doc, file_path.parent, root=served_root)
        doc.metadata["title"] = f"{file_path.name} - all2md"
        html_opts = HtmlRendererOptions(
            template_mode="replace",
            template_file=str(theme_path),
            include_toc=settings.toc,
            external_links_new_tab=True,
            render_mermaid=not settings.no_mermaid,
        )
        html_content = from_ast(doc, "html", renderer_options=html_opts)
        if not isinstance(html_content, str):
            raise RuntimeError("Expected string result from HTML rendering")
        # Splice in the mermaid / highlight.js CDN includes (graceful offline degrade)
        # before breadcrumbs so the injection targets the original <head>.
        html_content = inject_web_assets(
            html_content,
            mermaid=not settings.no_mermaid,
            highlight=not settings.no_syntax_highlight,
            dark=is_dark,
        )
        if breadcrumb_path:
            breadcrumbs = _generate_breadcrumbs(breadcrumb_path)
            html_content = html_content.replace("<body>", "<body>\n" + breadcrumbs, 1)
        return html_content

    def _rescan_directory(initial: bool = False) -> bool:
        """Rescan the served directory; update state and drop stale caches.

        Returns ``True`` when the file set has actually changed (or on the
        initial scan), ``False`` otherwise.
        """
        new_files, new_subdirs, new_mapping, new_signature = _compute_directory_state(
            input_path, settings.recursive, serve_pattern, settings.include_hidden
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

    print(f"Preparing directory: {input_path.name}")
    _rescan_directory(initial=True)

    # Empty directories are still legitimate if they ship an index.html /
    # index.md / README.md the user wants served.
    if not supported_files and (not settings.index_page or _find_index_file(input_path) is None):
        print(f"Error: No supported document files found in {input_path}", file=sys.stderr)
        return EXIT_ERROR

    mode_str = "recursively" if settings.recursive else "in directory"
    print(f"Found {len(supported_files)} document(s) {mode_str} - will convert on demand")

    def _is_directory_index_path(path: str) -> bool:
        """Return ``True`` when ``path`` addresses a directory listing."""
        if path == "/":
            return True
        subdir = unquote(path.strip("/"))
        with state_lock:
            return subdir in known_subdirs

    def _render_directory_index(path: str) -> str | None:
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

        if settings.index_page:
            index_file = _find_index_file(target_dir)
            if index_file is not None:
                breadcrumb_path: str | None = ("/" + subdir + "/") if subdir else None
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
        )

    # Create custom request handler
    class ServeHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            # Remove query string if present
            path = self.path.split("?")[0]

            # Directory index requests (root or known subdirectory)
            if _is_directory_index_path(path):
                with state_lock:
                    cached = index_cache.get(path)
                if cached is not None:
                    self._send_html(cached)
                    return
                html_content = _render_directory_index(path)
                if html_content is None:
                    self._send_500("Failed to render directory index")
                    return
                with state_lock:
                    index_cache[path] = html_content
                self._send_html(html_content)
                return

            # File request
            with state_lock:
                file_path = file_mapping.get(path)
                cached_file = file_cache.get(path) if file_path else None

            # Checked on every request rather than left to the poller, so a refresh right
            # after saving shows the edit. Taken before converting: a file saved during the
            # conversion then differs from this stamp, and converts again on the next request.
            stamp = _file_stamp(file_path) if file_path else None
            if file_path is None or stamp is None:
                self._send_404()
                return

            if cached_file is not None and cached_file[0] == stamp:
                self._send_html(cached_file[1])
                return

            print(f"Converting {file_path.name}...")
            try:
                html_content = _convert_to_html(file_path, breadcrumb_path=unquote(path))
            except Exception as e:
                print(f"Error converting {file_path.name}: {e}", file=sys.stderr)
                self._send_500(f"Error converting document: {e}")
                return

            with state_lock:
                file_cache[path] = (stamp, html_content)
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

    # Start server. If the requested port is taken, fall back to an OS-assigned
    # random free port instead of giving up (port 8000 is frequently in use).
    try:
        httpd, fell_back = _bind_http_server(settings.host, settings.port, ServeHandler)
    except OSError as e:
        print(f"Error: Could not start server: {e}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    # Use the port we actually bound (differs from --port when we fell back).
    bound_port = httpd.server_address[1]
    if fell_back:
        print(f"Port {settings.port} is unavailable; bound a random free port instead.", file=sys.stderr)

    url = f"http://{settings.host}:{bound_port}/"
    print(f"\nServing at {url}")

    # Use a loopback host for the browser when bound to a wildcard address, which
    # browsers can't navigate to directly.
    # nosec B104: not binding here -- detecting a wildcard bind host so the
    # browser is pointed at a reachable loopback address instead.
    wildcard_hosts = ("0.0.0.0", "::", "")  # nosec B104
    browse_host = "127.0.0.1" if settings.host in wildcard_hosts else settings.host
    browse_url = f"http://{browse_host}:{bound_port}/"

    # A native window needs pywebview; without it, fall back to a browser tab.
    use_window = settings.window and not os.environ.get("ALL2MD_TEST_NO_BROWSER")
    if use_window and not window.is_available():
        print(f"Note: {window.INSTALL_HINT}", file=sys.stderr)
        print("Falling back to a browser tab.", file=sys.stderr)
        use_window = False
    print("Close the window to stop" if use_window else "Press Ctrl+C to stop")

    # Open the served URL in the browser when requested (skipped under test mode,
    # matching `all2md view`).
    if settings.browse and not use_window and not os.environ.get("ALL2MD_TEST_NO_BROWSER"):
        print(f"Opening {browse_url} in browser...")
        try:
            webbrowser.open(browse_url)
        except Exception as e:  # pragma: no cover - browser launch is best-effort
            print(f"Could not open browser: {e}", file=sys.stderr)

    stop_event = threading.Event()

    # Background polling for live directory updates. Skipped when polling is disabled.
    poll_thread: threading.Thread | None = None
    if settings.poll_interval > 0:

        def _poll_loop() -> None:
            while not stop_event.is_set():
                if stop_event.wait(timeout=settings.poll_interval):
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
        # The window blocks until it is closed, which stops the server.
        if use_window:
            window.open_window(browse_url, title=f"{Path(settings.input).name} - all2md")
            stop_event.set()
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
