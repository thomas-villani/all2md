"""End-to-end tests for ``all2md view`` on a folder: the local server, its listing and pages."""

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestViewFolderCLIEndToEnd:
    """``view`` on a folder, through a real server process."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.cli_path = Path(__file__).parent.parent.parent / "src" / "all2md" / "cli.py"
        self.server_process = None

    def teardown_method(self):
        """Clean up test environment."""
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait()  # Wait for kill to complete
            # Give the OS time to release the port
            time.sleep(0.2)
        cleanup_test_dir(self.temp_dir)

    def _start_server(self, args: list[str], wait_for_start: bool = True) -> subprocess.Popen:
        """Start ``all2md view`` in a subprocess, with no browser and no config file.

        Parameters
        ----------
        args : list[str]
            Command line arguments to pass to the CLI
        wait_for_start : bool
            If True, wait for server to start accepting connections

        Returns
        -------
        subprocess.Popen
            The server process

        """
        cmd = [sys.executable, "-m", "all2md", *args, "--no-config"]

        self.server_process = subprocess.Popen(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "ALL2MD_TEST_NO_BROWSER": "1"},
        )

        if wait_for_start:
            # Wait for server to start (check if port is ready)
            port = 8000
            for arg_idx, arg in enumerate(args):
                if arg == "--port" and arg_idx + 1 < len(args):
                    port = int(args[arg_idx + 1])
                    break

            max_retries = 20
            for _ in range(max_retries):
                # Check if our process is still running
                if self.server_process.poll() is not None:
                    stdout, stderr = self.server_process.communicate()
                    raise RuntimeError(f"Server failed to start: {stderr}")

                try:
                    urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                    # Successfully connected - verify our process is still alive
                    if self.server_process.poll() is None:
                        break  # Server is running and responding
                    else:
                        # Process died but something responded - likely old server
                        stdout, stderr = self.server_process.communicate()
                        raise RuntimeError(
                            f"Server process died but port {port} still responding (likely leftover server): {stderr}"
                        )
                except (URLError, OSError):
                    time.sleep(0.1)
            else:
                # Server didn't start in time
                if self.server_process.poll() is not None:
                    stdout, stderr = self.server_process.communicate()
                    raise RuntimeError(f"Server failed to start: {stderr}")
                else:
                    raise RuntimeError(f"Server didn't respond on port {port} within timeout")

        return self.server_process

    def _fetch_url(self, url: str, timeout: int = 5) -> bytes:
        """Fetch content from URL.

        Parameters
        ----------
        url : str
            URL to fetch
        timeout : int
            Request timeout in seconds

        Returns
        -------
        bytes
            Response content

        """
        with urlopen(url, timeout=timeout) as response:
            return response.read()

    def _create_test_markdown(self, filename: str = "test.md", content: str | None = None) -> Path:
        """Create a test Markdown file.

        Parameters
        ----------
        filename : str
            Name of the file to create
        content : str, optional
            Content for the file. If None, default test content is used.

        Returns
        -------
        Path
            Path to the created file

        """
        if content is None:
            content = """# Test Document

This is a test document for the folder view.

## Features

- **Bold text**
- *Italic text*
- `Code snippets`

### Code Block

