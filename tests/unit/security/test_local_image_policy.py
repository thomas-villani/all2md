"""Renderers read images from the local disk only when the document's policy allows it.

A Markdown or HTML document is untrusted input. Without a policy, an image path in it
copies files from the converting machine into the output, so local images are off by
default and, when turned on, must still be images, under the size limit and inside any
allowlist.
"""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest

from all2md.ast import Document, Heading, Image, Paragraph, Text
from all2md.options.common import LocalFileAccessOptions
from all2md.utils.security import read_local_image, validate_local_file_access

pytestmark = [pytest.mark.unit, pytest.mark.security]

MARKER = b"LOCAL-IMAGE-POLICY-MARKER"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
ALLOW = LocalFileAccessOptions(allow_local_files=True)


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    """A secret, a text file that starts like a bitmap, an XML file, and a real PNG."""
    paths = {
        "secret": tmp_path / "secret.json",
        "bm_text": tmp_path / "BMnotes.txt",
        "xml": tmp_path / "config.xml",
        "png": tmp_path / "pic.png",
    }
    paths["secret"].write_bytes(b'{"token": "' + MARKER + b'"}')
    paths["bm_text"].write_bytes(b"BM is not a bitmap " + MARKER)
    paths["xml"].write_bytes(b'<?xml version="1.0"?><config><key>' + MARKER + b"</key></config>")
    paths["png"].write_bytes(PNG_1X1 + MARKER)
    return paths


def _contains(data: bytes, needle: bytes) -> bool:
    if needle in data:
        return True
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return any(needle in archive.read(name) for name in archive.namelist())
    return False


def _doc(url: str, source_path: Path | None = None) -> Document:
    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Image(url=url, alt_text="x")]),
            Image(url=url, alt_text="x"),
        ]
    )
    if source_path is not None:
        doc.metadata["source_path"] = str(source_path)
    return doc


def _renderer(fmt: str, local_files: LocalFileAccessOptions | None):
    if fmt == "docx":
        pytest.importorskip("docx")
        from all2md.options.docx import DocxRendererOptions
        from all2md.renderers.docx import DocxRenderer

        opts = DocxRendererOptions() if local_files is None else DocxRendererOptions(local_files=local_files)
        return DocxRenderer(opts)
    if fmt == "odt":
        pytest.importorskip("odf")
        from all2md.options.odt import OdtRendererOptions
        from all2md.renderers.odt import OdtRenderer

        opts = OdtRendererOptions() if local_files is None else OdtRendererOptions(local_files=local_files)
        return OdtRenderer(opts)
    if fmt == "odp":
        pytest.importorskip("odf")
        from all2md.options.odp import OdpRendererOptions
        from all2md.renderers.odp import OdpRenderer

        opts = OdpRendererOptions() if local_files is None else OdpRendererOptions(local_files=local_files)
        return OdpRenderer(opts)
    if fmt == "pptx":
        pytest.importorskip("pptx")
        from all2md.options.pptx import PptxRendererOptions
        from all2md.renderers.pptx import PptxRenderer

        opts = PptxRendererOptions() if local_files is None else PptxRendererOptions(local_files=local_files)
        return PptxRenderer(opts)
    if fmt == "epub":
        pytest.importorskip("ebooklib")
        from all2md.options.epub import EpubRendererOptions
        from all2md.renderers.epub import EpubRenderer

        opts = EpubRendererOptions() if local_files is None else EpubRendererOptions(local_files=local_files)
        return EpubRenderer(opts)
    raise AssertionError(fmt)


ZIP_FORMATS = ["docx", "odt", "odp", "pptx", "epub"]


@pytest.mark.parametrize("fmt", ZIP_FORMATS)
@pytest.mark.parametrize("name", ["secret", "png"])
def test_local_files_are_not_read_by_default(fmt: str, name: str, files: dict[str, Path]) -> None:
    out = _renderer(fmt, None).render_to_bytes(_doc(str(files[name])))
    assert not _contains(out, MARKER)


@pytest.mark.parametrize("fmt", ZIP_FORMATS)
@pytest.mark.parametrize("name", ["secret", "bm_text", "xml"])
def test_non_images_are_never_read_even_when_allowed(fmt: str, name: str, files: dict[str, Path]) -> None:
    out = _renderer(fmt, ALLOW).render_to_bytes(_doc(str(files[name])))
    assert not _contains(out, MARKER)


