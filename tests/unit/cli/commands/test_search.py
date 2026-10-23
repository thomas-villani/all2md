"""Unit tests for all2md CLI search command handlers.

This module tests the search and grep command handlers directly,
providing coverage for argument parsing and helper functions.
"""

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from all2md.cli.commands.search import (
    _append_with_dim_ellipses,
    _apply_search_config,
    _collect_search_overrides,
    _create_search_documents,
    _format_plain_snippet,
    _group_results_by_doc_and_section,
    _make_search_progress_callback,
    _parse_line_number_if_present,
    _parse_search_mode,
    _render_compact_plain,
    _render_grep_results,
    _render_grouped_plain,
    _render_search_results,
    _result_to_dict,
    _rich_snippet,
    handle_grep_command,
    handle_search_command,
)
from all2md.cli.input_items import CLIInputItem
from all2md.options.search import SearchOptions
from all2md.search.service import SearchMode, SearchResult


@pytest.mark.unit
class TestSearchCommandHelpers:
    """Test helper functions for search command."""

    def test_parse_line_number_present(self):
        """Test parsing line number from grep output."""
        line_num, content = _parse_line_number_if_present("42: some text here", True)
        assert line_num == "42"
        assert content == "some text here"

    def test_parse_line_number_absent(self):
        """Test parsing when no line number present."""
        line_num, content = _parse_line_number_if_present("just text", True)
        assert line_num is None
        assert content == "just text"

    def test_parse_line_number_disabled(self):
        """Test parsing when line numbers disabled."""
        line_num, content = _parse_line_number_if_present("42: text", False)
        assert line_num is None
        assert content == "42: text"

    def test_format_plain_snippet_basic(self):
        """Test formatting plain text snippet."""
        lines = _format_plain_snippet("Short text", width=100, indent="  ")
        assert len(lines) == 1
        assert lines[0] == "  Short text"

    def test_format_plain_snippet_multiline(self):
        """Test formatting multiline snippet."""
        text = "Line 1\nLine 2\nLine 3"
        lines = _format_plain_snippet(text, width=100, indent="    ")
        assert len(lines) == 3
        assert all(line.startswith("    ") for line in lines)

    def test_parse_search_mode_grep(self):
        """Test parsing grep mode."""
        from all2md.search.service import SearchMode

        options = SearchOptions()
        mode = _parse_search_mode("grep", options)
        assert mode == SearchMode.GREP

    def test_parse_search_mode_keyword(self):
        """Test parsing keyword mode."""
        from all2md.search.service import SearchMode

        options = SearchOptions()
        mode = _parse_search_mode("keyword", options)
        assert mode == SearchMode.KEYWORD

    def test_parse_search_mode_invalid(self):
        """Test parsing invalid mode raises error."""
        options = SearchOptions()
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_search_mode("invalid_mode", options)


