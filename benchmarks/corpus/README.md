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

| Source     | Format(s)   | Sample | Reproducible | Notes                                                        |
| ---------- | ----------- | ------ | ------------ | ------------------------------------------------------------ |
| `arxiv`    | pdf         | 30     | **no**       | Recent cs.CL papers; text + math heavy.                      |
| `govdocs1` | pdf, docx   | 50     | yes          | Real-world docs harvested from .gov sites.                   |
| `poi`      | docx, pptx  | 30     | **no**       | Apache POI's curated test corpus — known-tricky office docs. |
| `enron`    | eml         | 50     | yes          | Public Enron email release.                                  |

### Reproducibility, and why only half the corpus is gated

Sampling is seeded (`random.Random(seed).sample`), which is deterministic **given a
fixed pool**. Two of these pools are not fixed:

- **`arxiv`** queries the live API sorted by `submittedDate` descending, so the pool
  is "the 200 most recent cs.CL papers" and changes every day.
- **`poi`** reads `apache/poi` at `ref = trunk`, which moves whenever POI edits its
  test data.

This is invisible locally: the fetchers short-circuit on a cached `_index.json`, so
once your machine has run the benchmark its document set never changes again. CI gets
a cold cache every run and re-resolves against upstream.

So `reproducible = true` in `corpus.toml` marks the sources whose sample is fixed, and
**only those are gated** — comparing a baseline against a corpus that changed
composition reports document-mix noise as a regression. The other two still run and
still appear in the report; they're an exploratory signal, not a ratchet.

Making all four gateable would need a committed lockfile of resolved ids + content
hashes, with `poi` pinned to a SHA. Note arxiv revises PDFs (`v1` → `v2`) under the
same id, so ids alone would not be enough.

Run just the gated half with `--only-reproducible` (this is what CI does):

```bash
.venv/Scripts/python.exe -m benchmarks.corpus.run --only-reproducible
```

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

# Delete the cached corpus (~1 GB)
.venv/Scripts/python.exe -m benchmarks.corpus.run purge

# Full pipeline, then clean up the cache (useful in CI / ephemeral disks)
.venv/Scripts/python.exe -m benchmarks.corpus.run --purge-after
```

## Flags

| Flag                 | Effect                                                              |
| -------------------- | ------------------------------------------------------------------- |
| `mode`               | `download`, `benchmark`, `report`, `all` (default), or `purge`.     |
| `--sources`          | Comma-separated source names. Subset of `corpus.toml`.              |
| `--only-reproducible`| Restrict to sources whose sample is fixed across cold runs (gated). |
| `--formats`          | Comma-separated formats (e.g. `pdf,docx`).                          |
| `--max-docs`         | Cap total docs benchmarked.                                         |
| `--max-size-mb`      | Skip docs larger than this size.                                    |
| `--manifest`         | Override path to `corpus.toml`.                                     |
| `--cache-dir`        | Override cache location.                                            |
| `--results-dir`      | Override results location.                                          |
| `--results-file`     | (report mode) Render a specific results JSON.                       |
| `--use-layout-model` | Enable pymupdf-layout for PDF parsing (off by default; see below).  |
| `--purge-after`      | Delete the corpus cache after the benchmark / pipeline finishes.    |

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
- **POI is not stable either**, despite what this section used to claim: `ref = trunk`
  is a moving branch, not a pinned commit, so the file list changes as POI edits its
  test data. Only govdocs1 (fixed shard of a frozen archive) and Enron (frozen
  tarball) hand back the same documents on every cold run.
- A warm `.cache/` hides all of the above — the fetchers reuse `_index.json` and never
  re-resolve. Your machine will look perfectly reproducible while CI is not.
- Wall-clock timings depend on hardware and load — don't compare across
  machines, only across runs on the same machine.

## Adding a source

Add a `[sources.<name>]` block to `corpus.toml`, then implement a fetcher in
`download.py` and wire it up in the `FETCHERS` dict. Each fetcher takes a
config dict + cache dir and returns a list of `CorpusItem`. Caching via
`_read_index` / `_write_index` keeps the pipeline idempotent.

## The gate

`benchmarks/corpus/gate.py` turns a results JSON into a pass/fail verdict, run
weekly by the `Corpus Fidelity Gate` workflow (and on dispatch).

It gates **which documents fail to convert** — a set of names, compared exactly, with
no tolerance and no runner variance to argue about. It deliberately does **not** gate
throughput: that needs a variance study on the runners it would run on before any
threshold is defensible, and a flaky gate gets disabled, which leaves the appearance
of coverage rather than coverage.

Four ways to go red, so the baseline can't rot in any direction:

| status | meaning |
| --- | --- |
| `NEW_FAILURE` | a document failed that the baseline doesn't accept |
| `FIXED` | an accepted failure now converts — record the win |
| `STALE` | the baseline accepts a document no longer in the corpus |
| `MISSING_DOCS` | a gated source returned fewer docs than recorded |

That last one is not about failures at all. A half-succeeded download produces fewer
documents, therefore fewer failures, therefore a green gate — so the most likely
infrastructure fault in the whole pipeline would read as success. The gate also
refuses to report a pass when *no* gated sources are present, for the same reason.

Bootstrap or re-record a baseline from a run:

```bash
.venv/Scripts/python.exe -m benchmarks.corpus.gate <results.json> --emit-baseline \
  > benchmarks/corpus/corpus_baseline.json
```

Then replace each `TODO` reason with a real justification — a machine can record that
something failed, but only a person can say whether it's acceptable.

The committed baseline was recorded on 2026-07-26 from
[run 30183702769](https://github.com/thomas-villani/all2md/actions/runs/30183702769)
against 1.10.0, and its allowlist is **empty**: all 100 gated documents converted
without raising. So any entry appearing in it later is a regression with a name, and
the right response is a fix rather than a line in the list.

Note what the gated half actually covers: 50 PDFs and 50 emails. `corpus.toml` asks
govdocs1 for `pdf` and `docx`, but govdocs1 is a 2009 harvest of `.gov` sites and
carries legacy `.doc`, so the `docx` request matches almost nothing. The gate is real,
it is just narrower than the manifest reads.