```python
def hello():
    return "Hello, World!"
```
"""
        md_file = self.temp_dir / filename
        md_file.write_text(content, encoding="utf-8")
        return md_file

    def test_view_folder_single_file(self):
        """Test serving a single file."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--port", "8001"])

        # Fetch the content
        content = self._fetch_url("http://127.0.0.1:8001/test.md")
        html = content.decode("utf-8")

        assert "Test Document" in html
        assert "Features" in html
        assert "hello" in html

    def test_view_folder_markdown_does_not_warn_about_attachment_mode(self):
        """The server forces base64 attachments; markdown has none, and that must not warn."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--port", "8034"])
        assert "Test Document" in self._fetch_url("http://127.0.0.1:8034/test.md").decode("utf-8")

        self.server_process.terminate()
        _, stderr = self.server_process.communicate(timeout=5)
        self.server_process = None

        assert "were ignored" not in stderr

    def test_view_folder_lists_every_document_and_embeds_its_images(self):
        """``view DIR`` serves the generated listing even beside a README, and the folder's images."""
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000d49444154789c63f8cfc0f01f0005000201c2a6a9a60000000049454e44ae426082"
        )
        docs = self.temp_dir / "docs"
        (docs / "img").mkdir(parents=True)
        (docs / "img" / "in.png").write_bytes(png)
        (self.temp_dir / "out.png").write_bytes(png)
        (docs / "README.md").write_text("# Only a few documents\n", encoding="utf-8")
        (docs / "a.md").write_text("# A\n\n![in](img/in.png)\n\n![out](../out.png)\n", encoding="utf-8")

        self._start_server(["view", str(docs), "--port", "8035"])
        index = self._fetch_url("http://127.0.0.1:8035/").decode("utf-8")
        assert "href='/a.md'" in index and "href='/README.md'" in index
        page = self._fetch_url("http://127.0.0.1:8035/a.md").decode("utf-8")
        assert 'src="data:image/png;base64,' in page
        assert 'src="../out.png"' in page

    def test_view_folder_directory(self):
        """Test serving a directory with multiple files."""
        # Create multiple markdown files
        self._create_test_markdown("file1.md", "# File 1\n\nThis is file 1.")
        self._create_test_markdown("file2.md", "# File 2\n\nThis is file 2.")
        self._create_test_markdown("file3.md", "# File 3\n\nThis is file 3.")

        self._start_server(["view", str(self.temp_dir), "--port", "8002"])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8002/")
        html = content.decode("utf-8")

        # Should show directory listing
        assert "Document Directory" in html or "file1.md" in html
        assert "file2.md" in html
        assert "file3.md" in html

    def test_view_folder_directory_file_access(self):
        """Test accessing individual files in a served directory."""
        self._create_test_markdown("test.md", "# Test File\n\nContent here.")

        self._start_server(["view", str(self.temp_dir), "--port", "8003"])

        # Fetch specific file
        content = self._fetch_url("http://127.0.0.1:8003/test.md")
        html = content.decode("utf-8")

        assert "Test File" in html
        assert "Content here" in html

    def _serve_one_document(self, port: int, content: str) -> tuple[Path, str]:
        """Serve a folder holding one document, fetch it once so it is cached, return its path and URL."""
        document = self.temp_dir / "doc.md"
        document.write_text(content, encoding="utf-8")
        # The tests fetch straight after each change: the page must not wait for the poller.
        self._start_server(["view", str(self.temp_dir), "--port", str(port)])
        url = f"http://127.0.0.1:{port}/doc.md"
        assert content.encode("utf-8") in self._fetch_url(url)
        return document, url

    def test_view_folder_shows_an_edit_on_the_next_refresh(self):
        """An edited document is converted again, immediately."""
        document, url = self._serve_one_document(8147, "first version")

        document.write_text("second version, longer", encoding="utf-8")

        page = self._fetch_url(url)
        assert b"second version, longer" in page
        assert b"first version" not in page

    def test_view_folder_notices_an_edit_that_keeps_the_size(self):
        """The modification time counts too, for an edit of the same length."""
        document, url = self._serve_one_document(8148, "first version")
        before = document.stat()

        document.write_text("other version", encoding="utf-8")
        os.utime(document, ns=(before.st_atime_ns, before.st_mtime_ns + 5_000_000_000))

        assert b"other version" in self._fetch_url(url)

    def test_view_folder_reuses_the_page_of_an_unchanged_document(self):
        """With size and time unchanged the cached page is served, so caching still works."""
        document, url = self._serve_one_document(8149, "first version")
        before = document.stat()

        document.write_text("other version", encoding="utf-8")
        os.utime(document, ns=(before.st_atime_ns, before.st_mtime_ns))

        assert b"first version" in self._fetch_url(url)

    def test_view_folder_gives_404_for_a_document_just_deleted(self):
        """A deleted document stops being served at once, not at the next poll."""
        document, url = self._serve_one_document(8150, "first version")

        document.unlink()

        with pytest.raises(HTTPError) as error:
            self._fetch_url(url)
        assert error.value.code == 404

    def test_view_folder_injects_web_assets(self):
        """Served documents include the mermaid + highlight.js CDN includes."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--port", "8031"])

        html = self._fetch_url("http://127.0.0.1:8031/test.md").decode("utf-8")
        assert "mermaid@11" in html
        assert "highlight.min.js" in html
        # highlight.js hooks the language class the renderer already emits.
        assert "language-python" in html

    def test_view_folder_no_mermaid_no_highlight_flags(self):
        """The --no-* flags suppress the injected assets."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--no-mermaid", "--no-syntax-highlight", "--port", "8032"])

        html = self._fetch_url("http://127.0.0.1:8032/test.md").decode("utf-8")
        assert "mermaid@11" not in html
        assert "highlight.min.js" not in html

    def test_view_folder_directory_uses_table_and_cards(self):
        """The auto-generated directory index is a toggleable table/card listing."""
        self._create_test_markdown("file1.md", "# File 1")
        self._create_test_markdown("file2.md", "# File 2")

        self._start_server(["view", str(self.temp_dir), "--port", "8033"])

        html = self._fetch_url("http://127.0.0.1:8033/").decode("utf-8")
        assert "file-table" in html
        assert "file-cards" in html
        assert "a2m-view-btn" in html

    def test_view_folder_with_custom_port(self):
        """Test serving on a custom port."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--port", "8888"])

        # Fetch on custom port
        content = self._fetch_url("http://127.0.0.1:8888/test.md")
        html = content.decode("utf-8")

        assert "Test Document" in html

    def test_view_folder_with_dark_theme(self):
        """Test serving with dark theme."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--dark", "--port", "8004"])

        content = self._fetch_url("http://127.0.0.1:8004/test.md")
        html = content.decode("utf-8")

        assert "Test Document" in html
        # Dark theme should have dark background styles

    def test_view_folder_with_custom_theme(self):
        """Test serving with a custom theme."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--theme", "newspaper", "--port", "8005"])

        content = self._fetch_url("http://127.0.0.1:8005/test.md")
        html = content.decode("utf-8")

        assert "Test Document" in html

    def test_view_folder_with_toc(self):
        """Test serving with table of contents enabled."""
        content = """# Main Title