@pytest.mark.unit
class TestHandleSearchCommand:
    """Test handle_search_command function."""

    def test_search_help(self, capsys):
        """Test search --help returns successfully."""
        exit_code = handle_search_command(["--help"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_search_missing_query(self):
        """Test search without query fails."""
        exit_code = handle_search_command([])
        # Returns non-zero or raises SystemExit
        if exit_code is not None:
            assert exit_code != 0

    def test_search_persist_without_index_dir(self, capsys):
        """Test --persist requires --index-dir."""
        try:
            exit_code = handle_search_command(["query", "file.md", "--persist"])
            assert exit_code != 0
        except SystemExit as e:
            assert e.code != 0
        captured = capsys.readouterr()
        assert "--persist requires --index-dir" in captured.err

    def test_search_negative_context(self, capsys):
        """Test negative context values are rejected."""
        with pytest.raises(SystemExit):
            handle_search_command(["query", "file.md", "--grep", "-A", "-1"])


@pytest.mark.unit
class TestHandleGrepCommand:
    """Test handle_grep_command function."""

    def test_grep_help(self, capsys):
        """Test grep --help returns successfully."""
        with pytest.raises(SystemExit) as exc_info:
            handle_grep_command(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_grep_missing_inputs(self):
        """Test grep without inputs fails."""
        with pytest.raises(SystemExit):
            handle_grep_command([])


@pytest.mark.unit
class TestSearchModesParsing:
    """Test parsing of various search modes."""

    def test_parse_search_mode_vector(self):
        """Test parsing vector mode."""
        options = SearchOptions()
        mode = _parse_search_mode("vector", options)
        assert mode == SearchMode.VECTOR

    def test_parse_search_mode_hybrid(self):
        """Test parsing hybrid mode."""
        options = SearchOptions()
        mode = _parse_search_mode("hybrid", options)
        assert mode == SearchMode.HYBRID

    def test_parse_search_mode_bm25_alias(self):
        """Test parsing bm25 as alias for keyword mode."""
        options = SearchOptions()
        mode = _parse_search_mode("bm25", options)
        assert mode == SearchMode.KEYWORD

    def test_parse_search_mode_case_insensitive(self):
        """Test parsing mode is case insensitive."""
        options = SearchOptions()
        mode = _parse_search_mode("GREP", options)
        assert mode == SearchMode.GREP

        mode = _parse_search_mode("Keyword", options)
        assert mode == SearchMode.KEYWORD

    def test_parse_search_mode_with_whitespace(self):
        """Test parsing mode with whitespace."""
        options = SearchOptions()
        mode = _parse_search_mode("  grep  ", options)
        assert mode == SearchMode.GREP

    def test_parse_search_mode_uses_default(self):
        """Test parsing None uses default mode from options."""
        options = SearchOptions(default_mode="keyword")
        mode = _parse_search_mode(None, options)
        assert mode == SearchMode.KEYWORD


@pytest.mark.unit
class TestProgressCallback:
    """Test progress callback functionality."""

    def test_make_search_progress_callback_disabled(self):
        """Test callback is None when disabled."""
        callback = _make_search_progress_callback(False)
        assert callback is None

    def test_make_search_progress_callback_enabled(self):
        """Test callback is callable when enabled."""
        callback = _make_search_progress_callback(True)
        assert callable(callback)

    def test_progress_callback_handles_error_event(self, capsys):
        """Test callback handles error events."""
        callback = _make_search_progress_callback(True)

        # Create mock event with error type
        event = MagicMock()
        event.event_type = "error"
        event.message = "Test error message"

        callback(event)
        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert "Test error message" in captured.err

    def test_progress_callback_handles_item_done_event(self, capsys):
        """Test callback handles item_done events for documents."""
        callback = _make_search_progress_callback(True)

        event = MagicMock()
        event.event_type = "item_done"
        event.message = "Document processed"
        event.metadata = {"item_type": "document"}

        callback(event)
        captured = capsys.readouterr()
        assert "ITEM_DONE" in captured.err
        assert "Document processed" in captured.err

    def test_progress_callback_skips_non_document_items(self, capsys):
        """Test callback skips non-document item_done events."""
        callback = _make_search_progress_callback(True)

        event = MagicMock()
        event.event_type = "item_done"
        event.message = "Some item"
        event.metadata = {"item_type": "chunk"}  # Not document or search

        callback(event)
        captured = capsys.readouterr()
        assert "Some item" not in captured.err


@pytest.mark.unit
class TestRichSnippet:
    """Test rich snippet formatting."""

    def test_rich_snippet_empty(self):
        """Test rich snippet with empty string."""
        result = _rich_snippet("")
        assert result is None

    def test_rich_snippet_no_highlights(self):
        """Test rich snippet without highlight markers."""
        result = _rich_snippet("Plain text without highlights")
        assert result is not None

    def test_rich_snippet_with_highlights(self):
        """Test rich snippet with highlight markers."""
        result = _rich_snippet("Text with <<highlighted>> content")
        assert result is not None

    def test_rich_snippet_multiple_highlights(self):
        """Test rich snippet with multiple highlights."""
        result = _rich_snippet("First <<word>> and second <<match>>")
        assert result is not None

    def test_rich_snippet_unclosed_marker(self):
        """Test rich snippet handles unclosed markers."""
        result = _rich_snippet("Text with <<unclosed marker")
        assert result is not None


@pytest.mark.unit
class TestAppendWithDimEllipses:
    """Test ellipses styling functionality."""

    def test_append_with_dim_ellipses_empty(self):
        """Test with empty content."""
        text = MagicMock()
        _append_with_dim_ellipses(text, "")
        text.append.assert_not_called()

    def test_append_with_dim_ellipses_no_ellipses(self):
        """Test with content without ellipses."""
        text = MagicMock()
        _append_with_dim_ellipses(text, "plain text")
        text.append.assert_called()

    def test_append_with_dim_ellipses_with_ellipses(self):
        """Test with content containing ellipses."""
        text = MagicMock()
        _append_with_dim_ellipses(text, "start...end")
        # Should have multiple append calls - one for text parts, one for ellipses
        assert text.append.call_count >= 2


@pytest.mark.unit
class TestGroupResultsByDocAndSection:
    """Test result grouping functionality."""

    def test_group_results_empty(self):
        """Test grouping empty results."""
        grouped = _group_results_by_doc_and_section([])
        assert grouped == {}

    def test_group_results_single_doc(self):
        """Test grouping results from single document."""
        # Create mock results
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/path/to/doc.md", "section_heading": "Section 1"}

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk

        grouped = _group_results_by_doc_and_section([result])

        assert "/path/to/doc.md" in grouped
        assert "Section 1" in grouped["/path/to/doc.md"]
        assert len(grouped["/path/to/doc.md"]["Section 1"]) == 1

    def test_group_results_multiple_sections(self):
        """Test grouping results with multiple sections."""
        chunk1 = MagicMock()
        chunk1.metadata = {"document_path": "/doc.md", "section_heading": "Section 1"}
        result1 = MagicMock(spec=SearchResult)
        result1.chunk = chunk1

        chunk2 = MagicMock()
        chunk2.metadata = {"document_path": "/doc.md", "section_heading": "Section 2"}
        result2 = MagicMock(spec=SearchResult)
        result2.chunk = chunk2

        grouped = _group_results_by_doc_and_section([result1, result2])

        assert "Section 1" in grouped["/doc.md"]
        assert "Section 2" in grouped["/doc.md"]

    def test_group_results_uses_preamble_for_missing_section(self):
        """Test grouping uses (preamble) for missing section heading."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md"}  # No section_heading

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk

        grouped = _group_results_by_doc_and_section([result])

        assert "(preamble)" in grouped["/doc.md"]

    def test_group_results_fallback_to_path_hint(self):
        """Test grouping uses path_hint when document_path missing."""
        chunk = MagicMock()
        chunk.metadata = {"path_hint": "hint.md", "section_heading": "Section"}

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk

        grouped = _group_results_by_doc_and_section([result])

        assert "hint.md" in grouped


@pytest.mark.unit
class TestRenderFunctions:
    """Test rendering helper functions."""

    def test_render_compact_plain_basic(self, capsys):
        """Test compact plain rendering."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md", "section_heading": "Section"}
        chunk.text = "Match line 1\nMatch line 2"

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk

        grouped = _group_results_by_doc_and_section([result])
        _render_compact_plain(grouped, show_line_numbers=False)

        captured = capsys.readouterr()
        assert "/doc.md" in captured.out
        assert "Section:" in captured.out

    def test_render_compact_plain_with_line_numbers(self, capsys):
        """Test compact plain rendering with line numbers."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md", "section_heading": "Section"}
        chunk.text = "42: Match content"

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk

        grouped = _group_results_by_doc_and_section([result])
        _render_compact_plain(grouped, show_line_numbers=True)

        captured = capsys.readouterr()
        assert "42:" in captured.out

    def test_render_grouped_plain_basic(self, capsys):
        """Test grouped plain rendering."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md", "section_heading": "Section"}
        chunk.text = "Match content"

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk

        grouped = _group_results_by_doc_and_section([result])
        _render_grouped_plain(grouped)

        captured = capsys.readouterr()
        assert "/doc.md" in captured.out
        assert "Section" in captured.out
        assert "Match content" in captured.out

    def test_render_search_results_no_results(self, capsys):
        """Test rendering when no results."""
        _render_search_results([], use_rich=False)
        captured = capsys.readouterr()
        assert "No results found" in captured.out

    def test_render_search_results_with_results(self, capsys):
        """Test rendering with results."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md", "section_heading": "Section"}
        chunk.text = "Match content"

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk
        result.score = 0.95
        result.metadata = {"backend": "keyword"}

        _render_search_results([result], use_rich=False)
        captured = capsys.readouterr()

        assert "0.95" in captured.out or "score" in captured.out.lower()

    def test_render_grep_results_compact(self, capsys):
        """Test grep results rendering in compact format."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md", "section_heading": "Section"}
        chunk.text = "grep match"

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk
        result.metadata = {"backend": "grep"}

        _render_grep_results([result], use_rich=False, context_before=0, context_after=0, show_line_numbers=False)
        captured = capsys.readouterr()

        assert "grep match" in captured.out

    def test_render_grep_results_with_context(self, capsys):
        """Test grep results rendering with context lines."""
        chunk = MagicMock()
        chunk.metadata = {"document_path": "/doc.md", "section_heading": "Section"}
        chunk.text = "context line"

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk
        result.metadata = {"backend": "grep"}

        _render_grep_results([result], use_rich=False, context_before=2, context_after=2, show_line_numbers=False)
        captured = capsys.readouterr()

        assert "context line" in captured.out


