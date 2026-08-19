- **Third-party comparison lane** (`benchmarks/comparison/`): scores pymupdf4llm and
  Docling with the PMC lane's own text-survival and invented-text instruments, on the
  held-out 110-article corpus, with every tool's markdown re-parsed through one
  normalization path. Ships the 2026-08-19 reading (`results-2026-08-19.json`), pinned
  baseline versions, and a lost-block diff (`lost_blocks.py`) that names the truth
  blocks a baseline recovers that all2md loses — the diff that produced #405 and #406.
  Run by hand only; never in CI.
