# PDF to Word: the office documents lane

Does a contract, report or form survive `all2md x.pdf --out x.docx`? The PMC lane can't say. Its
corpus is journal articles, and it measures with layout analysis on and images extracted, which
is not what `pip install all2md[pdf]` gets by default. Most people converting a PDF to Word have
contracts, reports and forms.

## How it works

Each case is a script that builds a document in Word through
[`wordlive`](https://pypi.org/project/wordlive/). Word exports it to PDF, so **the source `.docx`
is the truth** for what the PDF should convert back into. Conversions are read back through Word
itself, and the source goes through the same reader, so both sides are measured the same way.

Three tools are scored on every case:

| Column | What it is |
|---|---|
| `ours_default` | The CLI with layout analysis off and no images: what a plain `all2md[pdf]` install gets |
| `ours_full` | Layout analysis on, images embedded |
| `word_import` | Word opening the PDF itself: the baseline people already have |

Each PDF exists tagged and untagged. The two pages are the same, and only Word's structure tags
differ, so the pair shows what tags are worth to any tool that reads them.

## What it scores

| Structure | The question |
|---|---|
| Paragraphs | Did each stay whole, get merged with its neighbors, split apart, or go missing? |
| Headings | Found, at the right relative level, and none invented? |
| Lists | Own paragraph? Real Word numbering, or typed text? Is the printed marker right? |
| Tables | Found, right shape, each cell's text in the right place? |
| Footnotes | Real footnotes, or text dropped into the body? |
| Headers and footers | Real page furniture, or a line in the middle of clause 4? |
| Pictures and charts | Still there? |
| Page | Size, margins, body font and size, page count, and the share of words in text boxes or frames |

The aim is a document that looks right **and** is easy to edit, so the last number matters as much
as the others: Word's importer often looks right by putting the text in frames.

## Running it

Windows and Word only, by hand. Word runs privately and hidden, so it doesn't touch a Word you
have open. Layout analysis needs its extra:

```bash
uv sync --frozen --extra all --extra dev --extra pdf_layout --extra ocr --extra benchmarks
uv run --with pywin32 python -m benchmarks.pdfword --out reading.json --montage ./montages
```

`--montage` writes each page side by side: source, then one column per tool. Look at these as well
as the numbers, since nothing here measures how a page looks yet.

## Posture

- **A ledger, not a gate.** Fidelity isn't gated. Readings are dated below.
- **Crash-gated on every pull request.** `tests/unit/test_pdfword_benchmark.py` converts every PDF,
  checks every digest, and shows each scorer check failing on the defect it exists to catch.
- **The self-check.** Every run reads each source again and scores it against its recorded truth.
  Anything short of perfect means the lane is wrong, and the run exits non-zero.
- **One control.** `control/plain-prose` is headings and paragraphs in one column, with nothing
  hard in it. A loss here is the simplest case of a defect, so check the converted document first:
  it is either a lane bug or the most basic form of a conversion bug.

## Regenerating the corpus

Word must be running and visible, and the run takes it over:

```bash
uv run --with pywin32 python -m benchmarks.pdfword.generate.generate
uv run --with pywin32 python -m benchmarks.pdfword.generate.generate --only form/invoice
```

**Don't run this under a timeout, and don't kill it.** It changes the author name in your Word
settings while it runs and restores it at the end. A killed run never restores it.

Each case declares what its document contains, and generation fails if Word reads back anything
else. This exists because the first probe's truth was wrong twice without anyone noticing: a style
leaked into the paragraphs after a heading, and a chart landed inside one. Either would have scored
as a conversion defect. Then look at the rendered pages too: two more defects passed their
declarations and were only caught by eye (a leftover placeholder, and columns that never balanced).

## Limits

- **Word's home turf.** Every PDF here came from Word, whose importer has an obvious advantage. Its
  column overstates how it does on PDFs from other producers. LibreOffice wasn't available when the
  corpus was built, and a set of real public PDFs is still to come.
- **Clean by construction.** A scripted corpus has no scans, no damaged fonts and no decades of
  template drift. It is the sharp instrument, and real documents will be the noisy one.
- **Small.** 13 documents show the kinds of failure and let a fix be measured. The totals are not an
  estimate of how often anything happens in the wild.
- **Structure, not looks.** The montages are for people. A visual score is the next instrument.

## Readings

### 2026-11-04: first reading

13 documents, untagged PDFs, Word 16.0. All self-checks were clean and nothing crashed.

| | `ours_default` | `ours_full` | `word_import` |
|---|---|---|---|
| Words kept, in order | 2823/2836 | 2823/2836 | 2820/2836 |
| Paragraphs left whole | 109/128 | 108/128 | 108/128 |
| Headings found | 12/52 | 46/52 | 37/52 |
| Headings at the right level | 12/52 | 12/52 | 37/52 |
| Headings invented | 0 | 11 | 9 |
| List items in their own paragraph | 32/47 | 32/47 | 38/47 |
| List items with real Word numbering | 17/47 | 17/47 | 15/47 |
| List markers printed correctly | 36/47 | 36/47 | 42/47 |
| Tables found | 7/15 | 7/15 | 15/15 |
| Tables with the right shape | 5/15 | 5/15 | 14/15 |
| Table cells right | 255/408 | 255/408 | 331/408 |
| Real footnotes | 0/4 | 0/4 | 4/4 |
| Real page headers and footers | 0/24 | 0/24 | 4/24 |
| Header or footer lines in the text | 40 | 41 | 26 |
| Pictures and charts | 0/3 | 2/3 | 2/3 |
| Page size right | 10/13 | 10/13 | 13/13 |
| Margins right | 0/13 | 0/13 | 4/13 |
| Body font right | 3/13 | 3/13 | 13/13 |
| Body size right | 3/13 | 3/13 | 12/13 |
| Pages (source: 20) | 18 | 19 | 31 |

What it shows:

- **The words are fine, the structure isn't.** All three tools keep over 99% of the words in order.
- **Layout analysis finds headings but flattens them.** It takes headings from 12 to 46 of 52, all at one
  level, and invents 11. The invented ones include a clause number split from its heading (`1.` then
  `PURPOSE`).
- **Ruled tables are in the PDF and we lose them.** `page.find_tables()` finds both of the vendor form's
  grids, but they come out as a line of labels. It reads them as 4x8 and 3x8, because the shaded label
  cells add edges, and the annual report's table as 6x12 for the same reason.
- **Borderless tables have no lines to find.** Signature blocks, key-terms tables and memo headers
  draw nothing, so these need layout inference from text positions, or a vision model.
- **A table across two pages stays two tables,** with the footer and header stranded between them.
- **Clause lists merge.** `msa-auto-numbered` keeps only 8 of 23 paragraphs whole.
- **Even plain prose splits.** Two of the control's six paragraphs break after their first line.
- **Word's importer is ahead on tables, notes, fonts and sizes, on its own PDFs.** But it runs 55% over on
  pages, loses 15 headings, puts most page furniture in the text, and has the same trouble with clauses.
- **Tags changed nothing.** Tagged and untagged scores were identical for all three columns. We
  don't read tags yet, so what reading them would be worth is still unmeasured.
- **One font per document is a coarse check.** Our 3 of 13 are the three documents that happen to use
  our default font.