@pytest.mark.unit
class TestApplySearchConfig:
    """Test search config application."""

    def test_apply_search_config_empty(self):
        """Test applying empty config section."""
        options = SearchOptions()
        result = _apply_search_config(options, {})
        assert result == options

    def test_apply_search_config_with_values(self):
        """Test applying config with values."""
        options = SearchOptions()
        config = {"chunk_size_tokens": 1000, "bm25_k1": 1.5}
        result = _apply_search_config(options, config)

        assert result.chunk_size_tokens == 1000
        assert result.bm25_k1 == 1.5

    def test_apply_search_config_ignores_invalid_keys(self):
        """Test that invalid keys are ignored."""
        options = SearchOptions()
        config = {"invalid_key": "value", "chunk_size_tokens": 500}
        result = _apply_search_config(options, config)

        assert result.chunk_size_tokens == 500
        assert not hasattr(result, "invalid_key")


@pytest.mark.unit
class TestCollectSearchOverrides:
    """Test collection of search option overrides from parsed args."""

    def test_collect_search_overrides_empty(self):
        """Test collecting overrides with no values set."""
        parsed = argparse.Namespace()
        overrides = _collect_search_overrides(parsed)
        assert overrides == {}

    def test_collect_search_overrides_with_values(self):
        """Test collecting overrides with values set."""
        parsed = argparse.Namespace(
            chunk_size_tokens=1000,
            bm25_k1=1.5,
            vector_model_name="all-MiniLM-L6-v2",
        )
        overrides = _collect_search_overrides(parsed)

        assert overrides.get("chunk_size_tokens") == 1000
        assert overrides.get("bm25_k1") == 1.5
        assert overrides.get("vector_model_name") == "all-MiniLM-L6-v2"

    def test_collect_search_overrides_none_values_excluded(self):
        """Test that None values are not included."""
        parsed = argparse.Namespace(
            chunk_size_tokens=None,
            bm25_k1=None,
        )
        overrides = _collect_search_overrides(parsed)
        assert "chunk_size_tokens" not in overrides
        assert "bm25_k1" not in overrides