## Section 1

Content for section 1.

## Section 2

Content for section 2.

### Subsection 2.1

More content.
"""
        self._create_test_markdown(content=content)

        self._start_server(["view", str(self.temp_dir), "--toc", "--port", "8006"])

        html_content = self._fetch_url("http://127.0.0.1:8006/test.md")
        html = html_content.decode("utf-8")

        assert "Main Title" in html

    def test_view_folder_nonexistent_file(self):
        """Test serving a file that doesn't exist."""
        nonexistent = self.temp_dir / "nonexistent.md"

        cmd = [sys.executable, "-m", "all2md", "view", str(nonexistent)]
        result = subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode != 0
        assert "Error" in result.stderr or "not found" in result.stderr.lower()

    def test_view_folder_empty_directory(self):
        """Test serving an empty directory."""
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()

        cmd = [sys.executable, "-m", "all2md", "view", str(empty_dir)]
        result = subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should fail with no supported files
        assert result.returncode != 0

    def test_view_folder_html_file(self):
        """Test serving an HTML file."""
        html_content = """<!DOCTYPE html>
<html>
<head><title>Test HTML</title></head>
<body>
    <h1>HTML Document</h1>
    <p>This is an HTML file being served.</p>
</body>
</html>"""
        html_file = self.temp_dir / "test.html"
        html_file.write_text(html_content, encoding="utf-8")

        self._start_server(["view", str(self.temp_dir), "--port", "8007"])

        content = self._fetch_url("http://127.0.0.1:8007/test.html")
        html = content.decode("utf-8")

        assert "HTML Document" in html

    def test_view_folder_404_error(self):
        """Test that requesting non-existent path returns 404."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--port", "8008"])

        # Try to fetch a non-existent path
        try:
            self._fetch_url("http://127.0.0.1:8008/nonexistent")
            raise AssertionError("Should have raised URLError for 404")
        except URLError as e:
            # Expected 404 error
            assert "404" in str(e) or hasattr(e, "code") and e.code == 404

    def test_view_folder_with_unicode_content(self):
        """Test serving markdown with unicode characters."""
        unicode_content = """# Unicode Test Document

