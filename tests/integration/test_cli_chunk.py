#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for the ``all2md chunk`` CLI command."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.cli]

SAMPLE_MD = """# Introduction

The introduction explains the motivation and the goals of the work in a
few sentences so there is enough text to chunk.

# Methods

The methods section describes how the study was conducted, step by step,
with enough detail to produce multiple chunks under a small token budget.

# Results

The results section reports what was found.
"""

TABLE_MD = """# Data

Intro paragraph with several words to chunk here first.

| Name | Role | Notes |
|------|------|-------|
| Alice | Engineer | builds things |
| Bob | Designer | draws things |
| Carol | PM | plans things |

An image: ![pic](https://example.com/logo.png)

Trailing paragraph after the table content.
"""


@pytest.fixture
def sample_file(tmp_path) -> Path:
    """Write a multi-section markdown file to a temp dir."""
    path = tmp_path / "doc.md"
    path.write_text(SAMPLE_MD, encoding="utf-8")
    return path


@pytest.fixture
def table_file(tmp_path) -> Path:
    """Write a markdown file containing a table and an image."""
    path = tmp_path / "table.md"
    path.write_text(TABLE_MD, encoding="utf-8")
    return path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the all2md CLI as a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "all2md", "chunk", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class TestChunkCLI:
    """End-to-end behavior of the chunk subcommand."""

    def test_jsonl_default(self, sample_file):
        """Default JSONL output: every line parses and respects the token budget."""
        result = _run(
            [str(sample_file), "--strategy", "paragraph", "--max-tokens", "40", "--token-counter", "whitespace"],
            cwd=sample_file.parent,
        )
        assert result.returncode == 0, result.stderr
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        assert lines
        objs = [json.loads(ln) for ln in lines]
        assert all(o["token_count"] <= 40 for o in objs)
        # Provenance fields present and sections captured.
        assert {"chunk_id", "section_heading", "page", "char_basis"} <= set(objs[0])
        assert "Introduction" in {o["section_heading"] for o in objs}

    def test_json_array(self, sample_file):
        """JSON format emits a single parseable array."""
        result = _run(
            [
                str(sample_file),
                "--strategy",
                "section",
                "--max-tokens",
                "200",
                "--format",
                "json",
                "--token-counter",
                "whitespace",
            ],
            cwd=sample_file.parent,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert isinstance(data, list) and data

    def test_pretty_output(self, sample_file):
        """Pretty format is human-readable and mentions a section."""
        result = _run(
            [
                str(sample_file),
                "--strategy",
                "section",
                "--max-tokens",
                "200",
                "--format",
                "pretty",
                "--token-counter",
                "whitespace",
            ],
            cwd=sample_file.parent,
        )
        assert result.returncode == 0, result.stderr
        assert "Introduction" in result.stdout

    def test_out_file(self, sample_file, tmp_path):
        """--out writes JSONL to a file and reports the count on stderr."""
        out = tmp_path / "chunks.jsonl"
        result = _run(
            [
                str(sample_file),
                "--strategy",
                "paragraph",
                "--max-tokens",
                "40",
                "--out",
                str(out),
                "--token-counter",
                "whitespace",
            ],
            cwd=sample_file.parent,
        )
        assert result.returncode == 0, result.stderr
        assert out.exists()
        for ln in out.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                json.loads(ln)

    def test_stdin(self, sample_file):
        """Reading from stdin labels the document 'stdin'."""
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "all2md",
                "chunk",
                "-",
                "--strategy",
                "paragraph",
                "--max-tokens",
                "60",
                "--token-counter",
                "whitespace",
            ],
            cwd=sample_file.parent,
            input=SAMPLE_MD,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        first = json.loads(next(ln for ln in proc.stdout.splitlines() if ln.strip()))
        assert first["document_id"] == "stdin"

    def test_whitespace_token_strategy_rejected(self, sample_file):
        """A token-boundary strategy with --token-counter whitespace fails cleanly."""
        result = _run(
            [str(sample_file), "--strategy", "token", "--token-counter", "whitespace"],
            cwd=sample_file.parent,
        )
        assert result.returncode != 0
        assert "token" in result.stderr.lower()

    def test_help(self, sample_file):
        """--help renders and lists the strategy flag."""
        result = _run(["--help"], cwd=sample_file.parent)
        assert result.returncode == 0
        assert "--strategy" in result.stdout
        assert "--avoid-table-split" in result.stdout
        assert "--drop-elements" in result.stdout


class TestChunkElementHandling:
    """Flags governing tables, dropped elements, and attachments."""

    def test_avoid_table_split(self, table_file):
        """--avoid-table-split keeps the table in a single chunk."""
        result = _run(
            [
                str(table_file),
                "--strategy",
                "paragraph",
                "--max-tokens",
                "8",
                "--avoid-table-split",
                "--token-counter",
                "whitespace",
            ],
            cwd=table_file.parent,
        )
        assert result.returncode == 0, result.stderr
        objs = [json.loads(ln) for ln in result.stdout.splitlines() if ln.strip()]
        table_chunks = [o for o in objs if "|" in o["text"]]
        assert len(table_chunks) == 1

    def test_drop_elements_removes_table_and_image(self, table_file):
        """--drop-elements strips tables and images from the output entirely."""
        result = _run(
            [
                str(table_file),
                "--strategy",
                "paragraph",
                "--max-tokens",
                "200",
                "--drop-elements",
                "images,tables",
                "--token-counter",
                "whitespace",
            ],
            cwd=table_file.parent,
        )
        assert result.returncode == 0, result.stderr
        text = result.stdout
        assert "| Name |" not in text
        assert "example.com/logo.png" not in text
        # Prose survives.
        assert "Intro paragraph" in text

    def test_drop_elements_typo_is_rejected(self, table_file):
        """A misspelled node type fails cleanly with a suggestion."""
        result = _run(
            [str(table_file), "--drop-elements", "tabel", "--token-counter", "whitespace"],
            cwd=table_file.parent,
        )
        assert result.returncode != 0
        assert "table" in result.stderr.lower()

    def test_attachment_mode_accepted(self, table_file):
        """--attachment-mode is accepted and threads to the converter cleanly.

        It is a parse-time lever (controls whether a binary format embeds images
        as base64 / alt-text / skips them); a plain Markdown image link is not a
        binary attachment, so this only asserts the flag runs and yields chunks.
        Binary-attachment handling is covered by the parser option tests.
        """
        result = _run(
            [
                str(table_file),
                "--strategy",
                "section",
                "--max-tokens",
                "300",
                "--attachment-mode",
                "skip",
                "--token-counter",
                "whitespace",
            ],
            cwd=table_file.parent,
        )
        assert result.returncode == 0, result.stderr
        assert [ln for ln in result.stdout.splitlines() if ln.strip()]