@pytest.mark.unit
class TestCreateSearchDocuments:
    """Test search document creation from CLI input items."""

    def test_create_search_documents_empty(self):
        """Test creating documents from empty list."""
        docs = _create_search_documents([])
        assert docs == []

    def test_create_search_documents_with_path(self):
        """Test creating documents with file path."""
        item = CLIInputItem(
            raw_input="/path/to/doc.md",
            kind="local_file",
            display_name="doc.md",
            path_hint=Path("/path/to/doc.md"),
            metadata={},
        )
        docs = _create_search_documents([item])

        assert len(docs) == 1
        assert docs[0].metadata["display_name"] == "doc.md"

    def test_create_search_documents_with_bytes(self):
        """Test creating documents with bytes input."""
        item = CLIInputItem(
            raw_input=b"# Document content",
            kind="stdin_bytes",
            display_name="stdin",
            path_hint=None,
            metadata={},
        )
        docs = _create_search_documents([item])

        assert len(docs) == 1
        assert isinstance(docs[0].source, bytes)

    def test_create_search_documents_preserves_metadata(self):
        """Test that item metadata is preserved."""
        item = CLIInputItem(
            raw_input="/path/to/doc.md",
            kind="local_file",
            display_name="doc.md",
            path_hint=Path("/path/to/doc.md"),
            metadata={"custom_key": "custom_value"},
        )
        docs = _create_search_documents([item])

        assert docs[0].metadata["custom_key"] == "custom_value"


