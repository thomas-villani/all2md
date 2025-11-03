"""End-to-end tests for all2md serve CLI command.

This module tests the serve command functionality, including HTTP server setup,
directory/file serving, theme support, and proper shutdown.
"""

import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from utils import cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
class TestServeCLIEndToEnd:
    """End-to-end tests for serve CLI command."""

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
        """Start the serve command in a subprocess.

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
        cmd = [sys.executable, "-m", "all2md"] + args

        self.server_process = subprocess.Popen(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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

This is a test document for the serve command.

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

    def test_serve_single_file(self):
        """Test serving a single file."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file)])

        # Fetch the content
        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        assert "Test Document" in html
        assert "Features" in html
        assert "hello" in html

    def test_serve_directory(self):
        """Test serving a directory with multiple files."""
        # Create multiple markdown files
        self._create_test_markdown("file1.md", "# File 1\n\nThis is file 1.")
        self._create_test_markdown("file2.md", "# File 2\n\nThis is file 2.")
        self._create_test_markdown("file3.md", "# File 3\n\nThis is file 3.")

        self._start_server(["serve", str(self.temp_dir)])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        # Should show directory listing
        assert "Document Directory" in html or "file1.md" in html
        assert "file2.md" in html
        assert "file3.md" in html

    def test_serve_directory_file_access(self):
        """Test accessing individual files in a served directory."""
        self._create_test_markdown("test.md", "# Test File\n\nContent here.")

        self._start_server(["serve", str(self.temp_dir)])

        # Fetch specific file
        content = self._fetch_url("http://127.0.0.1:8000/test.md")
        html = content.decode("utf-8")

        assert "Test File" in html
        assert "Content here" in html

    def test_serve_with_custom_port(self):
        """Test serving on a custom port."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file), "--port", "8888"])

        # Fetch on custom port
        content = self._fetch_url("http://127.0.0.1:8888/")
        html = content.decode("utf-8")

        assert "Test Document" in html

    def test_serve_with_dark_theme(self):
        """Test serving with dark theme."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file), "--dark"])

        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        assert "Test Document" in html
        # Dark theme should have dark background styles

    def test_serve_with_custom_theme(self):
        """Test serving with a custom theme."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file), "--theme", "newspaper"])

        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        assert "Test Document" in html

    def test_serve_with_toc(self):
        """Test serving with table of contents enabled."""
        content = """# Main Title

## Section 1

Content for section 1.

## Section 2

Content for section 2.

### Subsection 2.1

More content.
"""
        md_file = self._create_test_markdown(content=content)

        self._start_server(["serve", str(md_file), "--toc"])

        html_content = self._fetch_url("http://127.0.0.1:8000/")
        html = html_content.decode("utf-8")

        assert "Main Title" in html

    def test_serve_nonexistent_file(self):
        """Test serving a file that doesn't exist."""
        nonexistent = self.temp_dir / "nonexistent.md"

        cmd = [sys.executable, "-m", "all2md", "serve", str(nonexistent)]
        result = subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode != 0
        assert "Error" in result.stderr or "not found" in result.stderr.lower()

    def test_serve_empty_directory(self):
        """Test serving an empty directory."""
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()

        cmd = [sys.executable, "-m", "all2md", "serve", str(empty_dir)]
        result = subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should fail with no supported files
        assert result.returncode != 0

    def test_serve_html_file(self):
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

        self._start_server(["serve", str(html_file)])

        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        assert "HTML Document" in html

    def test_serve_404_error(self):
        """Test that requesting non-existent path returns 404."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file)])

        # Try to fetch a non-existent path
        try:
            self._fetch_url("http://127.0.0.1:8000/nonexistent")
            raise AssertionError("Should have raised URLError for 404")
        except URLError as e:
            # Expected 404 error
            assert "404" in str(e) or hasattr(e, "code") and e.code == 404

    def test_serve_help_message(self):
        """Test that serve --help displays usage information."""
        cmd = [sys.executable, "-m", "all2md", "serve", "--help"]
        result = subprocess.run(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout
        assert "serve" in result.stdout
        assert "--port" in result.stdout
        assert "--theme" in result.stdout

    def test_serve_with_unicode_content(self):
        """Test serving markdown with unicode characters."""
        unicode_content = """# Unicode Test Document

## International Characters

