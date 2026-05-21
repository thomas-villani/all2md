"""End-to-end tests for the all2md edit CLI command."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.e2e
@pytest.mark.cli
class TestEditCLIEndToEnd:
    """End-to-end tests for edit CLI command."""

    def setup_method(self) -> None:
        self.process: subprocess.Popen | None = None

    def teardown_method(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            time.sleep(0.1)

    def _start(self, file_path: Path, port: int) -> str:
        cmd = [
            sys.executable,
            "-m",
            "all2md",
            "edit",
            str(file_path),
            "--no-browser",
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
        ]
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        url = f"http://127.0.0.1:{port}/"
        for _ in range(40):
            if self.process.poll() is not None:
                _, err = self.process.communicate()
                raise RuntimeError(f"edit server failed to start: {err}")
            try:
                with urlopen(url, timeout=1):
                    return url
            except (URLError, OSError):
                time.sleep(0.1)
        raise RuntimeError("edit server did not become ready")

    def _post_json(self, url: str, payload: dict) -> tuple[int, dict]:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_index_page_embeds_markdown(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# Hello edit\n\nA tiny doc.\n", encoding="utf-8")
        port = _free_port()

        base = self._start(md, port)
        with urlopen(base, timeout=5) as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")

        assert "/assets/toastui-editor-all.min.js" in body
        assert "/assets/toastui-editor.min.css" in body
        # The initial markdown is embedded inside the JSON state script tag.
        assert "Hello edit" in body

    def test_assets_served(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# x\n", encoding="utf-8")
        port = _free_port()
        base = self._start(md, port)

        with urlopen(base + "assets/toastui-editor.min.css", timeout=5) as resp:
            assert resp.status == 200
            assert "text/css" in resp.headers.get("Content-type", "")
            assert len(resp.read()) > 1000

    def test_unknown_asset_returns_404(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# x\n", encoding="utf-8")
        port = _free_port()
        base = self._start(md, port)

        try:
            urlopen(base + "assets/etc-passwd", timeout=5)
            pytest.fail("expected 404")
        except HTTPError as e:
            assert e.code == 404

    def test_save_writes_new_file(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# original\n", encoding="utf-8")
        out = tmp_path / "edited.md"
        port = _free_port()
        base = self._start(md, port)

        status, body = self._post_json(
            base + "api/save",
            {
                "content": "# edited\n\nnew body\n",
                "target_format": "markdown",
                "target_path": str(out),
                "overwrite": False,
            },
        )
        assert status == 200, body
        assert body["ok"] is True
        assert body["backup"] is None
        assert out.exists()
        assert "edited" in out.read_text(encoding="utf-8")

    def test_save_existing_without_overwrite_is_409(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# original\n", encoding="utf-8")
        existing = tmp_path / "existing.md"
        existing.write_text("# old\n", encoding="utf-8")
        port = _free_port()
        base = self._start(md, port)

        status, body = self._post_json(
            base + "api/save",
            {
                "content": "# new\n",
                "target_format": "markdown",
                "target_path": str(existing),
                "overwrite": False,
            },
        )
        assert status == 409
        assert body["ok"] is False
        assert existing.read_text(encoding="utf-8") == "# old\n"

    def test_save_with_overwrite_creates_backup(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# original\n", encoding="utf-8")
        port = _free_port()
        base = self._start(md, port)

        status, body = self._post_json(
            base + "api/save",
            {
                "content": "# rewritten\n",
                "target_format": "markdown",
                "target_path": str(md),
                "overwrite": True,
            },
        )
        assert status == 200, body
        assert body["ok"] is True
        assert body["backup"] is not None
        backup = Path(body["backup"])
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "# original\n"
        assert "rewritten" in md.read_text(encoding="utf-8")

    def test_unknown_format_rejected(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# x\n", encoding="utf-8")
        out = tmp_path / "out.bogus"
        port = _free_port()
        base = self._start(md, port)

        status, body = self._post_json(
            base + "api/save",
            {
                "content": "# x\n",
                "target_format": "bogus-format",
                "target_path": str(out),
                "overwrite": False,
            },
        )
        assert status == 400
        assert body["ok"] is False
        assert not out.exists()

    def test_save_relative_traversal_rejected(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# original\n", encoding="utf-8")
        escaped = tmp_path.parent / "escape.md"
        port = _free_port()
        base = self._start(md, port)

        status, body = self._post_json(
            base + "api/save",
            {
                "content": "# pwned\n",
                "target_format": "markdown",
                "target_path": "../escape.md",
                "overwrite": True,
            },
        )
        assert status == 403, body
        assert body["ok"] is False
        assert not escaped.exists()

    def test_save_absolute_path_outside_root_rejected(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# original\n", encoding="utf-8")
        outside = tmp_path.parent / "abs-escape.md"
        port = _free_port()
        base = self._start(md, port)

        status, body = self._post_json(
            base + "api/save",
            {
                "content": "# pwned\n",
                "target_format": "markdown",
                "target_path": str(outside),
                "overwrite": True,
            },
        )
        assert status == 403, body
        assert body["ok"] is False
        assert not outside.exists()

    def test_save_requires_json_content_type(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("# original\n", encoding="utf-8")
        out = tmp_path / "csrf.md"
        port = _free_port()
        base = self._start(md, port)

        # Mimic a cross-origin "simple request": a valid JSON body but a
        # text/plain content type, which a browser sends without a CORS
        # preflight. The server must refuse it before writing anything.
        req = Request(
            base + "api/save",
            data=json.dumps(
                {
                    "content": "# pwned\n",
                    "target_format": "markdown",
                    "target_path": str(out),
                    "overwrite": True,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=5) as resp:
                status = resp.status
        except HTTPError as e:
            status = e.code
        assert status == 415
        assert not out.exists()
