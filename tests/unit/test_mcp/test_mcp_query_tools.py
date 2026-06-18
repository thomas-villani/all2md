"""Unit tests for MCP query tool implementations (search, diff, outline)."""

import importlib.util

import pytest

from all2md.mcp.config import MCPConfig
from all2md.mcp.query_tools import (
    diff_documents_impl,
    get_document_outline_impl,
    search_documents_impl,
)
from all2md.mcp.schemas import (
    DiffDocumentsInput,
    GetDocumentOutlineInput,
    SearchDocumentsInput,
)
from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs

HAS_BM25 = importlib.util.find_spec("rank_bm25") is not None

SAMPLE_MD = """# Introduction

The alpha protocol governs the handshake.

## Details

Beta follows alpha in the sequence.

### Edge Cases

Gamma is rarely reached.

# Conclusion

The alpha protocol is complete.
"""


def _make_config(tmp_path, **overrides):
    """Build an MCPConfig with read/write allowlists rooted at tmp_path."""
    allow = prepare_allowlist_dirs([str(tmp_path)])
    kwargs = {"read_allowlist": allow, "write_allowlist": allow}
    kwargs.update(overrides)
    return MCPConfig(**kwargs)


def _write_corpus(tmp_path):
    """Create a small markdown corpus and return the directory."""
    (tmp_path / "doc1.md").write_text(SAMPLE_MD, encoding="utf-8")
    (tmp_path / "doc2.md").write_text("# Other\n\nNothing relevant here, just delta.\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# get_document_outline
# ---------------------------------------------------------------------------
class TestOutline:
    def test_outline_from_content(self):
        config = MCPConfig()
        result = get_document_outline_impl(GetDocumentOutlineInput(doc=SAMPLE_MD, format_hint="markdown"), config)
        headings = [s["heading"] for s in result.sections]
        assert headings == ["Introduction", "Details", "Edge Cases", "Conclusion"]
        assert result.total == 4
        # Indices are zero-based and contiguous
        assert [s["index"] for s in result.sections] == [0, 1, 2, 3]
        # Levels reflect heading depth
        levels = {s["heading"]: s["level"] for s in result.sections}
        assert levels["Introduction"] == 1
        assert levels["Details"] == 2
        assert levels["Edge Cases"] == 3

    def test_outline_max_level_filters_deeper_headings(self):
        config = MCPConfig()
        result = get_document_outline_impl(
            GetDocumentOutlineInput(doc=SAMPLE_MD, format_hint="markdown", max_level=2), config
        )
        headings = [s["heading"] for s in result.sections]
        assert "Edge Cases" not in headings  # level 3 excluded
        assert "Details" in headings

    def test_outline_invalid_max_level(self):
        config = MCPConfig()
        with pytest.raises(ValueError):
            get_document_outline_impl(
                GetDocumentOutlineInput(doc=SAMPLE_MD, format_hint="markdown", max_level=9), config
            )

    def test_outline_from_file_path(self, tmp_path):
        test_file = tmp_path / "outline.md"
        test_file.write_text(SAMPLE_MD, encoding="utf-8")
        config = _make_config(tmp_path)
        result = get_document_outline_impl(GetDocumentOutlineInput(doc=str(test_file), format_hint="markdown"), config)
        assert result.total == 4

    def test_outline_path_outside_allowlist_denied(self, tmp_path):
        # File exists but read allowlist points elsewhere
        outside = tmp_path / "secret.md"
        outside.write_text(SAMPLE_MD, encoding="utf-8")
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        config = MCPConfig(read_allowlist=prepare_allowlist_dirs([str(allowed_dir)]))
        with pytest.raises(MCPSecurityError):
            get_document_outline_impl(GetDocumentOutlineInput(doc=str(outside), format_hint="markdown"), config)


# ---------------------------------------------------------------------------
# diff_documents
# ---------------------------------------------------------------------------
class TestDiff:
    def test_diff_unified_with_changes(self):
        config = MCPConfig()
        result = diff_documents_impl(DiffDocumentsInput(old="Hello world", new="Goodbye world"), config)
        assert result.has_changes is True
        assert "Hello" in result.diff
        assert "Goodbye" in result.diff

    def test_diff_no_changes(self):
        config = MCPConfig()
        result = diff_documents_impl(DiffDocumentsInput(old="Same content", new="Same content"), config)
        assert result.has_changes is False

    def test_diff_json_format(self):
        config = MCPConfig()
        result = diff_documents_impl(DiffDocumentsInput(old="Hello world", new="Goodbye world", format="json"), config)
        assert result.has_changes is True
        # JSON renderer returns a JSON document
        import json

        parsed = json.loads(result.diff)
        assert isinstance(parsed, dict)

    def test_diff_from_files(self, tmp_path):
        old_file = tmp_path / "v1.md"
        new_file = tmp_path / "v2.md"
        old_file.write_text("# Title\n\nFirst version.\n", encoding="utf-8")
        new_file.write_text("# Title\n\nSecond version.\n", encoding="utf-8")
        config = _make_config(tmp_path)
        result = diff_documents_impl(DiffDocumentsInput(old=str(old_file), new=str(new_file)), config)
        assert result.has_changes is True


# ---------------------------------------------------------------------------
# search_documents
# ---------------------------------------------------------------------------
class TestSearch:
    def test_grep_mode_finds_matches(self, tmp_path):
        _write_corpus(tmp_path)
        config = _make_config(tmp_path)
        result = search_documents_impl(SearchDocumentsInput(query="alpha", mode="grep", paths=[str(tmp_path)]), config)
        assert result.mode == "grep"
        assert result.total >= 1
        # Highlight markers present in snippets
        assert any("<<" in item.snippet and ">>" in item.snippet for item in result.results)
        # Document path metadata propagated
        assert all(item.document_path for item in result.results)

    def test_grep_ignore_case(self, tmp_path):
        _write_corpus(tmp_path)
        config = _make_config(tmp_path)
        result = search_documents_impl(
            SearchDocumentsInput(query="ALPHA", mode="grep", ignore_case=True, paths=[str(tmp_path)]),
            config,
        )
        assert result.total >= 1

    def test_grep_no_match_returns_empty(self, tmp_path):
        _write_corpus(tmp_path)
        config = _make_config(tmp_path)
        result = search_documents_impl(
            SearchDocumentsInput(query="nonexistentterm", mode="grep", paths=[str(tmp_path)]), config
        )
        assert result.total == 0
        assert result.results == []

    def test_unsupported_mode_rejected(self, tmp_path):
        _write_corpus(tmp_path)
        config = _make_config(tmp_path)
        with pytest.raises(ValueError, match="Unsupported search mode"):
            search_documents_impl(SearchDocumentsInput(query="alpha", mode="vector", paths=[str(tmp_path)]), config)

    def test_search_path_outside_allowlist_denied(self, tmp_path):
        _write_corpus(tmp_path)
        outside = tmp_path / "doc1.md"
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        config = MCPConfig(read_allowlist=prepare_allowlist_dirs([str(allowed_dir)]))
        with pytest.raises(MCPSecurityError):
            search_documents_impl(SearchDocumentsInput(query="alpha", mode="grep", paths=[str(outside)]), config)

    def test_no_documents_raises(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        config = _make_config(tmp_path)
        with pytest.raises(ValueError, match="No readable documents"):
            search_documents_impl(SearchDocumentsInput(query="alpha", mode="grep", paths=[str(empty)]), config)

    @pytest.mark.skipif(not HAS_BM25, reason="rank-bm25 not installed")
    def test_keyword_mode_ranks_results(self, tmp_path):
        _write_corpus(tmp_path)
        config = _make_config(tmp_path)
        result = search_documents_impl(
            SearchDocumentsInput(query="alpha protocol", mode="keyword", paths=[str(tmp_path)]), config
        )
        assert result.mode == "keyword"
        assert result.total >= 1
        # The alpha-heavy document should be among the results
        assert any("alpha" in item.snippet.lower() for item in result.results)

    @pytest.mark.skipif(not HAS_BM25, reason="rank-bm25 not installed")
    def test_keyword_persistence_creates_and_reuses_index(self, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        _write_corpus(corpus)
        index_dir = tmp_path / "idx"
        config = _make_config(tmp_path, search_index_dir=str(index_dir))

        # First call builds and persists the index
        first = search_documents_impl(
            SearchDocumentsInput(query="alpha protocol", mode="keyword", paths=[str(corpus)]), config
        )
        assert first.total >= 1
        assert (index_dir / "keyword").exists()
        assert (index_dir / "chunks.jsonl").exists()

        # Second call reuses the persisted index and still returns results
        second = search_documents_impl(
            SearchDocumentsInput(query="alpha protocol", mode="keyword", paths=[str(corpus)]), config
        )
        assert second.total >= 1

    @pytest.mark.skipif(not HAS_BM25, reason="rank-bm25 not installed")
    def test_index_dir_outside_write_allowlist_denied(self, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        _write_corpus(corpus)
        # Read allowlist covers corpus; write allowlist is a sibling that does NOT
        # contain the requested index dir.
        write_dir = tmp_path / "writable"
        write_dir.mkdir()
        config = MCPConfig(
            read_allowlist=prepare_allowlist_dirs([str(corpus)]),
            write_allowlist=prepare_allowlist_dirs([str(write_dir)]),
            search_index_dir=str(tmp_path / "outside_idx"),
        )
        with pytest.raises(MCPSecurityError):
            search_documents_impl(SearchDocumentsInput(query="alpha", mode="keyword", paths=[str(corpus)]), config)


# ---------------------------------------------------------------------------
# config flags
# ---------------------------------------------------------------------------
class TestConfigFlags:
    def test_new_tools_enabled_by_default(self):
        config = MCPConfig()
        assert config.enable_search is True
        assert config.enable_diff is True
        assert config.enable_outline is True
        assert config.search_index_dir is None

    def test_validate_allows_only_read_only_tools(self):
        # Disable the original three; the read-only trio should keep config valid
        config = MCPConfig(enable_to_md=False, enable_from_md=False, enable_doc_edit=False)
        config.validate()  # should not raise

    def test_validate_requires_at_least_one_tool(self):
        config = MCPConfig(
            enable_to_md=False,
            enable_from_md=False,
            enable_doc_edit=False,
            enable_search=False,
            enable_diff=False,
            enable_outline=False,
            enable_list_files=False,
        )
        with pytest.raises(ValueError):
            config.validate()

    def test_env_vars_toggle_flags(self, monkeypatch):
        from all2md.mcp.config import load_config_from_env

        monkeypatch.setenv("ALL2MD_MCP_ENABLE_SEARCH", "false")
        monkeypatch.setenv("ALL2MD_MCP_ENABLE_DIFF", "false")
        monkeypatch.setenv("ALL2MD_MCP_ENABLE_OUTLINE", "false")
        monkeypatch.setenv("ALL2MD_MCP_SEARCH_INDEX_DIR", "/tmp/all2md-index")

        config = load_config_from_env()
        assert config.enable_search is False
        assert config.enable_diff is False
        assert config.enable_outline is False
        assert config.search_index_dir == "/tmp/all2md-index"