## International Characters

- Chinese: \U00004e2d\U00006587
- Russian: \U00000420\U0000043e\U00000441\U00000441\U00000438\U00000439\U00000441\U0000043a\U00000438\U00000439
"""
        self._create_test_markdown(content=unicode_content)

        self._start_server(["view", str(self.temp_dir), "--port", "8009"])

        content = self._fetch_url("http://127.0.0.1:8009/test.md")
        html = content.decode("utf-8")

        assert "Unicode Test Document" in html

    def test_view_folder_directory_non_recursive(self):
        """Test serving directory without recursive flag (default behavior)."""
        # Create nested directory structure
        subdir1 = self.temp_dir / "subdir1"
        subdir1.mkdir()

        # Create files in root and subdirectory
        (self.temp_dir / "root.md").write_text("# Root File", encoding="utf-8")
        (subdir1 / "sub1.md").write_text("# Subdir1 File", encoding="utf-8")

        # Serve without --recursive flag
        self._start_server(["view", str(self.temp_dir), "--port", "8010"])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8010/")
        html = content.decode("utf-8")

        # Should only show root files, not subdirectory files
        assert "root.md" in html
        # Should NOT show subdirectory files
        assert "sub1.md" not in html

    def test_view_folder_recursive_subdirectories(self):
        """Test serving directory with --recursive flag."""
        # Create nested directory structure
        subdir1 = self.temp_dir / "subdir1"
        subdir2 = self.temp_dir / "subdir2"
        nested = subdir1 / "nested"

        subdir1.mkdir()
        subdir2.mkdir()
        nested.mkdir(parents=True)

        # Create files in different locations
        (self.temp_dir / "root.md").write_text("# Root File", encoding="utf-8")
        (subdir1 / "sub1.md").write_text("# Subdir1 File", encoding="utf-8")
        (subdir2 / "sub2.md").write_text("# Subdir2 File", encoding="utf-8")
        (nested / "nested.md").write_text("# Nested File", encoding="utf-8")

        # Serve WITH --recursive flag
        self._start_server(["view", str(self.temp_dir), "--recursive", "--port", "8011"])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8011/")
        html = content.decode("utf-8")

        # Root index should show root files and immediate subdirectories
        assert "root.md" in html
        assert "subdir1" in html
        assert "subdir2" in html

        # Subdirectory index should show its files and nested subdirectories
        content = self._fetch_url("http://127.0.0.1:8011/subdir1/")
        html = content.decode("utf-8")
        assert "sub1.md" in html
        assert "nested" in html

        # Test accessing file in subdirectory
        content = self._fetch_url("http://127.0.0.1:8011/subdir1/sub1.md")
        html = content.decode("utf-8")
        assert "Subdir1 File" in html

        # Test accessing file in nested subdirectory
        content = self._fetch_url("http://127.0.0.1:8011/subdir1/nested/nested.md")
        html = content.decode("utf-8")
        assert "Nested File" in html

    @pytest.mark.parametrize("path", ["upload", "api/convert"])
    def test_view_folder_has_no_upload_form_or_api(self, path):
        """The upload form and the REST API were removed in 1.18 and stay gone."""
        self._create_test_markdown()

        self._start_server(["view", str(self.temp_dir), "--port", "8013"])

        with pytest.raises(HTTPError) as error:
            self._fetch_url(f"http://127.0.0.1:8013/{path}")
        assert error.value.code == 404
