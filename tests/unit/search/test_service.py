import importlib
from pathlib import Path

import pytest

from all2md.options.search import SearchOptions
from all2md.search.service import SearchDocumentInput, SearchService
from all2md.search.types import SearchMode


@pytest.fixture()
def sample_markdown(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text("""# Sample\n\nThis document contains a keyword for testing search.""", encoding="utf-8")
    return path


def test_search_service_grep(sample_markdown: Path) -> None:
    service = SearchService()
    document = SearchDocumentInput(source=sample_markdown, document_id="sample")
    service.build_indexes([document], modes={SearchMode.GREP})

    results = service.search("keyword", mode=SearchMode.GREP, top_k=5)
    assert results
    assert any("keyword" in result.chunk.text.lower() for result in results)


@pytest.mark.skipif(importlib.util.find_spec("rank_bm25") is None, reason="rank_bm25 not installed")
def test_search_service_keyword_mode(sample_markdown: Path) -> None:
    service = SearchService(options=SearchOptions())
    document = SearchDocumentInput(source=sample_markdown, document_id="sample")
    service.build_indexes([document], modes={SearchMode.KEYWORD})

    results = service.search("keyword", mode=SearchMode.KEYWORD, top_k=5)
    assert results
    assert results[0].metadata.get("backend") == "keyword"


@pytest.mark.skipif(importlib.util.find_spec("rank_bm25") is None, reason="rank_bm25 not installed")
def test_build_search_service_api(sample_markdown: Path) -> None:
    from all2md.search import build_search_service, search_with_service

    document = SearchDocumentInput(source=sample_markdown, document_id="sample")
    service = build_search_service([document], modes={SearchMode.KEYWORD})
    results = search_with_service(service, "keyword", mode=SearchMode.KEYWORD)
    assert results
