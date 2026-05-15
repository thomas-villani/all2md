# all2md corpus benchmark

A reproducible performance benchmark over a few hundred real-world documents
pulled from public corpora. Useful for spotting regressions, finding files that
break the parser, and producing comparable timing numbers across machines.

## What it does

1. **Download** — pulls a deterministic sample from each configured source into
   `benchmarks/corpus/.cache/<source>/` (gitignored).
2. **Benchmark** — runs `all2md.to_markdown()` once per cached doc, captures
   per-doc timings + errors, writes `results/results_<timestamp>.json`.
3. **Report** — renders a stratified markdown report next to the JSON
   (`results_<timestamp>.md`) with per-source/per-format tables, the top-10
   slowest docs, and a grouped failure list.

## Sources

All sources are HTTP-only — no AWS credentials required.

| Source     | Format(s)   | Sample | Notes                                                        |
| ---------- | ----------- | ------ | ------------------------------------------------------------ |
| `arxiv`    | pdf         | 30     | Recent cs.CL papers; text + math heavy.                      |
| `govdocs1` | pdf, docx   | 50     | Real-world docs harvested from .gov sites.                   |
| `poi`      | docx, pptx  | 30     | Apache POI's curated test corpus — known-tricky office docs. |
| `enron`    | eml         | 50     | Public Enron email release.                                  |

**PMC** (PubMed Central biomedical articles) is currently disabled in the
default manifest. NCBI's OA web service is not reliable for programmatic PDF
retrieval and intermittently rate-limits. The fetcher code (`fetch_pmc` in
`download.py`) is kept for reference and the source block in `corpus.toml`
can be uncommented to re-enable.

Initial download is around **~1 GB**, dominated by the Enron tarball (423 MB)
and the govdocs1 zip shard (~250 MB). Subsequent runs are no-ops once the cache
is populated.

Sample sizes, seeds, and source-specific config live in [`corpus.toml`](corpus.toml).

## Usage

From the repo root, with the `.venv` active and `all2md` installed:

```bash
# Run the whole pipeline
.venv/Scripts/python.exe -m benchmarks.corpus.run

# Just download / refresh the cache
.venv/Scripts/python.exe -m benchmarks.corpus.run download

# Benchmark only PDFs from arxiv and PMC, cap at 10 docs
.venv/Scripts/python.exe -m benchmarks.corpus.run --sources arxiv,pmc --max-docs 10

# Skip anything over 5 MB (useful for smoke runs)
.venv/Scripts/python.exe -m benchmarks.corpus.run --max-size-mb 5

# Re-render the report from the latest results JSON
.venv/Scripts/python.exe -m benchmarks.corpus.run report
```

## Flags

| Flag             | Effect                                                    |
| ---------------- | --------------------------------------------------------- |
| `mode`           | `download`, `benchmark`, `report`, or `all` (default).    |
| `--sources`      | Comma-separated source names. Subset of `corpus.toml`.    |
| `--formats`      | Comma-separated formats (e.g. `pdf,docx`).                |
| `--max-docs`     | Cap total docs benchmarked.                               |
| `--max-size-mb`  | Skip docs larger than this size.                          |
| `--manifest`     | Override path to `corpus.toml`.                           |
| `--cache-dir`    | Override cache location.                                  |
| `--results-dir`  | Override results location.                                |
| `--results-file` | (report mode) Render a specific results JSON.             |

## Inspecting conversion quality

Timing tells you whether a doc is fast; only reading the markdown tells you
whether it's *correct*. The `inspect` helper saves the markdown for a curated
subset of docs alongside a copy of the source so you can flip through them.

```bash
# 10 slowest from the latest results JSON (default)
.venv/Scripts/python.exe -m benchmarks.corpus.inspect

# 15 largest cached PDFs, regardless of timing
.venv/Scripts/python.exe -m benchmarks.corpus.inspect --criteria largest --n 15 --formats pdf

# Random sample from a specific source (good for spotting unexpected breakage)
.venv/Scripts/python.exe -m benchmarks.corpus.inspect --criteria random --sources pmc --n 5 --seed 1

# Wipe previous output before writing
.venv/Scripts/python.exe -m benchmarks.corpus.inspect --clean
```

Output lands in `inspect/<source>/`:

```
inspect/
├── _summary.md                         # index with size + timing + links
├── arxiv/
│   ├── 2605.01302v1.pdf                # copy of source
│   └── 2605.01302v1.md                 # converted markdown
└── pmc/
    └── ...
```

Open `_summary.md` in a markdown viewer that resolves relative links and you
can click straight to source/output pairs.

## Reading the report

- **Per-source / per-format tables** — counts, success rate, p50/p95 wall time,
  throughput in MB/s. Compare these against a previous run to detect regressions.
- **Slowest** — the longest-running successful conversions. These are usually
  worth profiling.
- **Failures** — grouped by exception type. New error types appearing here
  after a code change is the loudest regression signal.

## Reproducibility caveats

- The arxiv and PMC pools come from live APIs and shift over time. The seed
  controls sampling within the pool, but the pool itself drifts. Two runs on
  different days won't pick the same papers — they'll pick a comparable mix.
- govdocs1 / Enron / POI samples are stable: same shard, same git ref, same
  tarball content.
- Wall-clock timings depend on hardware and load — don't compare across
  machines, only across runs on the same machine.

## Adding a source

Add a `[sources.<name>]` block to `corpus.toml`, then implement a fetcher in
`download.py` and wire it up in the `FETCHERS` dict. Each fetcher takes a
config dict + cache dir and returns a list of `CorpusItem`. Caching via
`_read_index` / `_write_index` keeps the pipeline idempotent.