@pytest.mark.unit
class TestResultToDict:
    """Test search result to dictionary conversion."""

    def test_result_to_dict_basic(self):
        """Test converting result to dictionary."""
        chunk = MagicMock()
        chunk.chunk_id = "chunk_1"
        chunk.text = "Match content"
        chunk.metadata = {"section": "intro"}

        result = MagicMock(spec=SearchResult)
        result.chunk = chunk
        result.score = 0.85
        result.metadata = {"backend": "keyword"}

        result_dict = _result_to_dict(result)

        assert result_dict["score"] == 0.85
        assert result_dict["chunk_id"] == "chunk_1"
        assert result_dict["text"] == "Match content"
        assert result_dict["chunk_metadata"]["section"] == "intro"
        assert result_dict["result_metadata"]["backend"] == "keyword"


@pytest.mark.unit
class TestSearchCommandArguments:
    """Test search command argument parsing."""

    def test_search_help_shows_modes(self, capsys):
        """Test that help shows available modes."""
        handle_search_command(["--help"])
        captured = capsys.readouterr()
        assert "grep" in captured.out.lower()
        assert "keyword" in captured.out.lower()

    def test_search_help_shows_context_options(self, capsys):
        """Test that help shows context options."""
        handle_search_command(["--help"])
        captured = capsys.readouterr()
        assert "-A" in captured.out or "--after-context" in captured.out
        assert "-B" in captured.out or "--before-context" in captured.out
        assert "-C" in captured.out or "--context" in captured.out

    def test_search_negative_top_k(self, capsys):
        """Test that negative top-k is rejected."""
        with pytest.raises(SystemExit):
            handle_search_command(["query", "file.md", "--top-k", "-1"])

    def test_search_zero_top_k(self, capsys):
        """Test that zero top-k is rejected."""
        with pytest.raises(SystemExit):
            handle_search_command(["query", "file.md", "--top-k", "0"])


