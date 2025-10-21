"""Performance benchmark tests for all2md document conversions.

Run with: pytest tests/performance --benchmark
Save results: pytest tests/performance --benchmark --benchmark-save
"""

from pathlib import Path

import pytest

from all2md import from_markdown, to_markdown

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "documents"


@pytest.mark.benchmark
class TestPdfBenchmarks:
    """Performance benchmarks for PDF conversion."""

    @pytest.mark.pdf
    def test_benchmark_pdf_basic(self, benchmark_runner):
        """Benchmark basic PDF conversion."""
        pdf_file = FIXTURES_DIR / "basic.pdf"
        if not pdf_file.exists():
            pytest.skip(f"Test file not found: {pdf_file}")

        result = benchmark_runner.run(format_name="pdf", file_path=pdf_file, iterations=5)

        assert result.mean_time > 0
        assert result.mean_time < 10.0

    @pytest.mark.pdf
    @pytest.mark.slow
    def test_benchmark_pdf_complex(self, benchmark_runner):
        """Benchmark complex PDF conversion with tables and formatting."""
        pdf_file = FIXTURES_DIR / "complex.pdf"
        if not pdf_file.exists():
            pytest.skip(f"Test file not found: {pdf_file}")

        result = benchmark_runner.run(format_name="pdf", file_path=pdf_file, iterations=3)

        assert result.mean_time > 0
        print(f"\nComplex PDF: {result.throughput_mbps:.2f} MB/s")


@pytest.mark.benchmark
class TestDocxBenchmarks:
    """Performance benchmarks for DOCX conversion."""

    @pytest.mark.docx
    def test_benchmark_docx_basic(self, benchmark_runner):
        """Benchmark basic DOCX conversion."""
        docx_file = FIXTURES_DIR / "basic.docx"
        if not docx_file.exists():
            pytest.skip(f"Test file not found: {docx_file}")

        result = benchmark_runner.run(format_name="docx", file_path=docx_file, iterations=5)

        assert result.mean_time > 0
        assert result.mean_time < 5.0

    @pytest.mark.docx
    @pytest.mark.slow
    def test_benchmark_docx_complex(self, benchmark_runner):
        """Benchmark complex DOCX with tables and formatting."""
        docx_file = FIXTURES_DIR / "complex.docx"
        if not docx_file.exists():
            pytest.skip(f"Test file not found: {docx_file}")

        result = benchmark_runner.run(format_name="docx", file_path=docx_file, iterations=3)

        assert result.mean_time > 0
        print(f"\nComplex DOCX: {result.throughput_mbps:.2f} MB/s")

    @pytest.mark.docx
    def test_benchmark_docx_footnotes(self, benchmark_runner):
        """Benchmark DOCX with footnotes and comments."""
        docx_file = FIXTURES_DIR / "footnotes-endnotes-comments.docx"
        if not docx_file.exists():
            pytest.skip(f"Test file not found: {docx_file}")

        result = benchmark_runner.run(format_name="docx", file_path=docx_file, iterations=3)

        assert result.mean_time > 0


@pytest.mark.benchmark
class TestHtmlBenchmarks:
    """Performance benchmarks for HTML conversion."""

    @pytest.mark.html
    def test_benchmark_html_basic(self, benchmark_runner):
        """Benchmark basic HTML conversion."""
        html_file = FIXTURES_DIR / "basic.html"
        if not html_file.exists():
            pytest.skip(f"Test file not found: {html_file}")

        result = benchmark_runner.run(format_name="html", file_path=html_file, iterations=10)

        assert result.mean_time > 0
        assert result.mean_time < 2.0

    @pytest.mark.html
    def test_benchmark_html_readability(self, benchmark_runner):
        """Benchmark HTML conversion with readability."""
        html_file = FIXTURES_DIR / "html_readability_article.html"
        if not html_file.exists():
            pytest.skip(f"Test file not found: {html_file}")

        result = benchmark_runner.run(format_name="html", file_path=html_file, iterations=5)

        assert result.mean_time > 0


@pytest.mark.benchmark
class TestPptxBenchmarks:
    """Performance benchmarks for PPTX conversion."""

    @pytest.mark.pptx
    def test_benchmark_pptx_basic(self, benchmark_runner):
        """Benchmark basic PPTX conversion."""
        pptx_file = FIXTURES_DIR / "basic.pptx"
        if not pptx_file.exists():
            pytest.skip(f"Test file not found: {pptx_file}")

        result = benchmark_runner.run(format_name="pptx", file_path=pptx_file, iterations=5)

        assert result.mean_time > 0
        assert result.mean_time < 5.0


@pytest.mark.benchmark
class TestXlsxBenchmarks:
    """Performance benchmarks for XLSX conversion."""

    @pytest.mark.xlsx
    def test_benchmark_xlsx_basic(self, benchmark_runner):
        """Benchmark basic XLSX conversion."""
        xlsx_file = FIXTURES_DIR / "basic.xlsx"
        if not xlsx_file.exists():
            pytest.skip(f"Test file not found: {xlsx_file}")

        result = benchmark_runner.run(format_name="xlsx", file_path=xlsx_file, iterations=5)

        assert result.mean_time > 0
        assert result.mean_time < 3.0


