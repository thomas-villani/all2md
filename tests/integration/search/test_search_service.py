import importlib
from pathlib import Path

import pytest

from all2md.search import SearchDocumentInput, SearchMode, SearchService

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents"


@pytest.mark.integration
@pytest.mark.search
def test_search_service_grep_roundtrip(tmp_path: Path) -> None:
    source = FIXTURE_DIR / "basic.md"
    service = SearchService()
    service.build_indexes([SearchDocumentInput(source=source, document_id="basic-md")], modes={SearchMode.GREP})

    assert service.state.chunk_count > 0

    results = service.search("hyperlink", mode=SearchMode.GREP, top_k=5)
    assert results
    assert any("hyperlink" in result.chunk.text.lower() for result in results)
    assert "<<" in results[0].chunk.text
    assert results[0].metadata.get("lines")

    service.save(tmp_path)
    reloaded = SearchService.load(tmp_path)

    persisted_results = reloaded.search("hyperlink", mode=SearchMode.GREP, top_k=5)
    assert persisted_results
    assert "<<" in persisted_results[0].chunk.text
    assert persisted_results[0].metadata.get("lines")


@pytest.mark.integration
@pytest.mark.search
@pytest.mark.skipif(importlib.util.find_spec("rank_bm25") is None, reason="rank_bm25 not installed")
def test_search_service_keyword_roundtrip(tmp_path: Path) -> None:
    source = FIXTURE_DIR / "basic.md"
    service = SearchService()
    service.build_indexes([SearchDocumentInput(source=source, document_id="basic-md")], modes={SearchMode.KEYWORD})

    results = service.search("hyperlink", mode=SearchMode.KEYWORD, top_k=5)
    assert results
    assert "<<" in results[0].chunk.text

    service.save(tmp_path)
    reloaded = SearchService.load(tmp_path)

    persisted_results = reloaded.search("hyperlink", mode=SearchMode.KEYWORD, top_k=5)
    assert persisted_results
    assert "<<" in persisted_results[0].chunk.text


@pytest.mark.integration
@pytest.mark.search
@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is None, reason="sentence_transformers not installed"
)
def test_search_service_vector_roundtrip(tmp_path: Path) -> None:
    source = FIXTURE_DIR / "basic.md"
    service = SearchService()
    service.build_indexes([SearchDocumentInput(source=source, document_id="basic-md")], modes={SearchMode.VECTOR})

    results = service.search("hyperlink", mode=SearchMode.VECTOR, top_k=5)
    assert results

    service.save(tmp_path)
    reloaded = SearchService.load(tmp_path)

    persisted_results = reloaded.search("hyperlink", mode=SearchMode.VECTOR, top_k=5)
    assert persisted_results