@pytest.mark.unit
class TestGrepCommandArguments:
    """Test grep command argument parsing."""

    def test_grep_help_shows_options(self, capsys):
        """Test that help shows grep-specific options."""
        with pytest.raises(SystemExit):
            handle_grep_command(["--help"])
        captured = capsys.readouterr()
        assert "-i" in captured.out or "--ignore-case" in captured.out
        assert "-n" in captured.out or "--line-number" in captured.out
        assert "-e" in captured.out or "--regex" in captured.out

    def test_grep_context_shortcut(self, capsys):
        """Test that -C context shortcut is documented."""
        with pytest.raises(SystemExit):
            handle_grep_command(["--help"])
        captured = capsys.readouterr()
        assert "-C" in captured.out or "--context" in captured.out


@pytest.mark.unit
class TestFormatPlainSnippetEdgeCases:
    """Test edge cases for plain snippet formatting."""

    def test_format_plain_snippet_empty(self):
        """Test formatting empty snippet."""
        lines = _format_plain_snippet("", width=100, indent="  ")
        # Empty string should return empty list or list with just indent
        assert lines == [] or lines == ["  "]

    def test_format_plain_snippet_long_line(self):
        """Test formatting very long line."""
        long_text = "word " * 50  # 250 chars
        lines = _format_plain_snippet(long_text, width=80, indent="  ")
        assert len(lines) > 1  # Should wrap

    def test_format_plain_snippet_preserves_indent(self):
        """Test that custom indent is preserved."""
        lines = _format_plain_snippet("text", width=100, indent=">>>")
        assert lines[0].startswith(">>>")

    def test_format_plain_snippet_empty_lines(self):
        """Test handling of empty lines in multiline text."""
        text = "Line 1\n\nLine 3"
        lines = _format_plain_snippet(text, width=100, indent="  ")
        assert len(lines) == 3


_GREP_DOC = """Intro line about latency.

# Results

First paragraph.

Second paragraph with latency here.

Third paragraph.

- item one
- item latency two

| Region | p50 |
|---|---|
| us-east | 42 |

Run `compute_latency()` now.

```python
def latency():
    return 1
```

## Sub latency

Sub text.
"""


@pytest.mark.unit
class TestGrepLines:
    """grep searches lines: a paragraph, list item, table row, heading or line of code each."""

    @pytest.fixture
    def doc(self, tmp_path: Path) -> Path:
        path = tmp_path / "doc.md"
        path.write_text(_GREP_DOC, encoding="utf-8")
        return path

    def _grep(self, capsys, *args: str) -> tuple[int, list[str]]:
        from all2md.cli.commands.search import handle_grep_command

        code = handle_grep_command(list(args))
        return code, [line.strip() for line in capsys.readouterr().out.splitlines() if line.strip()]

    def test_every_block_is_a_line_numbered_through_the_document(self, doc: Path, capsys):
        code, lines = self._grep(capsys, "-n", "latency", str(doc))
        assert code == 0
        assert lines[1:] == [
            "(preamble):1:Intro line about latency.",
            "Results:4:Second paragraph with latency here.",
            "Results:7:- item latency two",
            "Results:10:Run compute_latency() now.",
            "Results:11:def latency():",
            "Sub latency:13:Sub latency",
        ]

    def test_a_table_row_is_a_line(self, doc: Path, capsys):
        _, lines = self._grep(capsys, "-n", "us-east", str(doc))
        assert lines[1:] == ["Results:9:us-east | 42"]

    def test_context_marks_context_lines_and_separates_runs(self, doc: Path, capsys):
        _, lines = self._grep(capsys, "-n", "-C", "1", "-e", "Second|two", str(doc))
        assert lines[lines.index("Results") + 1 :] == [
            "3- First paragraph.",
            "4: Second paragraph with latency here.",
            "5- Third paragraph.",
            "6- - item one",
            "7: - item latency two",
            "8- Region | p50",
        ]
        _, lines = self._grep(capsys, "-n", "-A", "1", "-e", "First|two", str(doc))
        assert lines[lines.index("Results") + 1 :] == [
            "3: First paragraph.",
            "4- Second paragraph with latency here.",
            "--",
            "7: - item latency two",
            "8- Region | p50",
        ]

    def test_max_columns_zero_does_not_truncate(self, tmp_path: Path, capsys):
        path = tmp_path / "long.md"
        sentence = "word " * 80 + "needle " + "word " * 80
        path.write_text(sentence.strip() + "\n", encoding="utf-8")
        _, lines = self._grep(capsys, "-M", "0", "needle", str(path))
        assert lines[1] == "(preamble):" + sentence.strip()
        _, lines = self._grep(capsys, "-M", "40", "needle", str(path))
        assert "needle" in lines[1] and "..." in lines[1] and len(lines[1]) < 80

    def test_no_match_exits_one_and_prints_nothing(self, doc: Path, capsys):
        assert self._grep(capsys, "nothing-matches-this", str(doc)) == (1, [])

    def test_an_invalid_regex_is_an_error_not_a_miss(self, doc: Path, capsys):
        from all2md.cli.commands.search import handle_grep_command

        assert handle_grep_command(["-e", "(", str(doc)]) == 3
        assert "invalid regular expression" in capsys.readouterr().err