@pytest.mark.parametrize("fmt", ZIP_FORMATS)
def test_an_allowed_image_is_embedded(fmt: str, files: dict[str, Path]) -> None:
    out = _renderer(fmt, ALLOW).render_to_bytes(_doc(str(files["png"])))
    assert _contains(out, MARKER)


def test_pdf_refuses_local_images_by_default(files: dict[str, Path], caplog: pytest.LogCaptureFixture) -> None:
    pytest.importorskip("reportlab")
    from all2md.options.pdf import PdfRendererOptions
    from all2md.renderers.pdf import PdfRenderer

    PdfRenderer(PdfRendererOptions()).render_to_bytes(_doc(str(files["png"])))
    assert "reading local files is off" in caplog.text
    assert "--pdf-renderer-local-files-allow-local-files" in caplog.text


def test_relative_paths_resolve_against_the_source_document(tmp_path: Path, files: dict[str, Path]) -> None:
    pytest.importorskip("docx")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    doc = _doc("pic.png", source_path=tmp_path / "doc.md")
    policy = LocalFileAccessOptions(allow_local_files=True, local_file_allowlist=[str(tmp_path)])
    out = _renderer("docx", policy).render_to_bytes(doc)
    assert _contains(out, MARKER)


def test_allowlist_confines_reads(tmp_path: Path, files: dict[str, Path]) -> None:
    inside = tmp_path / "inside"
    inside.mkdir()
    policy = LocalFileAccessOptions(allow_local_files=True, local_file_allowlist=[str(inside)])
    assert read_local_image(str(files["png"]), policy) is None
    assert read_local_image("inside/../pic.png", policy, base_dir=tmp_path) is None
    (inside / "ok.png").write_bytes(PNG_1X1)
    image = read_local_image("ok.png", policy, base_dir=inside)
    assert image is not None and image.format == "png"


def test_size_limit_applies(files: dict[str, Path]) -> None:
    assert read_local_image(str(files["png"]), ALLOW, max_bytes=10) is None
    assert read_local_image(str(files["png"]), ALLOW, max_bytes=10_000) is not None


@pytest.mark.parametrize(
    "url",
    [
        "\\\\attacker\\share\\x.png",
        "//attacker/share/x.png",
        "file://attacker/share/x.png",
        "file:////attacker/share/x.png",
        "ftp://example.com/x.png",
        "javascript:alert(1)",
    ],
)
def test_network_paths_and_other_schemes_are_refused(url: str) -> None:
    assert read_local_image(url, ALLOW) is None


def test_svg_needs_an_svg_root(tmp_path: Path) -> None:
    svg = tmp_path / "a.svg"
    svg.write_bytes(b'<?xml version="1.0"?>\n<!-- c --><svg xmlns="http://www.w3.org/2000/svg"/>')
    image = read_local_image(str(svg), ALLOW)
    assert image is not None and image.format == "svg"


def test_html_guard_refuses_network_paths_before_resolving() -> None:
    assert not validate_local_file_access("file://attacker/share/x.png", allow_local_files=True)
    assert not validate_local_file_access("file:///etc/passwd", allow_local_files=False)


def test_arxiv_bundle_reads_local_images_only_when_allowed(files: dict[str, Path]) -> None:
    from all2md.options.arxiv import ArxivPackagerOptions
    from all2md.renderers.arxiv_latex import ArxivLatexRenderer

    for name, allowed, expected in [("secret", True, False), ("png", False, False), ("png", True, True)]:
        options = ArxivPackagerOptions(local_files=ALLOW) if allowed else ArxivPackagerOptions()
        renderer = ArxivLatexRenderer(arxiv_options=options)
        renderer.render_to_string(_doc(str(files[name])))
        got = any(f.data and MARKER in f.data for f in renderer.extracted_figures)
        assert got is expected, (name, allowed)


def test_static_site_copies_only_images_under_the_source_folder(tmp_path: Path, files: dict[str, Path]) -> None:
    from all2md.utils.static_site import StaticSiteGenerator, copy_document_assets

    site = tmp_path / "site"
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "ok.png").write_bytes(PNG_1X1)
    doc = Document(
        children=[
            Paragraph(content=[Image(url="ok.png", alt_text="a")]),
            Paragraph(content=[Image(url=str(files["png"]), alt_text="b")]),
            Paragraph(content=[Image(url="../secret.json", alt_text="c")]),
        ]
    )
    _, copied = copy_document_assets(doc, site, StaticSiteGenerator.HUGO, source_file=src_dir / "post.md")
    assert [Path(p).name for p in copied] == ["ok.png"]