@pytest.mark.benchmark
class TestOdfBenchmarks:
    """Performance benchmarks for ODF (ODT/ODP) conversion."""

    @pytest.mark.odf
    def test_benchmark_odt_basic(self, benchmark_runner):
        """Benchmark basic ODT conversion."""
        odt_file = FIXTURES_DIR / "basic.odt"
        if not odt_file.exists():
            pytest.skip(f"Test file not found: {odt_file}")

        result = benchmark_runner.run(format_name="odt", file_path=odt_file, iterations=5)

        assert result.mean_time > 0
        assert result.mean_time < 5.0

    @pytest.mark.odf
    def test_benchmark_odt_complex(self, benchmark_runner):
        """Benchmark complex ODT conversion."""
        odt_file = FIXTURES_DIR / "complex.odt"
        if not odt_file.exists():
            pytest.skip(f"Test file not found: {odt_file}")

        result = benchmark_runner.run(format_name="odt", file_path=odt_file, iterations=3)

        assert result.mean_time > 0


@pytest.mark.benchmark
class TestGeneratedFixtureBenchmarks:
    """Performance benchmarks using generated fixtures."""

    @pytest.mark.epub
    def test_benchmark_epub_simple(self, benchmark_runner):
        """Benchmark simple EPUB conversion."""
        epub_file = FIXTURES_DIR / "generated" / "epub-simple.epub"
        if not epub_file.exists():
            pytest.skip(f"Test file not found: {epub_file}")

        result = benchmark_runner.run(format_name="epub", file_path=epub_file, iterations=3)

        assert result.mean_time > 0

    @pytest.mark.ipynb
    def test_benchmark_ipynb_simple(self, benchmark_runner):
        """Benchmark simple Jupyter notebook conversion."""
        ipynb_file = FIXTURES_DIR / "generated" / "ipynb-simple.ipynb"
        if not ipynb_file.exists():
            pytest.skip(f"Test file not found: {ipynb_file}")

        result = benchmark_runner.run(format_name="ipynb", file_path=ipynb_file, iterations=5)

        assert result.mean_time > 0

    @pytest.mark.mhtml
    def test_benchmark_mhtml_simple(self, benchmark_runner):
        """Benchmark simple MHTML conversion."""
        mhtml_file = FIXTURES_DIR / "generated" / "mhtml-simple.mht"
        if not mhtml_file.exists():
            pytest.skip(f"Test file not found: {mhtml_file}")

        result = benchmark_runner.run(format_name="mhtml", file_path=mhtml_file, iterations=5)

        assert result.mean_time > 0

    def test_benchmark_csv_basic(self, benchmark_runner):
        """Benchmark CSV conversion."""
        csv_file = FIXTURES_DIR / "basic.csv"
        if not csv_file.exists():
            pytest.skip(f"Test file not found: {csv_file}")

        result = benchmark_runner.run(format_name="csv", file_path=csv_file, iterations=10)

        assert result.mean_time > 0
        assert result.mean_time < 1.0

    def test_benchmark_rtf_basic(self, benchmark_runner):
        """Benchmark RTF conversion."""
        rtf_file = FIXTURES_DIR / "basic-format.rtf"
        if not rtf_file.exists():
            pytest.skip(f"Test file not found: {rtf_file}")

        result = benchmark_runner.run(format_name="rtf", file_path=rtf_file, iterations=5)

        assert result.mean_time > 0


@pytest.mark.benchmark
class TestRoundtripBenchmarks:
    """Performance benchmarks for round-trip conversions (MD -> Format -> MD)."""

    @pytest.mark.docx
    @pytest.mark.slow
    def test_benchmark_roundtrip_markdown_to_docx(self, benchmark_runner, tmp_path):
        """Benchmark round-trip: Markdown -> DOCX -> Markdown."""
        md_file = FIXTURES_DIR / "basic.md"
        if not md_file.exists():
            pytest.skip(f"Test file not found: {md_file}")

        docx_output = tmp_path / "output.docx"

        def roundtrip_conversion():
            from_markdown(md_file, target_format="docx", output=docx_output)
            to_markdown(docx_output)

        result = benchmark_runner.run(
            format_name="md->docx->md",
            file_path=md_file,
            iterations=3,
            conversion_func=lambda x: roundtrip_conversion(),
        )

        assert result.mean_time > 0


@pytest.mark.benchmark
class TestBatchBenchmarks:
    """Performance benchmarks for batch processing multiple files."""

    @pytest.mark.slow
    def test_benchmark_batch_multiple_formats(self, benchmark_runner):
        """Benchmark converting multiple files in sequence."""
        test_files = [
            FIXTURES_DIR / "basic.pdf",
            FIXTURES_DIR / "basic.docx",
            FIXTURES_DIR / "basic.html",
            FIXTURES_DIR / "basic.xlsx",
        ]

        existing_files = [f for f in test_files if f.exists()]
        if not existing_files:
            pytest.skip("No test files found for batch benchmark")

        def batch_conversion():
            for file_path in existing_files:
                to_markdown(file_path)

        import time

        timings = []
        for _ in range(3):
            start = time.perf_counter()
            batch_conversion()
            timings.append(time.perf_counter() - start)

        mean_time = sum(timings) / len(timings)
        print(f"\nBatch conversion of {len(existing_files)} files: {mean_time:.3f}s")
        assert mean_time > 0