- Chinese: \U00004e2d\U00006587
- Russian: \U00000420\U0000043e\U00000441\U00000441\U00000438\U00000439\U00000441\U0000043a\U00000438\U00000439
"""
        md_file = self._create_test_markdown(content=unicode_content)

        self._start_server(["serve", str(md_file)])

        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        assert "Unicode Test Document" in html

    def test_serve_directory_non_recursive(self):
        """Test serving directory without recursive flag (default behavior)."""
        # Create nested directory structure
        subdir1 = self.temp_dir / "subdir1"
        subdir1.mkdir()

        # Create files in root and subdirectory
        (self.temp_dir / "root.md").write_text("# Root File", encoding="utf-8")
        (subdir1 / "sub1.md").write_text("# Subdir1 File", encoding="utf-8")

        # Serve without --recursive flag
        self._start_server(["serve", str(self.temp_dir)])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        # Should only show root files, not subdirectory files
        assert "root.md" in html
        # Should NOT show subdirectory files
        assert "sub1.md" not in html

    def test_serve_recursive_subdirectories(self):
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
        self._start_server(["serve", str(self.temp_dir), "--recursive"])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        # Should show all files including subdirectories
        assert "root.md" in html
        assert "sub1.md" in html or "subdir1" in html
        assert "sub2.md" in html or "subdir2" in html
        assert "nested.md" in html or "nested" in html

        # Test accessing file in subdirectory
        content = self._fetch_url("http://127.0.0.1:8000/subdir1/sub1.md")
        html = content.decode("utf-8")
        assert "Subdir1 File" in html

        # Test accessing file in nested subdirectory
        content = self._fetch_url("http://127.0.0.1:8000/subdir1/nested/nested.md")
        html = content.decode("utf-8")
        assert "Nested File" in html

    def test_serve_upload_form_enabled(self):
        """Test that upload form is accessible when enabled."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file), "--enable-upload"])

        # Fetch the upload page
        content = self._fetch_url("http://127.0.0.1:8000/upload")
        html = content.decode("utf-8")

        # Should show upload form
        assert "Document Converter" in html
        assert "multipart/form-data" in html
        assert "file" in html
        assert "format" in html

    def test_serve_upload_form_disabled_by_default(self):
        """Test that upload form is not accessible by default."""
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file)])

        # Try to access upload page - should get 404
        try:
            self._fetch_url("http://127.0.0.1:8000/upload")
            raise AssertionError("Upload page should not be accessible without --enable-upload")
        except Exception:
            # Expected - either 404 or connection error
            pass

    def test_serve_upload_link_in_index(self):
        """Test that upload link appears in directory index when enabled."""
        # Create a directory with files
        self._create_test_markdown("file1.md", "# File 1")

        self._start_server(["serve", str(self.temp_dir), "--enable-upload"])

        # Fetch the index page
        content = self._fetch_url("http://127.0.0.1:8000/")
        html = content.decode("utf-8")

        # Should show upload link
        assert "/upload" in html
        assert "Upload" in html or "upload" in html

    def test_serve_development_warning(self):
        """Test that development warning is printed when upload/API enabled."""
        md_file = self._create_test_markdown()

        cmd = [sys.executable, "-u", "-m", "all2md", "serve", str(md_file), "--enable-upload", "--enable-api"]

        # Start server but don't wait for it to fully start
        process = subprocess.Popen(
            cmd,
            cwd=self.cli_path.parent.parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it a moment to print startup messages
        time.sleep(3)

        # Kill the process
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)

        # Check for warning message
        combined_output = stdout + stderr
        assert "WARNING" in combined_output or "warning" in combined_output.lower()
        assert "DEVELOPMENT" in combined_output or "development" in combined_output.lower()

    def test_serve_no_cache_single_file(self):
        """Test that --no-cache causes file to be re-converted on each request."""
        # Create a markdown file
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file), "--no-cache"])

        # Fetch the content twice
        content1 = self._fetch_url("http://127.0.0.1:8000/")
        html1 = content1.decode("utf-8")

        content2 = self._fetch_url("http://127.0.0.1:8000/")
        html2 = content2.decode("utf-8")

        # Both should contain the same content (file unchanged)
        assert "Test Document" in html1
        assert "Test Document" in html2

        # Modify the file
        md_file.write_text("# Updated Content\n\nThis has changed!", encoding="utf-8")

        # Fetch again - should show new content due to --no-cache
        content3 = self._fetch_url("http://127.0.0.1:8000/")
        html3 = content3.decode("utf-8")

        assert "Updated Content" in html3
        assert "This has changed!" in html3

    def test_serve_with_cache_single_file(self):
        """Test that without --no-cache, file is cached and not re-converted."""
        # Create a markdown file
        md_file = self._create_test_markdown()

        self._start_server(["serve", str(md_file)])

        # Fetch the content once to populate cache
        content1 = self._fetch_url("http://127.0.0.1:8000/")
        html1 = content1.decode("utf-8")

        assert "Test Document" in html1

        # Modify the file
        md_file.write_text("# Updated Content\n\nThis has changed!", encoding="utf-8")

        # Fetch again - should still show old content due to cache
        content2 = self._fetch_url("http://127.0.0.1:8000/")
        html2 = content2.decode("utf-8")

        assert "Test Document" in html2
        assert "Updated Content" not in html2

    def test_serve_no_cache_directory(self):
        """Test that --no-cache re-scans directory on each request."""
        # Create initial files
        self._create_test_markdown("file1.md", "# File 1")

        self._start_server(["serve", str(self.temp_dir), "--no-cache"])

        # Fetch the index
        content1 = self._fetch_url("http://127.0.0.1:8000/")
        html1 = content1.decode("utf-8")

        assert "file1.md" in html1

        # Add another file
        self._create_test_markdown("file2.md", "# File 2")

        # Fetch again - should show new file due to --no-cache
        content2 = self._fetch_url("http://127.0.0.1:8000/")
        html2 = content2.decode("utf-8")

        assert "file1.md" in html2
        assert "file2.md" in html2

    def test_serve_no_cache_file_in_directory(self):
        """Test that --no-cache re-converts files in directory on each request."""
        # Create a file
        md_file = self._create_test_markdown("test.md", "# Original Content")

        self._start_server(["serve", str(self.temp_dir), "--no-cache"])

        # Fetch the file
        content1 = self._fetch_url("http://127.0.0.1:8000/test.md")
        html1 = content1.decode("utf-8")

        assert "Original Content" in html1

        # Modify the file
        md_file.write_text("# Modified Content", encoding="utf-8")

        # Fetch again - should show new content due to --no-cache
        content2 = self._fetch_url("http://127.0.0.1:8000/test.md")
        html2 = content2.decode("utf-8")

        assert "Modified Content" in html2
        assert "Original Content" not in html2
