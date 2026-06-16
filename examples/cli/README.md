# CLI pipeline examples (bash + PowerShell)

`all2md` is a powerful command-line tool, not just a library. These scripts show
how to drop it into shell pipelines and batch jobs for everyday document work and
for feeding documents to LLMs. Every concept ships as a **bash** (`.sh`) and a
**PowerShell** (`.ps1`) version, so you can use whichever your platform prefers.

> On Windows, the `.sh` scripts run under **Git Bash** or **WSL**; the `.ps1`
> scripts run in **PowerShell 7+**. All examples assume `all2md` is on your `PATH`
> (`pip install all2md`). The `search`/`diff`/`rag` bash scripts also use `jq`;
> the PowerShell versions parse JSON natively with `ConvertFrom-Json`.

## Scripts, simplest to most involved

| Script | What it shows |
| ------ | ------------- |
| `convert-and-pipe` | Convert to stdout, any-to-any (`--to`), stdin with `-`, attachment modes, piping into other tools |
| `batch-convert` | Whole-folder conversion: built-in batch (`--recursive --skip-errors --preserve-structure`), `--collate`, and parallel `find`/`xargs` (bash) / `ForEach-Object -Parallel` (PowerShell) |
| `extract-and-navigate` | Cheap reading of big docs: `--outline`, `--line-numbers`, `--extract "Section"`, `--extract "line:A-B"` |
| `grep-binary-docs` | `all2md grep` *inside* PDF/DOCX/PPTX that plain grep can't read |
| `search-corpus` | Ranked `all2md search --json` over a corpus, post-processed with `jq` / `ConvertFrom-Json`; provenance per hit |
| `diff-in-ci` | Semantic, cross-format `all2md diff` as a CI gate (unified for humans, JSON to fail the build) |
| `llm-minify-pipe` | `all2md llm-minify` to shrink a document to token-lean text before an LLM call |
| `rag-ingest` | Build a grounded, citation-numbered LLM prompt from retrieved chunks (shell-only sibling of `../llm/search_to_llm_rag.py`) |

## Quick start

```bash
# bash / Git Bash / WSL
./convert-and-pipe.sh report.pdf
./extract-and-navigate.sh manual.pdf
./search-corpus.sh "revenue recognition" ./reports
./diff-in-ci.sh v1.docx v2.docx
```

```powershell
# PowerShell 7+
./convert-and-pipe.ps1 report.pdf
./extract-and-navigate.ps1 manual.pdf
./search-corpus.ps1 "revenue recognition" ./reports
./diff-in-ci.ps1 v1.docx v2.docx
```

## Related

- Python equivalents and deeper workflows live in `../python/` and `../llm/`.
- The full CLI reference is in the project docs (`docs/source/cli.rst`) and via
  `all2md --help` / `all2md <command> --help`.