@pytest.mark.unit
class TestGrepSelectionAndSummaryFlags:
    """-w, -v, -q, -l and -c behave as they do in grep."""

    @pytest.fixture
    def docs(self, tmp_path: Path) -> tuple[Path, Path]:
        first = tmp_path / "doc.md"
        first.write_text(_GREP_DOC, encoding="utf-8")
        second = tmp_path / "other.md"
        second.write_text("Nothing to see.\n", encoding="utf-8")
        return first, second

    def _grep(self, capsys, *args: str) -> tuple[int, list[str]]:
        from all2md.cli.commands.search import handle_grep_command

        code = handle_grep_command(list(args))
        return code, [line.strip() for line in capsys.readouterr().out.splitlines() if line.strip()]

    def test_word_regexp_skips_a_match_inside_a_word(self, docs, capsys):
        _, lines = self._grep(capsys, "-n", "-w", "latency", str(docs[0]))
        assert "Results:10:Run compute_latency() now." not in lines
        assert "Results:11:def latency():" in lines
        _, lines = self._grep(capsys, "-w", "-e", "late.cy|p50", str(docs[0]))
        assert "Results:Region | p50" in lines

    def test_invert_match_selects_the_lines_without_a_match(self, docs, capsys):
        code, lines = self._grep(
            capsys, "-n", "-v", "-e", "latency|paragraph|item|Region|us-east|Run|return", str(docs[0])
        )
        assert code == 0
        assert lines[1:] == ["Results:2:Results", "Sub latency:14:Sub text."]

    def test_quiet_prints_nothing_and_reports_by_exit_status(self, docs, capsys):
        assert self._grep(capsys, "-q", "latency", str(docs[0])) == (0, [])
        assert self._grep(capsys, "-q", "absent", str(docs[0])) == (1, [])

    def test_files_with_matches_names_each_matching_document_once(self, docs, capsys):
        first, second = docs
        code, lines = self._grep(capsys, "-l", "latency", str(first), str(second))
        assert code == 0
        assert lines == [first.as_posix()]

    def test_count_lists_every_document_and_names_them_only_when_several(self, docs, capsys):
        first, second = docs
        assert self._grep(capsys, "-c", "latency", str(first)) == (0, ["6"])
        code, lines = self._grep(capsys, "-c", "latency", str(first), str(second))
        assert code == 0
        assert lines == [f"{first.as_posix()}:6", f"{second.as_posix()}:0"]
        assert self._grep(capsys, "-c", "absent", str(second)) == (1, ["0"])

    def test_stdin_is_named_standard_input(self, monkeypatch, capsys):
        import io

        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"hello world\n")))
        _, lines = self._grep(capsys, "-l", "hello", "-")
        assert lines == ["(standard input)"]
