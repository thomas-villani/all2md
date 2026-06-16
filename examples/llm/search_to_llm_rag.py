#!/usr/bin/env python3
"""Retrieval-augmented generation over a document corpus, end to end.

This is the headline "all2md for LLMs" example: point it at a folder of mixed
documents (PDF, DOCX, HTML, Markdown, ...) and ask a question. It

1. indexes the corpus with all2md's built-in search (BM25 keyword search over
   structure-aware chunks, each carrying provenance: source file + section),
2. retrieves the top-k most relevant chunks for the question,
3. builds a grounded prompt that includes those chunks with citation markers,
4. asks Claude to answer using *only* the retrieved context, citing sources.

All retrieval uses the real ``all2md.search`` API -- no external vector DB. Use
``--llm mock`` to see the retrieved context and prompt without an API key.

Usage:
    python search_to_llm_rag.py "<question>" <file-or-dir> [more paths ...]
    python search_to_llm_rag.py "What formats are supported?" ../../docs/source
    python search_to_llm_rag.py "How do attachments work?" ../../docs/source --llm anthropic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from all2md.search import search_documents
from all2md.search.service import SearchDocumentInput

# Extensions we'll pull in when a directory is given. all2md handles far more
# than this; keep the demo's auto-discovery to common, unambiguous document types.
DOC_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".html", ".htm", ".pdf", ".docx", ".pptx", ".epub"}


def collect_documents(paths: list[str]) -> list[SearchDocumentInput]:
    """Expand the given files/directories into SearchDocumentInput entries."""
    docs: list[SearchDocumentInput] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in DOC_EXTENSIONS:
                    docs.append(SearchDocumentInput(source=str(child)))
        elif p.is_file():
            docs.append(SearchDocumentInput(source=str(p)))
        else:
            print(f"  (skipping, not found: {raw})", file=sys.stderr)
    return docs


def build_grounded_prompt(question: str, results) -> str:
    """Assemble a citation-numbered context block + the question."""
    lines = ["Context passages:\n"]
    for i, result in enumerate(results, start=1):
        meta = dict(result.chunk.metadata)
        source = meta.get("document_path", "unknown source")
        section = meta.get("section_heading")
        label = f"{source}" + (f" -> {section}" if section else "")
        lines.append(f"[{i}] ({label})\n{result.chunk.text.strip()}\n")
    lines.append(
        "\nAnswer the question using ONLY the context passages above. "
        "Cite the passages you rely on with their bracketed numbers, e.g. [1]. "
        "If the context does not contain the answer, say so.\n"
    )
    lines.append(f"Question: {question}")
    return "\n".join(lines)


def main() -> int:
    """Index the corpus, retrieve for the question, and answer with citations."""
    parser = argparse.ArgumentParser(description="RAG over a document corpus with all2md search + Claude")
    parser.add_argument("question", help="The question to answer")
    parser.add_argument("paths", nargs="+", help="Files and/or directories to search")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    parser.add_argument(
        "--llm",
        choices=["mock", "anthropic"],
        default="mock",
        help="LLM provider: mock (no API key) or anthropic = Claude (default: mock)",
    )
    args = parser.parse_args()

    # 1. Gather and index the corpus.
    print(f"Collecting documents from: {', '.join(args.paths)}")
    documents = collect_documents(args.paths)
    if not documents:
        print("No documents found.", file=sys.stderr)
        return 1
    print(f"Indexing {len(documents)} document(s) and retrieving top {args.top_k} chunk(s)...")

    # 2. Retrieve. BM25 keyword search over structure-aware chunks with provenance.
    results = search_documents(documents, args.question, mode="keyword", top_k=args.top_k)
    if not results:
        print("No relevant passages found.")
        return 0

    print("\nRetrieved passages (with provenance):")
    print("-" * 70)
    for i, result in enumerate(results, start=1):
        meta = dict(result.chunk.metadata)
        source = meta.get("document_path", "unknown")
        section = meta.get("section_heading", "")
        snippet = result.chunk.text.strip().replace("\n", " ")
        print(f"[{i}] score={result.score:.3f}  {source}" + (f"  ({section})" if section else ""))
        print(f"    {snippet[:160]}{'...' if len(snippet) > 160 else ''}")
    print("-" * 70)

    # 3. Build the grounded prompt.
    prompt = build_grounded_prompt(args.question, results)

    # 4. Ask the model. The mock provider just echoes, so you can inspect the flow.
    from _llm_client import get_client

    if args.llm == "anthropic":
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
            return 1

    ask = get_client(args.llm)
    system = "You are a careful research assistant. Answer only from the provided context and cite sources."
    answer = ask(prompt, system=system)

    print("\nAnswer:")
    print("=" * 70)
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
