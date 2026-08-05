# PMC born-digital corpus

External ground truth for **born-digital** PDF conversion: text-layer extraction, vector
table detection, layout-derived reading order. This is the gap the OmniDocBench lane does
not cover — that corpus is 981 rasters, so it measures the OCR path.

**This directory is step 1 of that lane, and step 1 only: the corpus fetcher.** There is
no oracle and no gate here yet, by design.

## What it is

Articles come from the PMC Open Access AWS bucket, `pmc-oa-opendata`, which stores each
article under a versioned per-article prefix with the publisher PDF beside its JATS XML:

```
PMC11000001.1/PMC11000001.1.pdf     <- born-digital publisher PDF
PMC11000001.1/PMC11000001.1.xml     <- JATS ground truth, same prefix
```

JATS is publisher-produced and already structured — sections, paragraphs, captions, and
tables with real cell markup. That is why PMC was chosen over arXiv, where LaTeX means
macro expansion and moving floats and you end up fighting the ground truth.

## The manifest is the pin

This bucket has **no corpus-wide revision**. Article versions bump independently and
decade-old articles carry recent reprocessing timestamps, so there is nothing to pin the
way the OmniDocBench lane pins a Hugging Face dataset revision.

`manifest.json` plays that role: it records a SHA-256 and size for **both** the PDF and
the XML of every selected article, and it is committed. `load_corpus` never lists the
bucket — it materializes exactly what the manifest names and revalidates every byte
against it. The manifest's own digest keys the cache directory, so editing the manifest
produces a new cache rather than re-blessing files chosen under different rules.

Article bytes are never committed. Only the manifest is.

## Selection

An article is kept when **its JATS has at least one `<p>` and its PDF carries vector
drawings on some page**.

### Which half of that filter actually works — measured, and not what was expected

The build ledger settled this. Of 105 candidates: **32 rejected `no_paragraphs`, 0
rejected `no_vector_drawings`.**

A filter arm that never fires deserves suspicion, so it was checked directly. The
`no_paragraphs` articles turned out to be the scanned 19th-century back catalogue: their
JATS `<body>` holds a single `<preformat>` element containing raw OCR dump
(`"Editorial\r\nCHICAGO MEDICAL SOCIETY.\r\nJan. 18th…"`), 24–99 KB of it, with zero
structural markup. **The `<p>` test is the real discriminator, and it caught every scan
before the PDF was ever fetched** — which is also why the vector arm never got the chance
to fire.

The vector arm was then tested against three known scans on its own. It *can* reject
(`PMC10000000.1` has no drawings on any page), but it **accepted two of the three**:

| article | pages | drawings/page (median) | verdict on its own |
| --- | --- | --- | --- |
| `PMC5000000.1` (scan) | 28 | 1.0 | would **accept** ✗ |
| `PMC5000022.1` (scan) | 22 | 1.0 | would **accept** ✗ |
| `PMC10000000.1` (scan) | 11 | 0.0 | reject ✓ |
| `PMC10000015.1` (born-digital) | 5 | 6.0 | accept ✓ |
| `PMC10000026.1` (born-digital) | 16 | 5.0 | accept ✓ |
| `PMC10500000.1` (born-digital) | 2 | 15.5 | accept ✓ |

Scanned pages carry **exactly one** drawing — a page frame. `bool(page.get_drawings())`
cannot see the difference between that and a real figure; a *count* threshold could.

**This corrects the plan**, which called vector drawings "the clean discriminator" on the
strength of a nine-article spike. It is a backstop, not the discriminator. The corpus is
unaffected — every accepted article passed **both** arms, and none was admitted on the
weak arm alone — but calibrating that threshold belongs to step 2, on real data, not to a
guess made from three articles here.

### The other two calibrations, which held

- **A text layer is not a born-digital signal.** Scans ship an embedded OCR layer; a
  sample of scanned back-catalogue pages was 100% scans and 100% text-layer. Confirmed
  again above: all three known scans have text on every page.
- **`<p> > 0`, not `<sec> > 0`.** `PMC3500001.1` has 13 paragraphs and zero sections.
  Requiring sections would bias the corpus toward long research papers and quietly narrow
  what the lane measures. The build bears this out — `PMC10500000.1` was accepted with 3
  paragraphs and `PMC8500015.1` with 4.

### Sampling

Selection walks from seeds spread every 500k across the ID range, taking every 11th listed
prefix so a run of same-issue articles from one publisher cannot stand in for a corpus.
`limit` on the load side selects an **evenly spaced** subset for the same reason, never
the first N.

**The scanned material is not confined to the front of the ID range** — another
correction. `PMC10000000.1`, a 2023-era identifier, is a scanned 1890s medical society
editorial: back-catalogue digitization projects receive *modern* PMCIDs when deposited.
Sampling off the front is still wrong, but spreading the seeds is not by itself protection
against scans; the `<p>` filter is.

Note also that bucket listing is **lexicographic, not numeric**: `start-after=PMC1000000`
lands on `PMC10000000`, because an 8-digit id sorts before a 7-digit one. Seeds are
`start-after` anchors, not positions in the ID range.

## Rejections are recorded; network failures are not rejections

Every dropped candidate is written into the manifest by article id with its reason. A
silent filter is the same defect as a silent truncation.

Network failures are tracked **separately** and never enter the rejection ledger. A
rejection is a statement about an article; an unreachable host is a statement about the
run. A build that loses more than 10% of its candidates to network failure aborts rather
than committing a manifest that a bad link quietly thinned out.

## Usage

```bash
# Summarize the committed manifest. No network access.
.venv/Scripts/python.exe -m benchmarks.pmc show

# Materialize and verify the pinned corpus.
.venv/Scripts/python.exe -m benchmarks.pmc load
.venv/Scripts/python.exe -m benchmarks.pmc load --limit 10     # evenly spaced subset

# Rebuild the manifest by walking the bucket. Run by hand; commit the result.
.venv/Scripts/python.exe -m benchmarks.pmc build --per-seed 3
```

## What comes next, and what must not be assumed

**Step 2 — characterize before designing the oracle.** Run the corpus characterization
over the built corpus and confirm the aggregate matches the spike (vector drawings high,
single-full-page-image ~0). If it disagrees, stop and find out why.

The filter guarantees *at least one* vector page per article, so it partly determines that
result. What it does not determine — and what step 2 actually checks — is the aggregate
*distribution* across all pages.

**Carry the finding above into step 2:** a high aggregate vector-drawing rate is *not*
evidence that the corpus is born-digital, because scans score on that metric too. Pair it
with drawings-per-page and with the ≥80%-page-area image test, and set the threshold
there rather than assuming this one.

This is also why the manifest deliberately records **no PDF page traits**. Reading the
filter's own premise back out of the manifest and calling it characterization would be a
measurement that cannot fail.

**Step 3 — the oracle, and the alignment decision.** JATS describes a whole *article*
with no page boundaries; OmniDocBench annotates *pages*. Either this lane scores
per-article, or article truth is projected onto pages. That decision is **open and
reserved**, and this fetcher is deliberately agnostic to it: it exposes whole articles and
no page structure.

## Licences

The OA subset is not uniformly licensed. Each article's licence is read out of its own
JATS `ali:license_ref`/`license` element and recorded in the manifest. `show` prints the
breakdown. Nothing here redistributes article content — only digests.
