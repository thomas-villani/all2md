# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **INI renderer: `DEFAULT` section no longer fails to render.** `configparser`
  reserves `DEFAULT`, so `add_section("DEFAULT")` raises `ValueError` — which meant
  any document whose keys landed in the default section (orphan key/value lists with
  no heading, or a heading literally named `DEFAULT`) aborted the whole conversion
  with a `RenderingError`. Keys are now set on the parser directly for that section.
  Thanks [@santhreal](https://github.com/santhreal) (#116).
- **Org renderer: table header separators now end with a newline.** The header rule
  and the first body row were emitted glued together (`|---|---|| 1 | 2 |`), which
  is not a valid Org table and loses every body cell when re-parsed. Thanks
  [@santhreal](https://github.com/santhreal) (#117).
- **CSV renderer: line breaks inside table cells survive export.** `LineBreak` nodes
  and `<br>` HTML inlines were dropped when flattening a cell to text, silently
  joining the two lines. They now emit a newline, which the CSV writer quotes.
  Thanks [@santhreal](https://github.com/santhreal) (#118).
- **DokuWiki renderer: empty list items keep their bullet.** An empty `ListItem`
  produced no output at all, so `- a` / `-` / `- c` rendered as two bullets instead
  of three and shifted the list. Matches the Markdown/MediaWiki/AsciiDoc/RST
  renderers, which already preserve the blank bullet. Thanks
  [@santhreal](https://github.com/santhreal) (#119).
- **RTF renderer: lists nested in block quotes and definitions no longer crash.**
  pyth's `List` subclasses `Paragraph`, so prefixing a paragraph rewrapped a nested
  list as `Paragraph(content=[ListEntry…])` and raised `TypeError` — any Markdown
  with a list inside a block quote failed to convert. Thanks
  [@santhreal](https://github.com/santhreal) (#122).
- **AsciiDoc parser: escaped braces in an attribute-ref shape no longer hang.**
  Input as small as `{\{}` spun forever: escape preprocessing left a `{…}` shape, the
  combined inline pattern matched at the cursor, every handler declined, and the
  fallback advanced by zero. An unclaimed match is now consumed as literal text.
  Thanks [@santhreal](https://github.com/santhreal) (#123).
- **AsciiDoc parser: cross-reference targets restore their escapes.** `<<id>>` and
  `<<id,text>>` skipped escape postprocessing that the sibling `link:` branch already
  did, leaking internal placeholders into the URL and link text. Thanks
  [@santhreal](https://github.com/santhreal) (#124).
- **AsciiDoc parser: column spans survive a space after the pipe.** The span regex ran
  against the stripped cell but sliced the unstripped one, so `| 2+| spans two` left a
  stray `+` cell and split the row wrong. Thanks
  [@santhreal](https://github.com/santhreal) (#130).
- **AsciiDoc renderer: merged table cells keep their spans.** `colspan`/`rowspan` were
  dropped entirely, so an HTML table with merged cells lost its structure on
  conversion even though the AsciiDoc parser already understood `2+|`, `.3+|`, and
  `2.3+|`. A leading cell's spec replaces the row-opening `|`, since a spec binds to
  the cell after the pipe it precedes. Thanks
  [@santhreal](https://github.com/santhreal) (#131).
- **MediaWiki parser: literal pipes in table cells survive.** Cell-attribute stripping
  matched any cell whose text merely contained a `|`, so `pipe: a|b` became `b` and
  `[[Target|label]]` lost its target. A leading segment is now treated as attributes
  only when it contains `=`. Thanks [@santhreal](https://github.com/santhreal) (#125).
- **MediaWiki parser: table captions are read from `|+` lines.** `|+` was skipped
  outright, so `Table.caption` was always `None` and real wikitable captions were lost
  on parse and round-trip even though the renderer already emitted them. Thanks
  [@santhreal](https://github.com/santhreal) (#132).
- **MediaWiki renderer: table captions stay on one line.** A caption containing a
  newline (common from HTML `<caption>`) split across lines, which is invalid
  wikitable markup and dropped the remainder of the caption. Thanks
  [@santhreal](https://github.com/santhreal) (#129).
- **DokuWiki renderer: table column spans are emitted.** `TableCell.colspan` was
  ignored, so merged columns were lost; DokuWiki expresses a span with empty
  continuation cells (`| Wide || Tall |`). Thanks
  [@santhreal](https://github.com/santhreal) (#127).
- **Textile renderer: block children of a list item are separated properly.** Children
  were joined with a single space, so a table after a list item's lead paragraph
  became `* intro |_.H|` — ordinary text to Textile, and the table vanished on
  round-trip. Thanks [@santhreal](https://github.com/santhreal) (#126).
- **AST serialization: `Comment`, `CommentInline`, and `Mark` nodes are supported.**
  The dispatch tables had no entries for them, so serializing any document containing
  a Markdown HTML comment, `==mark==`, an AsciiDoc `//` comment, or an RST `..`
  comment raised `ValueError: Unknown node type for serialization`. Thanks
  [@santhreal](https://github.com/santhreal) (#128).

### Changed

- CI: bumped `actions/setup-python` 6 → 7 and `actions/setup-node` 6 → 7 (#120, #121).

## [1.9.0] - 2026-07-15

### Added

- **Conversion optimizer (`all2md optimize`).** Converts a document many times under
  different converter settings and reports the ones that recover the most well-formed
  structure — emitted both as a runnable command and as a `.all2md.toml` snippet.
  Built for the documents that need it most (the gnarly PDF with no known-good output
  to diff against), so the objective is reference-free — and it is deliberately
  neither of the two existing scores. The **confidence** score is a saturating
  breakage detector: on anything not visibly broken it pins to `100` regardless of
  settings, so it has no gradient to search (measured: 16 option combinations on a
  two-column PDF produced *one* distinct confidence score while the parsed AST
  produced *four* distinct outcomes). The **round-trip** score measures the renderer,
  not the parser — a garbled table round-trips through Markdown perfectly. So
  `all2md.optimize` scores the parsed AST directly.

  **Body text gates the score rather than contributing to it.** Losing a paragraph is
  data loss; leaving a running header in is an annoyance, and the two are not
  interchangeable at any exchange rate — so a candidate's body-text retention
  *multiplies* its fitness (cubed), and no amount of tidiness buys back deleted
  content. The weighted dimensions are the ones that are genuinely tradeable: tables
  (scored as quality-weighted *recall* — filled cells discounted by shape regularity,
  so a hallucinated table earns almost nothing while a missed real one still costs its
  cells), structure, and cleanliness (how much repeated furniture the setting left
  behind, where furniture is content that repeats across a substantial fraction of the
  document's pages).

  The search is cheap by construction — the named presets first, then coordinate
  descent, which costs `sum(len(values))` conversions instead of a full grid's
  `prod(len(values))`. It is still tens of full conversions, though, and a PDF page
  costs about a second to parse, so `--sample-pages` tunes against a slice of a long
  document and `--cache` makes repeat runs nearly free (18.5s → 0.3s warm, on a
  31-candidate run); the command warns up front when it is about to tune a whole
  document. Available from Python as `all2md.optimize_options(source, ...)` (with
  `optimizable_formats()`), and from the command line as `all2md optimize <file>`
  (`--rounds`, `--sample-pages`, `--no-presets`, `--top`, `--out`, `--json`). Tunable
  formats: `pdf`, `html`, `docx`. The reported fitness ranks candidates *against each
  other* and is not an absolute quality score — `all2md report` and `all2md roundtrip`
  remain the scores for that.
- **Round-trip fidelity scoring (`all2md roundtrip`).** Converts a document to
  another format, parses it straight back, and scores the structure that
  survived. Unlike the confidence report this comparison has a ground truth —
  the source document itself — so a lossless round trip scores exactly `100` and
  anything less is a concrete, itemized loss. Five dimensions are scored against
  independent alignments and combined: `structure` (0.40 — heading levels, list
  nesting, table placement), `text` (0.30 — the document-wide word stream),
  `inline` (0.15), `tables` (0.10) and `references` (0.05); dimensions the source
  does not exercise are dropped and the rest renormalized, so a document with no
  tables is neither rewarded nor punished for the tables it lacks. Alongside the
  score the report lists concrete `StructuralDelta` incidents ("heading(h1) ->
  paragraph", "table 1: 4x3 -> 4x2", "3 of 229 words") so a low score is
  actionable. Tight/loose list items and nested-paragraph artifacts are
  normalized away, so format-legal spelling differences do not read as loss.
  Available from Python as `all2md.roundtrip_report(source, via=...)` (with
  `roundtrippable_formats()` listing the 24 valid `via` formats) and from the
  command line as `all2md roundtrip <file>` (aligned card by default, `--via` to
  pick the intermediate format, `--json`, `--fail-under SCORE` as a CI gate,
  `--max-deltas N`, `--format` to override source detection for stdin). The score
  responds to converter options, which is what makes it usable as the fitness
  function for the planned `all2md optimize`.
- **Conversion confidence report ("quality card").** Every conversion now
  attaches a reference-free `ConfidenceReport` to `Document.metadata['confidence']`
  — a `0-100` `score`, a `high`/`medium`/`low` `band`, the signals behind it, and
  the discrete degraded-content incidents the converter recorded — surfacing
  sanity signals converters previously computed and threw away. PDF reports
  meaningful-text density (`chars_per_page`), OCR reliance (`ocr_page_fraction`),
  detected/rejected table counts (each rejected non-tabular region is recorded
  with its reason), and running-heading demotions; DOCX reports table/image
  counts and flags silently-dropped embedded objects, charts, and SmartArt. The
  single `score` doubles as an optimizer fitness function (no ground-truth needed).
  Read it programmatically with `all2md.confidence_report(source)` or from the
  command line with the new `all2md report <file>` verb (aligned pretty card by
  default, `--json` for machine use, `--fail-under SCORE` as a CI gate). Any
  parser can contribute incidents via `BaseParser._record_degraded`; container
  formats (`zip`, archives) already flag members that could not be parsed.
- **Opt-in conversion cache (`--cache`).** `grep`, `search`, `chunk`, `view`,
  `report`, `roundtrip` and `optimize` all take a `--cache` flag (and
  `--cache-dir DIR`) that stashes parsed documents on
  disk so repeated runs over unchanged files skip the expensive parse step. The
  cache is keyed by a fingerprint over the source file (path + size + mtime), the
  resolved format and parser options, and the all2md version + AST schema — so a
  changed file, changed options, or a version bump all miss cleanly rather than
  serving a stale AST. Off by default; also enable globally with `ALL2MD_CACHE=1`,
  and point it anywhere with `ALL2MD_CACHE_DIR` (defaults to the per-OS user cache
  directory via `platformdirs`). Exposed programmatically as
  `all2md.conversion_cache.use_conversion_cache(...)`, which transparently caches
  every `to_ast()` call made inside the context.
- **DOCX run-level character styles round-trip.** Named character styles on runs
  ("Intense Emphasis", "Quote Char", a custom style, …) are now captured on the
  AST inline node's `metadata['source_style']` and re-applied when rendering back
  to DOCX with a template — the run-level analog of the existing paragraph
  `source_style` handling. This preserves run styling across a DOCX → AST → DOCX
  round-trip (and combines with direct bold/italic). Character styles have no
  Markdown representation, so the name rides only the AST and is dropped on
  Markdown serialization; without a template that defines the style, application
  falls through silently, so default output is unchanged.

### Fixed

- **Markdown: footnotes round-trip as Markdown under the default flavor.** A footnote
  reference and its definition rendered to raw HTML on the default flavor, which the
  default `html_passthrough` policy then escaped on the next pass — so a footnote did
  not survive a `markdown → markdown` round trip. Footnotes now render in Markdown
  syntax by default and round-trip intact.
- **Markdown: inline marks, superscript and subscript are flavor-aware and round-trip
  by default.** Highlight (`==text==`), superscript (`^text^`) and subscript (`~text~`)
  defaulted to HTML tags that the default passthrough policy escaped on reparse. They
  now default to the roundtrip-safe Markdown spelling (flavors that support the syntax
  natively emit it directly); set the corresponding `*_mode` option to `html` for
  wider display support.
- **Markdown: underline (`^^text^^`) and non-GFM strikethrough round-trip instead of
  self-escaping.** Underline rendered `<u>…</u>` by default and the `<del>` fallback
  for flavors without `~~` did the same, both of which the default passthrough policy
  escaped to `&lt;u&gt;…` on the next pass. Underline now defaults to the pymdownx
  `^^text^^` insert spelling (the old `"markdown"` mode emitted `__…__`, which every
  flavor parses as **bold**, silently losing the underline); strikethrough on a flavor
  without `~~` now emits `~~` by default. Explicit `html` still opts into the tags.
- **Markdown: inline `$$…$$` display math is kept, not dropped.** An inline `$$…$$`
  span was silently discarded instead of being preserved as display math.
- **Markdown: a list survives an admonition that degrades to a labelled quote.** When
  an admonition inside a list item degraded to a labelled block quote, the surrounding
  list was broken apart; it now stays intact.
- **PDF: prose from *every* rejected table is preserved, not just degenerate grids.**
  Text inside a detected table's bbox is stripped from the ordinary text stream before
  the table is validated, so a rejection path that returned `None` deleted that text.
  A prior fix covered only degenerate (1×N / N×1) grids; the oversized-grid,
  mostly-empty, uniform-cell and dot-leader-TOC rejections still dropped a
  sparse-but-real table (a financial statement, a form) or a table of contents. All
  four now demote the region to a paragraph.
- **Round-trip scoring counts code, math and raw-HTML block content.** `CodeBlock`,
  `MathBlock`, `HTMLBlock` and their inline siblings keep their payload in a plain
  string with no `Text` children, so the text dimension never compared it — a round
  trip that dropped or mangled an entire code block scored a false `100`. Their content
  (and image alt text) is now part of the comparison.
- **Confidence: conversions with no quality instrumentation report `not_assessed`,
  not a false `high`.** Formats that emit no scored signals and no degraded events
  (docx, pptx, html) scored a vacuous `100/HIGH`, so a mangled `.docx` read as verified
  clean. Such a report is now banded `not_assessed`; the numeric score is unchanged.
- **DOCX: title-promotion inversion clamps heading levels at 6.** Demoting the headings
  after a leading title used an unbounded `level += 1`, pushing an H6 to an out-of-spec
  level 7 that serialization and the round-trip scorer saw. It is now clamped, mirroring
  the forward transform's bottom clamp.
- **`all2md optimize` searches only valid `figures_parsing` / `details_parsing` values.**
  The HTML search space listed values (`figure`, `image`, `details`, `content`) that no
  parser accepts; they were silently no-ops and could be written into a recommended
  `.all2md.toml`. Replaced with valid choices, guarded by a test.
- **Markdown: multi-paragraph and multi-line list items round-trip without collapsing.**
  Three problems in the same surface conspired to flatten lists on a Markdown round trip:

  *Loose lists were read as tight.* mistune 3.x carries the loose/tight flag on the list
  token itself, not in `attrs`; reading it only from `attrs` marked every list tight, so the
  renderer dropped the blank lines that separate a loose item's paragraphs and they merged
  into one on reparse.

  *Continuation lines were emitted at column zero.* A list item whose content wrapped across
  several lines (soft-wrapped source, or a multi-paragraph item) indented only its first line;
  every continuation went to the margin, where it reparses as a lazy continuation that
  collapses the wrapped lines together — or, when a nested block landed there, breaks the item
  apart. Code blocks and block quotes inside a list item had the same flaw and could escape to
  column zero as siblings of the list. Continuation lines, and nested code/quote blocks, now
  carry the item's indentation.

  *A nested list as an item's first child double-indented.* The first-child render path
  cleared the indent stacks but left the in-list flag set, so a nested list added its own
  indent level on top of the marker — rendering `1. - x` as `1.     - x`. It now renders flush
  and is shifted to the marker's content column like any other continuation.

  A task checkbox (`[ ] `) is treated as first-line content rather than marker width, so
  continuations align to the list marker and don't over-indent into an accidental code block.
  Net effect: a document like a nested ordered/task list with wrapped prose now survives
  `markdown → markdown` unchanged (idempotent), where before it flattened onto single lines.
- **DOCX: inline code and block quotes survive the Markdown round trip.** Two independent
  renderer/parser asymmetries on the `md → docx → md` path, both filed as #71:

  *Inline code was dropped.* The renderer emitted a `` `code` `` run with a monospace font
  but no named character style, so the parser — which recovers inline styling from run
  *styles*, not fonts — had nothing to key on, and `` `inline code` `` came back as plain
  `inline code`. The renderer now tags inline-code runs with a `Verbatim Char` character
  style (matching pandoc's name; created on demand and only when `use_styles` is on), and the
  parser maps that style back to a `Code` node. Recognized style names are configurable via
  the new `code_char_style_names` DOCX parser option.

  *A block quote came back as a bullet list.* The renderer wrote the quoted paragraph as a
  `Normal` paragraph with a left indent, and the parser read that indent as list nesting — so
  `> a quoted line` silently became `* a quoted line`, which looks intentional and is arguably
  worse than dropping it. The renderer now applies Word's built-in `Quote` paragraph style
  (which also makes the generated document look right in Word) and, for a single level, no
  longer sets a bare indent that the parser would misread; the parser maps `Quote` /
  `Intense Quote` back to a `BlockQuote`, coalescing adjacent quote paragraphs into one quote.
  Recognized style names are configurable via the new `quote_style_names` DOCX parser option.

  Together these take `all2md roundtrip … --via docx` on a document with inline code and a
  quote from `structure: 33 / inline: 0` to `100 / 100`. Both recoveries require styles
  (`use_styles=True`, the default); with styles disabled the render still falls back to
  font-and-indent as before.
- **DOCX: a document title survives the Markdown round trip.** Rendering to DOCX applies
  `TitlePromotionTransform` — a leading `# H1` becomes Word's **Title** style and every
  following heading is promoted one level (H2 → "Heading 1") so the document reads correctly
  in Word. The parser had no inverse: it mapped the `Title` style to a plain paragraph and
  left the promoted headings where they were, so `# Title` / `## Section` came back as body
  text plus `# Section` — the title silently demoted to prose and every heading shifted up a
  level (`all2md roundtrip … --via docx` scored `structure: 67`). The parser now maps Word's
  `Title` back to `Heading(level=1, is_title=True)` and, when that title leads the document,
  demotes the following headings one level to undo the promotion — making the transform
  exactly invertible (`structure: 100`) while keeping the nice-looking Word output. Word's
  `Title` is semantically the document title, so this also gives natively-authored Word
  documents a sensible outline (Title → `#`, its Heading 1 → `##`).
- **HTML: loose list items no longer grow a paragraph-inside-a-paragraph.** A *loose* item —
  one whose `<li>` already holds a block, `<li><p>x</p></li>` — was parsed to
  `ListItem > Paragraph > Paragraph > Text`, because `_process_list_item_to_ast` wrapped every
  item's content in a freshly synthesized `Paragraph` whether or not that content was already a
  block. No format represents a paragraph nested directly in a paragraph, so the inner node was
  pure artifact: a consumer walking the AST saw a different `ListItem` shape depending on how the
  source HTML happened to be written, and — because our own HTML renderer emits `<li><p>…</p></li>`
  — an `html → html` round trip accreted one extra `Paragraph` per item on every pass. The parser
  now adopts a `<li>`'s block children directly and only synthesizes a wrapping `Paragraph` for
  loose inline runs, so `<li><p>x</p></li>` and `<li>x</li>` produce the identical AST and the
  round trip is stable.
- **String page ranges select the pages you asked for.** `validate_page_range()` converted
  1-based page numbers to 0-based **twice** on the string path: `parse_page_ranges()` already
  returns 0-based indices, and the result was then decremented again. So every string range
  was wrong — one including page 1 (`pages="1-3"`) raised `Invalid page number: 0`, and every
  other one *silently returned the wrong pages*, shifted by one: `PdfOptions(pages="2")` gave
  you page 1. The list form (`pages=[2]`) was correct, and the tests only ever exercised
  lists, so nothing caught it. The string path now returns the already-0-based parse directly.

  Two adjacent failures went with it. **The CLI could not express the ranges the option
  documents:** `--pdf-pages 1-3` was rejected with "Expected comma-separated integers",
  because the builder resolved `pages: list[int] | str | None` to just `list[int]` — it takes
  the first non-`None` member of a union — and ignored the field's own `"type": str` metadata,
  which only `int` and `float` were honored. An explicit metadata type now overrides inference,
  so the page spec reaches the converter verbatim. (`--pdf-pages` is the only option in the
  library whose declared metadata type differs from its annotation, so nothing else changes.
  `--save-config` now records the spec as written — `"pdf.pages": "1-3"` — and configs
  carrying the older list form still load.) And **a range that selected nothing converted the
  whole document**: `pages="99"` on a 10-page PDF parsed to an empty selection, which
  `pdf.py` read as "no selection, use every page". It now raises.
- **HTML: tables no longer vanish inside `<figure>` or inline layout wrappers.** On a real
  arXiv paper (LaTeXML output), **13 tables / 150 rows / 794 cells parsed to 3 empty tables
  and not a single row**. The captions survived, so the output still looked plausible. Two
  independent defects, either of which was enough to lose every table in the document:

  `<figure>` was special-cased to images — `_process_figure_to_ast` looked for a
  `<figcaption>` and an `<img>` and built its result from those two alone, so any other child
  (a `<table>`, a `<pre>`, a `<video>`) was never visited. With a caption present it returned
  a `BlockQuote` holding only the caption; with neither image nor caption it returned `None`
  and dropped the figure whole. A figure is a *container that carries a caption* — HTML5
  recommends it for captioning tables and code listings too — so its content now goes through
  the normal block dispatch, whatever that content happens to be.

  Separately, **a block element inside an inline element was discarded outright**. An inline
  context has nowhere to put a block, so `_process_children_to_inline` skipped it behind a
  `logger.debug` whose message said this "should not happen with proper block/inline
  separation". It happens constantly: LaTeXML scales an oversized table by wrapping it in
  `<span class="ltx_transformed_inner" style="transform:scale(0.7)">`, and a `<table>` inside
  a `<span>` was lost — figure or no figure. An inline element wrapping block content is a
  layout wrapper, not inline content, and is now processed as a block container. Where a
  block genuinely cannot be kept (`<a><div>…</div></a>`, since a link cannot hold a block),
  the drop is now recorded as a degraded-content incident instead of being silent, so
  `all2md report` can see it.

  The same paper now parses to **13 tables, 150 rows, 794 cells** — every row and cell in the
  source. Four of the six documented `figures_parsing` modes were also unimplemented and fell
  through to the blockquote branch: `skip` did not skip, `paragraph` returned a blockquote,
  and `caption_only` kept the image. All six now behave as documented, and
  `image_with_caption` no longer drops a caption it cannot fold into the image's alt text.
- **`all2md optimize` no longer recommends breaking words in half.** The objective's text
  signal was a count of whitespace-separated tokens, which *rewards* a parse that fragments
  words — chop one word into two and the document appears to contain more text. When
  `merge_hyphenated_words` began working on native-text PDFs (it was previously a silent
  no-op), the optimizer immediately found this: repairing `hyphen-` + `ation` into
  `hyphenation` joins two tokens into one and so read as *losing a word*, and it recommended
  disabling the repair on **17 of 17** real papers. Judged against the publisher's HTML
  rendering, that advice made every one of them measurably worse (mean −0.03, worst −0.066).
  Word counts now go through `content_tokens()`, which rejoins hyphen-broken tokens and drops
  hyphens, so a fragmented parse and a clean one produce an *identical* count and the metric
  cannot have a preference. This is the third time this exploit surfaced (previously via
  `consolidate_inline_formatting`, where "hello" was counted as "hel" + "lo"); fixing the
  metric rather than the setting closes the whole class.

  Relatedly, `KNOBS` is now guarded by `FORBIDDEN_KNOBS`, because two categories of setting
  look tunable and are not. **Correctness settings** (`merge_hyphenated_words`,
  `consolidate_inline_formatting`) have one right value — there is no document for which the
  broken word is the better answer, so there is nothing to search. **Content-inclusion
  preferences** (`include_comments`) change *what the user asked for* rather than how well it
  was extracted; the objective rewards recovering more content and comments are words, so it
  would have recommended `include_comments=True` on essentially every DOCX — advice that
  leaks reviewer comments the author never meant to publish.
- **`auto_trim_headers_footers` now removes running headers and footers.** It largely
  did not. Three defects compounded, and each was hidden by the optional `pdf_layout`
  extra, which labels headers and footers directly — so on a development machine with
  the extra installed the feature looked fine, while a stock install got almost nothing.
  (1) Candidates were keyed on their **exact text**, so `Page 1 of 12` and `Page 2 of 12`
  looked like two unrelated blocks, neither ever repeated, and a footer carrying a page
  number — very nearly every running footer there is — could never be detected at all.
  Digit runs are now collapsed when keying, so a running footer is recognized as one.
  (2) Detection refused to run on documents with fewer than **three pages**, making the
  option a silent no-op on every two-page document; two pages are enough to show
  repetition. (3) The zone filter dropped any block that *began* inside the header zone,
  rather than one that lies **entirely** within it — so a body paragraph starting a few
  points below the running head was deleted in full, taking the rest of the page with it.
  On a real FCC filing whose body opened 4pt under the header, the opening paragraph of
  every page was destroyed. Furniture is always fully contained in the zone (the zone is
  derived from furniture's own far edge); body text merely pokes into it.

  Because collapsing digits makes `Section 1` and `Section 2` key alike, a candidate must
  now also **hold still**: real furniture is anchored to the page, whereas a heading that
  merely recurs is anchored to the text flow and lands somewhere different on each page.
  Verified against arXiv's HTML rendering of 29 papers as an external ground truth —
  recall did not fall on a single one — and the feature now has tests, which it did not
  before.
- **PDF table detection no longer invents tables out of prose — or deletes the prose
  when it declines to.** `find_tables()` fires on plenty of things that are not tables,
  and a grid with only one dimension is never one: a single column is prose wrapped in
  pipes, and a single row is a line of text chopped at its word boundaries (on one
  arXiv paper the sentence *"What is the capital of this country?"* was rendered as an
  eight-column table). Those detections are now rejected — but rejecting them was not
  simply a matter of dropping them. Text inside a detected table's bbox is removed from
  the ordinary text stream *before* the table is validated, so a rejection path that
  returned nothing did not demote the region to prose, it **deleted** it: doing that
  silently cost 256 words of real body text across the corpus. Rejected regions now come
  back as paragraphs. The same applied to regions the layout model predicted as tables
  and which turned out not to be — a common misfire on academic PDFs, where suppressing
  the fake tables also removed 530 words of body text with them. Measured across the PDF
  corpus: junk tables `21 → 2`, real tables `37 → 37` (none lost), and body text strictly
  *improves* — the junk grids had been shredding words into per-cell fragments
  (`Gender` → `G` + `ender`), so ~500 real words come back.
- **`merge_hyphenated_words` now actually works on text PDFs.** The option is on
  by default, but for any PDF that did not go through OCR it silently did
  nothing: the parser delegated the merge to PyMuPDF's `TEXT_DEHYPHENATE`
  extraction flag, and that flag is inert — on PyMuPDF 1.28 / MuPDF 1.29 it does
  not change `get_text()` output in any extraction mode. A word split at a line
  break came back as `"hyphen- ation"` instead of `"hyphenation"` in every
  ordinary text PDF. The merge is now performed directly on the extracted text
  blocks (`dehyphenate_blocks()`), moving the continuation word up into the
  preceding line so the joined word survives the line-to-paragraph join that
  callers perform. The existing capitalization rule is unchanged and now applies
  to native text too: an uppercase continuation keeps the hyphen
  (`"Anglo-\nSaxon"` → `"Anglo-Saxon"`), a lowercase one drops it
  (`"be-\nwusst"` → `"bewusst"`), and hyphens not between two letters
  (`"10-\n20"`) are left alone. This is the other half of the fix for #51, which
  addressed only the OCR path — on the explicit assumption that the flag already
  covered native extraction.
- **The options reference regenerates reproducibly.** Two `MarkdownRendererOptions`
  fields default to an `UNSET` sentinel, and the generator rendered it with
  `repr()` — emitting `<object object at 0x...>`, a memory address that changed on
  every run. `docs/source/options.rst` therefore showed a spurious diff after any
  documentation build, burying real option changes in noise. Those fields now
  render as `unset`, matching the wording `all2md --help` already used. Running
  `scripts/generate_options_doc.py` standalone also works now: its `--output` and
  `--narrative` defaults resolved against `scripts/` rather than the `docs/source/`
  tree they named, so a hand-run always failed on a missing narrative file.
- **DOCX no longer opens with a stray blank line.** A Word document whose first
  paragraph is empty (a common template artifact) produced a leading blank line
  in the Markdown output — including when that empty paragraph carried a list
  style, which slipped past the empty-paragraph filter as a blank bullet. Empty
  paragraphs are now dropped uniformly across regular, list-item, and post-list
  paths, and the Markdown renderer strips any leading blank line as a final
  safeguard (so no converter can emit one).
- **Capitalization-aware dehyphenation.** When merging words split across a line
  break by a hyphen (OCR text, `merge_hyphenated_words`), an uppercase
  continuation letter now keeps the hyphen — "Anglo-\nSaxon" becomes
  "Anglo-Saxon" rather than "AngloSaxon" — so legitimately hyphenated compounds
  and names survive instead of being fused.
- **Persistent search index no longer serves stale results.** A keyword index
  saved with `--search-index-dir` (MCP `search_documents`) was reused whenever the
  directory existed, with no record of the corpus it was built from — so pointing
  it at a changed corpus, or a different `paths` set, could silently return stale
  hits. The index now records a fingerprint of the documents and index-relevant
  options at save time and is rebuilt when they no longer match.
- **HTML: an ordered list keeps its `start` attribute instead of renumbering from 1.**
  The HTML parser built the `List` node without ever reading `<ol start="N">`, so
  `<ol start="3">` came back numbered from 1 on every HTML conversion — the Markdown
  renderer already honored `List.start`, the parser just never populated it. Ordered
  lists now carry their start value through (a non-numeric `start` falls back to 1), so
  a list that does not begin at 1 survives conversion and the `markdown → html →
  markdown` round trip.
- **Markdown: multi-paragraph definition lists round-trip without collapsing.** Two
  defects in the definition-list renderer flattened a list on a Markdown round trip: a
  description's paragraphs were joined with a single newline (so a second paragraph
  merged into the first as a lazy continuation on reparse), and consecutive
  term/description groups were separated by a single newline (so the next term merged
  into the previous description). Description blocks and term groups are now separated
  by a blank line and continuation lines indented four spaces, so multi-paragraph
  descriptions and multiple terms survive intact.
- **Markdown: footnote definitions survive parsing under mistune 3.x.** The parser
  recognized only the legacy `footnote_def` token and read identifiers from
  `attrs['label']`; mistune 3.x instead groups definitions in a `footnotes` container of
  `footnote_item` tokens (the label living in `attrs['key']` / the reference's `raw`
  field, with `attrs` holding only a numeric index), so every footnote definition was
  dropped from the AST and every reference lost its identifier. The parser now handles
  the `footnotes` container and reads `key`/`raw` with a `label` fallback; a
  multi-paragraph footnote is additionally rendered with a blank line between its blocks
  and four-space continuation indent, so it no longer collapses into one paragraph on
  reparse.
- **Markdown: a table nested in a list item stays in the list.** A table inside a list
  item was emitted at column zero instead of under the item's content margin, so on a
  Markdown round trip it re-parsed as a top-level sibling and broke the list apart.
  Idempotency did not catch it — the broken output was stable — but the round-trip
  benchmark's HTML-equivalence oracle did. Table rendering now shifts every line to the
  current indent, mirroring code-block handling, so the table stays inside its item; at
  the top level the indent is empty and output is unchanged.
- **A long single line is no longer mistaken for a file path and leaked as `OSError`.**
  During source resolution `LocalPathRetriever.can_handle` called `Path(value).exists()`
  on raw input before the parse-error wrapper, so a one-line string whose path component
  exceeds the OS name limit raised `OSError(ENAMETOOLONG)` and escaped `convert()`
  instead of surfacing as an `All2MdError`. The stat calls are now guarded (mirroring the
  existing guard in the parser base), so oversized inline content is handled as content.

### Performance

- **Faster CLI cold start.** Building the dynamic CLI parser imported every format's
  options module and introspected each field, adding ~1.7s to startup even when the
  invocation never needed it. `--version`/`-V` and `--about`/`-A` are now short-circuited
  before the parser is built (dropping `--version` from ~2.0s to ~0.8s, the bare import
  cost), `AttachmentOptionsMixin` is imported from `all2md.options.common` rather than the
  eager `all2md.options` package, and `get_type_hints()` is memoized per options class —
  cutting `create_parser()` from ~1.7s to ~0.24s after a warm import, which also roughly
  halves the small-file conversion path. A cold-start benchmark (`benchmarks/startup.py`)
  guards these wins against regression.
- **Cheaper repeated and batch conversions.** Four conversion-hot-path wins help
  many-small-file and repeated-conversion workloads: the flattened, priority-sorted
  converter list is memoized — and invalidated on register/unregister — instead of being
  rebuilt on every `detect_format`; `check_version_requirement` is cached per
  `(package, spec)` so the dependency-guard decorator stops re-reading installed versions
  and re-parsing specifiers on every parse/render; resolved option type hints are shared
  across option construction; and DOCX conversion with `attachment_mode="skip"`
  short-circuits before reading the image blob (output is byte-identical).

## [1.8.2] - 2026-07-09

### Fixed

- **Bullet lists no longer disappear when rendering DOCX with a custom template.**
  When a template lacked the `List Bullet` / `List Number` styles, the generated
  numbering part interleaved `w:abstractNum` and `w:num` elements. `CT_Numbering`
  requires every `w:abstractNum` to precede every `w:num`; Word does not reject the
  malformed part but silently mis-associates the stray definition, so bulleted lists
  rendered as plain paragraphs. Numbering definitions are now spliced in ahead of any
  existing `w:num`, which also fixes templates that already ship a numbering part
  (`--docx-renderer-template-path`, `DocxRendererOptions.template_path`).
- **Generated bullets use the correct glyph.** The bullet level specified `U+00B7`
  (MIDDLE DOT) while pinning the run font to Symbol, yielding the wrong character.
  It now uses `U+F0B7`, the Symbol font's bullet, matching Word's own output.
- **Generated list styles keep their names.** `List Bullet` / `List Number` were
  created as custom styles, colliding with Word's latent built-ins and getting
  renamed to `List Bullet1` / `List Number1` — so any styling a template applied to
  `List Bullet` never took effect. They are now created as built-in styles.

### Changed

- CI now runs on pushes to and pull requests against `release/**` branches, so patch
  releases cut from a release tag get a full lint/type/test run before merge.

## [1.8.1] - 2026-07-06

### Added

- **`--remote-input-no-require-head-success`.** Remote document fetching
  (``all2md https://…``) previously always required a successful HEAD request
  before downloading, with no way to opt out — servers that reject or mishandle
  HEAD could not be read at all. ``RemoteInputOptions`` gains
  ``require_head_success`` (default ``True``) with a matching CLI flag and
  ``ALL2MD_REMOTE_INPUT_REQUIRE_HEAD_SUCCESS`` environment variable.

### Fixed

- **Legacy `<center>` no longer swallows page content.** ``<center>`` was not in
  the HTML parser's block-element set, so pages that wrap their main content in
  it — notably Hacker News item pages — converted to empty output. It is now
  treated as a block container and its children (paragraphs, tables, …) are
  preserved.
- **Options docs now list only flags that actually exist.** The auto-generated
  options reference invented ``--network-*`` flags with no per-format prefix and
  showed positive forms of boolean flags the CLI only exposes negated
  (e.g. ``--html-network-no-require-https``). The generator now mirrors the CLI
  builder's real naming rules (per-format ``--<format>-network-*`` /
  ``--<format>-renderer-network-*`` prefixes, negated defaults, skipped internal
  fields), and every emitted flag is cross-checked against the live parser.

### Security

- **Redirect limits are now actually enforced.** The ``max_redirects`` check ran
  in an httpx *response* event hook, which fires before httpx assigns
  ``response.history`` — so the redirect count it inspected was always empty and
  the limit never triggered. Enforcement now uses httpx's native
  ``max_redirects``, surfacing violations as ``NetworkSecurityError``.
- **Four `NetworkFetchOptions` fields were accepted but silently ignored** when
  fetching attachments/images: ``max_redirects``, ``allowed_content_types``,
  ``max_requests_per_second``, and ``max_concurrent_requests``. They are now
  wired through a single shared fetch helper used by the HTML parser and the
  DOCX/EPUB/ODP/ODT/PDF/PPTX renderers (rate limiting is applied per converter
  instance), with a guard test asserting every field of the dataclass is
  forwarded so new fields can't silently drop out again.

## [1.8.0] - 2026-07-01

### Added

- **`all2md help cheatsheet`.** A bundled, grouped quick reference of the most common
  commands (convert, view/serve/edit, extract/navigate, grep/search, chunk, diff/lint,
  generate, transforms, stdin pipes, utilities), printable offline from the terminal
  (`--rich` renders it as Markdown). The cheatsheet ships in the wheel as a single
  source of truth and is mirrored into the docs (:doc:`cheatsheet`); the quick-help
  footer now points at it.

- **`all2md chunk`: provenance-aware document chunking for RAG/LLM pipelines.**
  Splits any supported document into chunks and emits them as JSONL (one object
  per line) — or ``--format json``/``pretty``. Unlike flat-text chunkers, every
  chunk carries AST-derived provenance: its section heading/level, and the source
  page span where the parser tracks it (PDF and friends). Eleven strategies:
  ``semantic`` (default; section-bounded real-token windows), ``heading``,
  ``section``, ``auto`` (coarse, one chunk per boundary), and ``token``,
  ``sentence``, ``paragraph``, ``word``, ``line``, ``char``, ``code`` (fine).
  ``--max-tokens``/``--overlap``/``--min-tokens`` bound size; ``--max-heading-level``,
  ``--include-preamble``/``--heading-merge`` toggles control structure;
  ``--token-counter {auto,tiktoken,whitespace}`` selects the tokenizer. Real BPE
  token counting uses ``tiktoken`` (new optional extra: ``pip install all2md[chunk]``);
  count-only strategies fall back to a whitespace approximation when it is absent.
  Element handling: ``--avoid-table-split`` and ``--avoid-code-split`` keep each table
  or fenced code block whole (one atomic chunk rather than fragmenting it),
  ``--drop-elements image,table,…`` strips noisy node types before chunking,
  ``--elide-data-uris`` (on by default) replaces long base64 ``data:`` URIs with a short
  placeholder so embedded images never inflate token counts or shred into noise, and
  ``--attachment-mode {skip,alt_text,save,base64}`` (plus any ``[pdf]``/``[html]``/
  top-level converter keys in a config file) controls how the underlying conversion
  handles images — so base64 blobs need never reach a chunk. Exposed from Python as a
  one-call ``all2md.chunk(source, …)`` (mirrors ``to_markdown``: converts and chunks in a
  single step, deriving ``document_id``/path from the source and forwarding converter
  kwargs), with ``all2md.chunking.chunk_ast(doc, …)`` for an AST you already hold; both
  return ``ProvenanceChunk`` records. The fine-grained chunkers are vendored from the
  ``localvectordb`` sister project.
- **Mermaid diagrams, syntax highlighting, and custom themes for `view`/`serve`.**
  The browser preview (`all2md view`) and local server (`all2md serve`) now render
  ```mermaid``` fences as diagrams (via mermaid.js) and syntax-highlight fenced code
  and raw source files (via highlight.js). Both are on by default with graceful
  offline degradation, toggle off with ``--no-mermaid`` / ``--no-syntax-highlight``,
  and pick dark variants under ``--dark``. Mermaid rendering is also exposed on the
  HTML renderer via the new ``HtmlRendererOptions.render_mermaid`` (off by default;
  ``view``/``serve`` enable it). ``serve``'s directory listing is rewritten as an
  aligned table (Name/Size/Modified/Created) plus a card view with a
  localStorage-remembered toggle and HTML-escaped names. ``--theme`` now also accepts
  a plain ``.css`` file (wrapped in a minimal shell) and a theme name registered in a
  new ``[themes]`` config table. New "Document Viewer & Server" guide (:doc:`viewer`).

### Fixed

- **`merge_hyphenated_words` now applies to OCR text.** PyMuPDF's
  ``TEXT_DEHYPHENATE`` flag only affects native text extraction, so words
  hyphenated across a line break (``be-\nwusst``) survived unmerged whenever a
  PDF page went through OCR (``--pdf-ocr-enabled``), even with
  ``merge_hyphenated_words = true``. OCR output is now dehyphenated the same way,
  joining the split halves (``bewusst``). Numeric ranges (``10-\n20``) and
  hyphens not sitting between two letters are left untouched. (#51)
- **Config-file discovery is now bounded at the home directory.**
  ``find_config_in_parents()`` walked from the working directory all the way to the
  filesystem root, so an ``.all2md.*`` sitting in a shared parent (a drive root,
  ``/``) would silently apply to every project underneath it. The upward walk now
  stops at ``Path.home()`` (inclusive). Real behavior is unchanged — ``~/.all2md.*``
  is still found, and the home fallback still covers a working directory outside the
  home subtree.

## [1.7.1] - 2026-06-25

### Added

- **Lint profiles: `all2md lint --profile NAME`.** Curated, named rule bundles
  built entirely from the existing 47 rules — ``prose`` (typographic polish for
  long-form writing, ideal for a converted DOCX), ``accessibility`` (alt text,
  link/table semantics, heading hierarchy at error severity), and
  ``technical-docs`` (structure and links enforced, prose typography relaxed).
  ``--list-profiles`` prints them with descriptions. Profiles are a base layer:
  config files and CLI flags layer on top in precedence ``profile`` < config file
  < CLI flags. Exposed from Python via ``all2md.linter.get_profile_config`` /
  ``available_profiles``. New "Linting & Enforcing a Style Guide" how-to guide in
  the docs walks the full convert → lint → fix → profile workflow.
- **`--extract` is now repeatable and understands tables and figures.** In
  addition to sections (by name/pattern or ``#:`` index) and ``line:`` ranges,
  ``--extract`` now selects tables (``table:2``, ``table:1-3``, ``table:*``) and
  figures/images (``figure:1``, ``image:*``). Pass ``--extract`` multiple times to
  pull several pieces at once; results are emitted in the order the flags appear,
  separated by ``---``. A single ``line:`` range still cannot be mixed with other
  selectors.
- **`--extract … ::N` word limit.** Append ``::N`` to a selector to cap its output
  at roughly ``N`` words, cut at node boundaries so the result stays valid (e.g.
  ``--extract "Introduction::500"``).
- **`--slice X/Y` paging.** Return the Xth of Y semantic slices of a document to
  stdout/file without writing split files. The document is divided into exactly
  ``Y`` balanced slices at section boundaries, and the chosen slice is emitted with
  a footer hint pointing at the next slice. Mutually exclusive with
  ``--extract``/``--outline``/``--split-by``/``--collate``.
- **`--head [N]`, `--tail [N]`, and `--lines START:END`.** Simple windows over the
  rendered Markdown output (1-based, inclusive), mirroring ``head``/``tail`` and the
  existing ``--extract line:`` range. ``--head``/``--tail`` default to 10 lines and
  honor ``--line-numbers``.

### Fixed

- **GFM tables nested in list items and blockquotes are now parsed.** Pipe tables
  indented inside a list item or ``>`` blockquote were previously left as plain text;
  they are now recognized and parsed into table nodes.

## [1.7.0] - 2026-06-24

### Changed

- **`--pager` no longer refuses to page Rich output on Windows/WSL.** Paging is
  left to the environment via ``PAGER``/``MANPAGER`` and the platform default.
  When ``--pager --rich`` is used on Windows without a configured ``PAGER`` (where
  the default ``more`` mangles ANSI color codes), all2md now prints a one-line hint
  pointing at an ANSI-capable pager such as ``less -R`` instead of silently
  dropping paging.
- **EML: HTML and RTF bodies keep their formatting.** Email bodies converted from
  HTML (with ``convert_html_to_markdown``) or RTF are now re-parsed into rich AST
  nodes, so headings, bold/italic, links, and lists survive into the output
  instead of being flattened to escaped plain text. Genuine plain-text bodies are
  still treated as plain text, and raw HTML is never passed through (the Markdown
  renderer escapes it by default), preserving the parser's sanitization stance.

### Added

- **`[rich]` config table for theming `--rich` terminal output.** A new
  ``[rich]`` table in the config file customizes the colors Rich uses for
  Markdown elements (headings, links, block quotes, list bullets, inline code,
  ...) in ``--rich`` output. Bare element names auto-prefix to ``markdown.*``;
  dotted keys pass through verbatim; invalid or non-string entries are skipped
  with a warning. Previously only code-block syntax themes were configurable.
  ``all2md config generate`` emits a commented ``[rich]`` example.
- **`all2md help markdown` (and `help md`).** Added as aliases for the verbose
  ``help common-markdown-formatting`` topic, matching the ``help <format>``
  pattern used by every other format.
- **`view`/`serve` honor converter options from the config file.** A single
  config file now drives ``all2md``, ``view``, and ``serve`` identically -- e.g.
  ``[pdf] detect_columns = true`` or a top-level ``attachment_mode`` applies when
  viewing or serving, not just when converting. (``serve`` still forces base64
  attachments so images render in-browser.)
- **Shorthand flags for `view` and `serve`.** ``view`` gains ``-d/--dark``,
  ``-w/--window``, ``-t/--theme``, ``-x/--extract``, ``-N/--no-wait``. ``serve``
  gains ``-p/--port``, ``-H/--host``, ``-B/--browse``, ``-C/--config``, and a new
  ``-a/--address HOST:PORT`` that sets host and port together (``-a 0.0.0.0:9000``,
  ``-a :9000``, ``-a host:``). Host uses ``-H`` because ``-h`` is reserved for
  ``--help``.
- **EML: RTF message bodies are converted to Markdown.** Emails whose body is an
  ``application/rtf`` / ``text/rtf`` part (e.g. Outlook messages exported via
  libpst/readpst) previously yielded empty content; the RTF body is now routed
  through the existing RTF parser as a fallback after plain-text and HTML, and
  rendered to Markdown. Controlled by the new ``include_rtf_parts`` option
  (``--no-include-rtf-parts``). (GitHub #39)

## [1.6.0] - 2026-06-18

### Added

- **`list_workspace_files` MCP tool.** A new read-only tool (enabled by default)
  that lets an agent discover the files it is allowed to read before reading or
  editing them. Returns each file's absolute path and size, supports a glob
  ``pattern`` and a workspace-relative ``subdirectory`` scope, recurses by
  default, and flags ``truncated`` when the listing is capped. Toggle with
  ``--enable-list-files`` / ``--no-list-files`` or
  ``ALL2MD_MCP_ENABLE_LIST_FILES``.
- **Additional read-only folders for the MCP server.** A new
  ``--additional-read-dirs`` flag and ``ALL2MD_MCP_ADDITIONAL_READ_DIRS``
  environment variable append folders to the read allowlist only (never the
  write allowlist), and are surfaced in the MCPB manifest.
- **Batch, in-place `edit_document`.** `edit_document` now accepts an ordered
  ``edits`` batch applied to a single parse; the batch is atomic (any failure
  writes nothing). When a batch contains a mutating action, the document is
  written back to disk in its original format (``disk_written`` / ``output_path``
  in the response). In-place write-back supports md/html/docx/pptx/rst/epub;
  other formats and read-only targets fail with a clear message. Responses echo
  only the edited region, not the whole document.

### Changed

- **`edit_document` auto-detects the source format** instead of assuming
  Markdown, so a ``.docx`` (or html/rst/epub/…) is parsed correctly rather than
  yielding zero sections and cryptic index errors. Mutating edits now require the
  target to be within the **write** allowlist (it was read-only before). DOCX
  write-back uses the original file as a template to preserve styles where
  possible.
- **MCP path handling.** Relative paths and bare filenames are resolved against
  the workspace (the read/write allowlist acts as the working directory) across
  the read, edit, outline, diff, and save tools. A source that is unmistakably a
  file path but cannot be found now fails loudly — listing the folders searched —
  instead of being silently treated as inline document text.

### Fixed

- **MCP stdio protocol corruption on PDFs.** PyMuPDF prints an advisory to
  stdout when processing PDFs, which corrupted the JSON-RPC channel and crashed
  the connection for any PDF. The server now redirects fd 1 → stderr around each
  tool's conversion work and sets ``PYMUPDF_MESSAGE=fd:2`` as an import-time
  backstop.

## [1.5.0] - 2026-06-15

### Added

- **MCP query tools.** The MCP server gained three read-only tools so an agent
  can query a document corpus, not just convert single files: `search_documents`
  (grep plus keyword/BM25 search across a corpus, returning ranked snippets),
  `diff_documents` (compare two documents of any format with unified or JSON
  output), and `get_document_outline` (list a document's heading structure, with
  indices aligned to `edit_document`'s `#N` notation). All three are enabled by
  default and read-only; each has its own `--no-<tool>` flag and
  `ALL2MD_MCP_ENABLE_<TOOL>` environment switch, and path inputs are enforced
  against the read allowlist. `search_documents` rebuilds a fresh in-memory index
  per call by default; opt into a persistent keyword index with
  `--search-index-dir` / `ALL2MD_MCP_SEARCH_INDEX_DIR` (validated against the
  write allowlist). Vector/hybrid search modes are rejected with a clear error.
- **Interactive `all2md batch` wizard.** A guided workflow that walks through file
  selection (with a file-type preview), output layout, attachment handling,
  per-format options, and advanced parameters, then prints the equivalent
  command and offers to run it. Uses Rich when available, with a plain-input
  fallback.
- **Near-source batch attachments.** With `--preserve-structure` and
  `--attachment-mode save` (and no explicit `--attachment-output-dir` /
  `--attachment-base-url`), saved attachments are now co-located in a shared
  `.attachments` folder beside each output file and linked with relative paths.
  Explicit overrides and the legacy single-folder behavior are preserved.
- **Batch help and docs.** The multi-file flags are now grouped under a "Batch
  options" group so `all2md help batch` works, `all2md help attachments` resolves
  to the global attachment topic, and a new `batch` page documents the
  batch-conversion CLI.
- **Material for MkDocs markdown syntax.** The markdown parser now understands
  several niche flavor constructs common on MkDocs sites: admonitions
  (`!!! note "Title"`) and their collapsible `???` / `???+` variants, and the
  pymdownx inline mark family — highlight (`==text==`, a new `Mark` AST node),
  insert/underline (`^^text^^`), superscript (`^text^`) and subscript
  (`~text~`). Admonitions round-trip to native `!!!` / `???` blocks on the
  `markdown_plus` flavor and degrade to labelled block quotes elsewhere; marks
  round-trip on flavors that support them and otherwise fall back to HTML.
  Controlled by the new `parse_marks` / `parse_admonitions` options
  (`--no-parse-marks`, `--no-parse-admonitions`).
- **Dark mode for `all2md edit`.** The in-browser editor now has a 🌙/☀️ toggle in
  its header, a `--dark` flag, and an `[edit]` config `dark = true` setting. The
  toggle choice is remembered across launches via the browser's `localStorage`.
- **Standalone-window mode for `all2md view` and `all2md edit`.** A new `--window`
  flag (and matching `[view]`/`[edit]` config setting) opens the preview/editor in
  a native OS window with no address bar or browser chrome. It uses the new
  optional `pywebview` dependency (`pip install all2md[window]`); without it,
  `all2md` prints a hint and falls back to a normal browser tab.

### Changed

- The raw-Markdown pane in `all2md edit` now uses a monospace font, matching the
  expectation for editing source text (the rendered preview pane is unchanged).

### Fixed

- **Definition lists are now parsed.** The `parse_definition_lists` option and
  its AST handling existed, but the underlying mistune plugin was never enabled,
  so `Term` / `: definition` syntax was silently dropped. It is now wired up
  (and the handler updated for the current mistune `def_list_item` token).
- **MCPB bundle now ships `rank-bm25`.** The `search_documents` MCP tool defaults
  to keyword (BM25) mode, but the Claude Desktop bundle didn't install
  `rank-bm25`, so corpus search failed out of the box with an install hint. The
  bundle now depends on `rank-bm25` directly (not the full `search` extra, whose
  `faiss-cpu` / `sentence-transformers` back the vector/hybrid modes that the MCP
  server rejects).

## [1.4.0] - 2026-06-11

### Added

- **EasyOCR engine for PDF OCR.** A new binary-free OCR backend, selectable via
  `OCROptions(engine="easyocr")` or `--pdf-ocr-engine easyocr`. Unlike the
  default Tesseract engine it needs no system binary (`pip install
  all2md[ocr-easyocr]`); it pulls in PyTorch and downloads recognition models on
  first use. Added an `OCROptions.gpu` flag (EasyOCR only). Tesseract remains
  the default with unchanged behavior.

### Fixed

- Corrected stale OCR CLI flags in the README (`--ocr-*` → `--pdf-ocr-*`).
- `rcat` opened a transient console window that closed instantly on Windows
  instead of rendering in the terminal (regression in 1.3.0). When the Windows
  context-menu integration added a `[project.gui-scripts]` table, the `rcat`
  entry point was inadvertently absorbed into it, so its launcher used the GUI
  subsystem and detached from the console. Moved `rcat` back to
  `[project.scripts]`; it renders in the terminal again.

## [1.3.0] - 2026-06-11

### Added
- `all2md llm-minify` — a token-lean conversion command for feeding documents to LLMs. The default preset keeps Markdown structure (headings, lists, code, tables) while dropping comments, frontmatter, and raw HTML, replacing embedded base64 image data with an alt-text-only reference (so a single inlined screenshot no longer costs tens of thousands of tokens), and collapsing redundant blank lines and interior whitespace. `--aggressive` (alias `--text`) strips all formatting down to bare text, and `--strip-links`/`--strip-images`/`--strip-formatting` layer additional pruning on top of either preset.
- Windows right-click context-menu integration via `all2md context-menu` (per-user, no administrator rights). It installs a **View** entry on files (browser preview), an **Edit** entry on files (in-browser editor), and a **Serve** entry on folders (local server). `install` registers View by default; add `--edit`, `--serve`, or `--all` for the others. `status` reports which entries are installed and `uninstall` removes them all. The file entries honor `--extensions`/`--all-text` for which file types they appear on; the folder Serve entry is unaffected.
- `generate-site` gained MkDocs, Zola, and Eleventy generators, joining the existing static-site backends.

### Changed
- JSON, YAML, TOML, and INI inputs now convert to a fenced, syntax-highlighted code block by default instead of a table/definition-list document (comments are preserved for the formats that have them). This is easier to read and round-trips cleanly. Pass `--<fmt>-no-literal-block` (e.g. `--json-no-literal-block`) to restore the previous structured-document output.
- In `all2md view` and `all2md serve`, external links now open in a new browser tab (`target="_blank" rel="noopener noreferrer"`) so clicking an off-site link no longer navigates away from the document; internal and relative links are unchanged. Plain `--to html` output is unaffected.
- Restructured the bundled agent skills into a single `all2md` skill following Anthropic's progressive-disclosure pattern: a lean `SKILL.md` overview that routes to per-task guides under `references/` (`read`, `convert`, `generate`, `grep`, `search`, `diff`), replacing the previous six top-level `all2md-*` skills. `install-skills` installs the one skill tree; `llm-help <topic>` maps to the reference files (topics unchanged, plus `overview`).
- Faster CLI startup: a generated converter manifest lets the CLI resolve formats without importing every converter module at launch.

### Fixed
- `auto` OCR mode now recovers scanned PDFs that previously came back empty. The per-page heuristic counts meaningful (alphanumeric) characters instead of raw string length, so pages whose extracted "text" is only whitespace or invisible glyphs now trigger OCR; a document-level safety net additionally re-runs OCR when the entire document renders near-empty under `auto`. When OCR is disabled, a hint now suggests `--pdf-ocr-mode force`.
- Corrected stale/renamed CLI flags throughout the bundled skills and docs (GitHub issue #16). Notably `--html-standalone` (HTML is standalone by default; use `--html-renderer-no-standalone` for a fragment), `--docx-template` → `--docx-renderer-template-path`, `--pdf-page-size` → `--pdf-renderer-page-size`, `--jinja-template*` → `--jinja-renderer-template*`, `--pdf-detect-tables` → `--pdf-table-detection-mode`, search `--semantic`/`--mode bm25` → `--vector`/`--keyword`, and several others. Added a regression test that fails if any removed flag reappears in bundled skill content.

### Documentation
- Comprehensive documentation audit: split the overview into a user-facing guide and a separate architecture-internals page, reconciled configuration-precedence docs, removed overlapping/duplicated guidance, and fixed a range of accuracy and correctness errors across the guides. The supported-format matrix is now auto-generated from the converter registry during the Sphinx build, so it can no longer drift from the code.

## [1.2.0] - 2026-05-29

### Added
- Config-file support for the `view`, `serve`, `diff`, `edit`, `arxiv`, and `generate-site` subcommands. Each command reads its own same-named section — `[view]`, `[serve]`, `[diff]`, `[edit]`, `[arxiv]`, `[generate-site]` — from `.all2md.toml`/`.yaml`/`.json` (or the equivalent `[tool.all2md.<command>]` block in `pyproject.toml`), so flags like `view --no-wait` or `serve --port` can be set once instead of typed every time. Precedence is built-in default < config section < explicit CLI flag, and every one of these commands now also accepts `--config <path>` and `--no-config`, mirroring the main converter. Keys are the option name (hyphens or underscores both work); only the matching section is read, so subcommand config never affects a normal conversion and vice versa. A config value can also satisfy an otherwise-required option (e.g. `[arxiv]` with `output = "paper.tar.gz"` lets `all2md arxiv paper.tex` run without `-o`).
- `all2md config generate` now emits a template section for each of those subcommands alongside the format sections, so generating a config is the quickest way to discover every available subcommand key and its default. See the new "Subcommand Options" section in `docs/source/configuration.rst`.

### Fixed
- The main converter no longer mishandles non-format config sections (`[view]`, `[serve]`, `[diff]`, etc.) when the input format can't be determined (stdin or failed detection). On that fallback path, any format-qualified option was previously applied blindly, so a subcommand section's keys (e.g. `port`, `no_wait`) could be injected as parser keyword arguments and crash the conversion. The fallback is now restricted to recognized parser/renderer format prefixes; unrecognized sections are dropped.

## [1.1.3] - 2026-05-21

### Added
- `rcat` — a standalone "rich cat" command equivalent to `all2md --rich`. Renders any supported document with rich terminal formatting (syntax highlighting, colors) and automatically falls back to plain Markdown when output is piped or redirected, so `rcat doc.pdf` pretty-prints while `rcat doc.pdf | grep ...` stays parseable.
- `all2md serve` now accepts glob patterns (e.g. `all2md serve "docs/*.docx"`). The pattern's anchor directory is served as a listing filtered to matching files; a `**` segment enables recursive matching. The background live-rescan continues to honor the filter, and a hand-authored `index.html`/`README.md` no longer overrides the filtered listing.
- `--include-hidden` flag for both conversion and `all2md serve`. Dot-files and dot-folders are now skipped by default when scanning directories or expanding globs; pass `--include-hidden` to include them. Explicitly named files (even hidden ones) are always converted.
- `-f` as a short alias for `--force-rich`.
- `install-skills`, `edit`, `lint`, and `arxiv` subcommands now appear in the `all2md --help` listing (previously hidden).

### Fixed
- `--force-rich` now actually emits ANSI styling when stdout is not a TTY, so piping forced rich output to a pager works (e.g. `rcat file --force-rich | less -R`). Previously the forced-rich path still produced plain text because the Rich console was not placed into terminal mode.

## [1.1.2] - 2026-05-20

### Added
- `all2md serve` now auto-renders an `index.html`, `index.htm`, `index.md`, or `README.md` (case-insensitive, priority order) from the served directory through the active theme instead of the generated file listing. Applies to every directory the server can reach, including subdirectories in `--recursive` mode. New `--force-auto-index` flag opts back into the generated listing.
- `all2md serve` directory mode now picks up newly added, removed, and modified files automatically via a background polling thread. New `--poll-interval SECONDS` flag (default `2.0`, set `0` to disable) controls the rescan cadence; on detected change the cached index page is invalidated and stale file-cache entries for vanished files are dropped.
- Line-number navigation for the CLI. `--line-numbers`/`-ln` annotates Markdown output with line numbers: `--outline --line-numbers` labels each heading with the line it occupies in the full conversion, a normal conversion numbers every line (`cat -n` style), and `--extract` keeps the returned lines' original numbers. Line numbers reference the Markdown rendering and are ignored for other targets.
- `--extract line:X-Y` selects content by output line range (`line:42`, `line:42-87`, `line:42-`, or `line:1-10,42-87`; 1-based, inclusive). The selection is taken on the Markdown rendering and re-parsed so it can still render to any `--to` target. Paired with `--outline --line-numbers`, this lets a reader (or an LLM/agent) map a document then pull back just the range it needs.

### Changed
- `all2md serve` now handles requests on per-connection threads (`ThreadingHTTPServer`), so a slow conversion no longer blocks other visitors.

### Fixed
- `all2md serve` Ctrl+C shutdown was previously delayed until the next inbound request arrived to unblock `select()` on Windows. The server now runs `serve_forever()` in a background daemon thread and the main thread reacts to SIGINT immediately, calling `httpd.shutdown()` for a prompt clean exit.
- `--to`/`--output-format` was silently ignored when converting to stdout (e.g. `all2md doc.md --to html` printed Markdown). The option is now tracked as explicitly provided, so it is honored for stdout and takes precedence over output-path extension inference; `ALL2MD_OUTPUT_FORMAT` also works as a default.
- Short UTF-8 files could be mojibaked when chardet misdetected rare multi-byte characters (en-dash, em-dash, smart quotes) as Windows-1252 (e.g. turning "–" into "â€""). A strict UTF-8 decode is now attempted first; since invalid UTF-8 byte sequences raise rather than mis-decode, a successful decode is definitively correct.

## [1.1.1] - 2026-05-15

### Added
- New PDF parsing options for handling brittle real-world layouts: `min_image_dimension` (filter decorative artifacts under a pixel threshold), `filter_header_footer_images` (drop images sitting inside detected page-header/footer bands), `collapse_excess_whitespace` (collapse long whitespace runs that PDF spans use as layout padding), `dedup_running_headings` (merge split numbering-prefix headings like `"I."` + `"Background"` into `"I. Background"`), and `annotate_rotated_text` (opt-in `*[rotated 90° counter-clockwise]*` marker; default off).
- DOCX round-trip formatting preservation. `to_ast`/`from_ast`/`from_markdown`/`convert` accept a new `preserve_formatting` kwarg, and `all2md edit` gains a `--preserve-formatting` flag (on by default for `.docx` → `.docx`; pass `--no-preserve-formatting` to opt out). Round-tripping a `.docx` through Markdown now keeps page setup, theme, headers/footers, and named paragraph styles instead of collapsing them to defaults. The parser stashes `paragraph.style.name` on AST nodes via `metadata['source_style']`, and the renderer re-applies it when the template defines the style — so custom paragraph styles like "Chapter Title" survive instead of degrading to "Heading 1". `to_ast` auto-stashes `Document.metadata['source_path']` for file-path inputs so the original document can be reused as a rendering template. Out of scope: run-level character styles still collapse on round-trip (tracked separately).
- `DocxRendererOptions.clear_template_body` (default `False`) — gates whether a loaded `template_path` keeps its body content (letterhead use case) or has it stripped before the AST is rendered (round-trip use case). Section properties, headers/footers, and style definitions are always preserved.
- Corpus benchmark harness under `benchmarks/corpus/` — pulls deterministic samples from arxiv, PubMed Central, govdocs1, Apache POI, and Enron, times conversion, and emits a stratified Markdown report. Companion `inspect` command saves converted Markdown next to the source for manual quality review on the slowest, largest, and random subsets. See `benchmarks/corpus/README.md` and the new "Corpus Benchmark Harness" section in `docs/source/performance.rst`.
- Manual-dispatch GitHub Actions workflow (`.github/workflows/benchmark.yml`) that runs the corpus harness on a clean `ubuntu-latest` VM, caches the ~1 GB corpus between runs, and uploads results as a 90-day workflow artifact. Use for reproducible perf numbers when the local dev box is too noisy.
- Benchmark CLI ergonomics: `purge` subcommand to delete the ~1 GB corpus cache, `--purge-after` flag for post-run cleanup (CI / ephemeral disks), and `--use-layout-model` to opt back into the optional `pymupdf-layout` ONNX classifier — off by default in the benchmark for reproducibility across machines.
- Reference benchmark snapshots under `benchmarks/reference/` — committed before/after `.md` + `.json` reports (`b0e4224-baseline`, `3516bc9-optimized`) that anchor the performance numbers cited in the docs.
- New documentation page `docs/source/optimizations.rst` walking through the v1.1.1 PDF performance work: methodology (corpus benchmark + cProfile + inspect), headline numbers, the 000887.pdf case study (5.6 min → 11.65 s), per-commit attribution, and a "what's still slow" section.

### Changed
- PDF table detection in the default mode now skips PyMuPDF's `find_tables()` on pages with no ruling-line drawings or large closed rectangles. Avoids ~1s/page of wasted work on prose-only pages where `find_tables()` would either return nothing useful or fire on decorative frames that downstream guards already reject. Net impact on the 149-doc corpus benchmark: 21.4 min → 6.7 min total (3.2x faster); PDF p50 8.5s → 728ms (12x); the slowest single file 5.6 min → 11.65 s (28x). The new `page_has_table_signals()` helper is conservative on error (returns True / runs `find_tables`) so PyMuPDF quirks can't silently lose real tables. `table_detection_mode="pymupdf"` is unchanged — explicit opt-in to always-run behavior. See `docs/source/optimizations.rst` for the full writeup.
- `image_placement_markers` no longer applies when `attachment_mode="alt_text"` (the default). Markers had no URL to target in that mode, so `![Image from page N]()` placeholders were just noise. The option now only takes effect in `save` and `base64` modes. As a side effect, image-heavy PDFs in the default mode also skip pixmap decoding entirely (≈160 decodes avoided on a typical 32-page workshop PDF).
- DOCX rendering re-applies parser-stashed `source_style` paragraph styles when the template defines them, rather than always falling back to built-in heading mapping.
- `DocxRendererOptions` field order: `network` moved to the end so the auto-generated options docs read in a more natural order. All fields remain keyword-friendly with defaults.

### Fixed
- PDF heading detection misclassified the body=11pt / header=12pt convention as body text (the 1.2 size-ratio default produced an empty `header_id`), silently ignored bold-only header styles, and classified mixed-style lines by `spans[0]` only. Spans are now aggregated per line and style requirements are enforced.
- PDF rotated text flooded output with one `*[rotated 90° counter-clockwise]*` marker per line (~280 markers on the "Attention Is All You Need" figure-axis labels). Consecutive rotated spans are now grouped within blocks and merged across blocks via metadata, and the annotation is opt-in via the new `annotate_rotated_text` option.
- PDF table detection fired on TOC dot-leader regions, decorative frames, and oversized empty grids in both PyMuPDF's `find_tables()` and the ruling-line fallback. Shared size, sparsity, uniformity, and dot-leader-ratio guards now reject pathological detections in both paths rather than emitting them as garbage tables.
- PDF `attachment_mode="alt_text"` emitted 100+ empty `![Image from page N]()` placeholders on image-heavy documents. `extract_page_images()` now returns early in `alt_text` mode (suppresses the placeholders and avoids decoding every pixmap only to throw the bytes away).
- Tiny decorative PDF images (logo strokes, signature artifacts) and images sitting inside detected page-header/footer regions are no longer emitted as ghost markers — see the new `min_image_dimension` and `filter_header_footer_images` options.

## [1.1.0] - 2026-05-01

### Added
- `all2md edit FILE` command — launches a local web-based editor (Toast UI Editor v3.2.2 with Markdown and WYSIWYG modes) pre-loaded with any supported document converted to Markdown. Saves back to disk in any installed target format, with automatic `.bak` creation when overwriting. For `.md` sources the default save target is the original file (overwrite enabled); for any other format the default target is a sibling `.md` file (overwrite disabled). Toast UI assets are vendored under `themes/assets/` and served from `/assets/` with a strict allow-list.
- Linter v2: 27 new rules across three new categories and four expanded ones, bringing the total to 47 built-in rules. New categories: **LST** (lists), **TBL** (tables), **IMG** (images). Expanded categories: STR (`short-section`, `empty-document`, `excessive-nesting`), HDG (`heading-as-sentence`, `heading-url`), LNK (`insecure-link`, `link-text-is-url`), TYP (`ellipsis-character`, `space-before-punctuation`, `consecutive-punctuation`).
- Auto-fix framework: `all2md lint --fix` applies safe auto-fixes in place. Seven rules ship with safe fixes attached: TYP001 (trailing-spaces), TYP002 (multiple-spaces), TYP003 (straight-quotes), TYP004 (double-hyphens), TYP006 (ellipsis-character), TYP007 (space-before-punctuation), and STR004 (empty-heading).
- `--dry-run` flag for `lint --fix`: report what would be changed without writing the file.
- Public API: `all2md.linter.lint_and_fix_document()`, `lint_and_fix_file()`, `LintFixResult`, `LintFix`, `FixSafety`, `FixContext`, `apply_fixes`.
- Reporters now surface auto-fix results: the text reporter prints per-file `applied N fix(es)` plus deferred-conflict counts; the JSON reporter adds `applied_fixes`, `skipped_fixes`, `pre_fix_violations`, and `rewritten` keys per result entry.

### Changed
- `Violation.fixable` is now a derived `@property` (`fix is not None`) rather than a stored field. Code that constructs `Violation(..., fixable=True)` will need to pass a `LintFix` instead.
- `LintRule.build_violation()` accepts an optional `fix=` keyword to attach a `LintFix` to a violation.

## [1.0.6] - 2026-04-10

### Added
- Per-subdirectory index pages with breadcrumb navigation when serving directories recursively (`all2md serve --recursive`)
- Batch conversion examples added to CLI help output for discoverability

### Fixed
- PDF conversion crash when PyMuPDF detects empty tables (tables with no cells)
- `view --no-wait` deleting the temp file before the browser could load it

### Changed
- Default document author is now set to "all2md" when not otherwise specified by the source document
- Auto-release CI workflow: tag pushes now run CI checks then publish to PyPI automatically
- Bumped `codecov/codecov-action` from 5 to 6 and `actions/setup-python` from 5 to 6

## [1.0.5] - 2026-04-08

### Added
- `--no-wait` flag for the `view` command for non-interactive use

### Fixed
- Create missing list styles when rendering DOCX with custom templates

## [1.0.4] - 2026-03-25

### Added
- ArXiv submission package generator (`all2md arxiv`) — converts any supported document format into a complete ArXiv-ready LaTeX submission archive (`.tar.gz` or directory) with extracted figures and optional `.bib` bibliography
- Pre-built [Agent Skills](https://agentskills.io) — 6 focused skill files (`all2md-read`, `all2md-convert`, `all2md-generate`, `all2md-grep`, `all2md-search`, `all2md-diff`) that teach AI coding assistants (Claude Code, Cursor, Windsurf) how to use all2md. Install with `all2md install-skills`
- Optional `pymupdf-layout` integration for GNN-based PDF layout analysis — classifies text blocks by semantic role (title, section-header, caption, footnote, etc.) for improved reading order and structure detection. Install with `pip install "all2md[pdf_layout]"`

### Fixed
- CLI renderer options (e.g. `--docx-renderer-template-path`) were silently dropped during format filtering, causing renderer-specific flags to have no effect

## [1.0.3] - 2026-03-16

### Added
- Flow layout engine for Markdown-to-PPTX rendering with template placeholder reuse and inherited built-in styles
- H1-to-Title promotion for Markdown-to-DOCX rendering

### Fixed
- HTML renderer anchor links now use GitHub-style heading IDs (`id="introduction"` instead of `id="introduction-1"`), so `#ref` links resolve correctly
- PPTX flow layout no longer overlaps template placeholders; HTML comments route to speaker notes
- `--collate --out` now writes the target format (e.g. DOCX) instead of raw Markdown
- Sphinx documentation build warning from malformed `.. deprecated::` directive
- Stale mypy `type: ignore` comments across pptx renderer, title promotion transform, and archive parser
- Flaky `test_detect_latin1` marked as `xfail` (chardet Latin-1 detection unreliable across platforms)

### Changed
- Upgraded to Black 26.x and pinned version (`~=26.1`) to prevent CI/local formatting drift
- Pre-commit format-sync hooks now use `uv run` for Windows compatibility
- `options=` accepted as deprecated alias for `parser_options` in `to_markdown()`; unmatched kwargs now warn

## [1.0.2] - 2026-02-27

### Fixed
- PPTX flow layout overlapping template placeholders
- HTML comments in PPTX now route to speaker notes

## [1.0.1] - 2025-12-18

### Added
- Softbreak parsing and DOCX CodeBlock styling support
- Dependency-aware file filtering for shell completions

### Fixed
- Diff CLI args renamed to original/modified for clarity
- CLI processor refactoring and PDF parsing internals split out
- Broken test from CLI help text change
- mypy type issue from merging lost branch

### Changed
- Refactored CLI processors and split PDF parsing internals

## [1.0.0] - 2025-10-29

#### Core Features
- Universal document conversion library supporting bidirectional transformation between various formats and Markdown
- AST-based (Abstract Syntax Tree) pipeline for consistent document manipulation across all formats
- Smart dependency management with format-specific optional dependencies
- Security-conscious design with SSRF protection and archive validation

#### Supported Input Formats (Parse to AST/Markdown)
- **Office Documents**: PDF, DOCX, PPTX, RTF, ODT, ODP, ODS, XLSX
- **Web & Markup**: HTML, MHTML, Markdown, reStructuredText, AsciiDoc, Org-Mode, MediaWiki, Textile, BBCode, DokuWiki
- **Email**: EML, MBOX, MSG (Outlook), PST/OST (Outlook archives)
- **E-books**: EPUB, FB2, CHM
- **Data & Code**: CSV/TSV, Jupyter Notebooks (.ipynb), OpenAPI/Swagger, 200+ source code languages
- **Archives**: ZIP, TAR, 7Z, RAR and other archive formats
- **Other**: LaTeX, plain text

#### Supported Output Formats (Render from AST/Markdown)
- **Markdown**: Multiple flavors (GFM, CommonMark, etc.)
- **Office**: DOCX, PPTX, PDF, ODT, ODP
- **Web**: HTML, RTF
- **Markup**: reStructuredText, AsciiDoc, Org-Mode, MediaWiki, Textile, DokuWiki, LaTeX
- **Data**: CSV, Jupyter Notebooks (.ipynb), AST JSON
- **Templates**: Custom Jinja2 templates for any text-based format
- **Plain text**

#### MCP Server Integration
- Built-in Model Context Protocol (MCP) server for AI assistant integration
- Smart auto-detection of input sources (file paths, data URIs, base64, plain text)
- Section extraction by heading name for targeted reading
- Security features including file allowlists and network controls
- Support for vision-enabled models with base64 image embedding

#### PDF Features
- Advanced table detection and extraction
- Multi-column layout analysis
- Intelligent header/footer removal
- OCR support for scanned documents (via Tesseract)
- Page range selection
- Configurable text extraction powered by PyMuPDF

#### Transform System
- Built-in transforms:
  - `remove-images`: Strip images from documents
  - `remove-nodes`: Remove specific node types
  - `heading-offset`: Adjust heading levels
  - `link-rewriter`: Rewrite URLs with patterns
  - `text-replacer`: Find and replace text content
  - `add-heading-ids`: Generate heading IDs for anchors
  - `remove-boilerplate`: Strip common boilerplate content
  - `add-timestamp`: Add conversion timestamp metadata
  - `word-count`: Add word count metadata
  - `add-attachment-footnotes`: Add footnotes for attachments
- Extensible plugin system for custom transforms via entry points

#### CLI Features
- Multi-file and directory processing with recursive mode
- Parallel execution for batch conversions
- Directory watching for automatic conversion
- stdin/stdout piping support
- Format-specific options exposed as CLI flags
- Progress bars and rich terminal output
- Preset configurations for common workflows
- Transform application from command line

#### Python API
- Simple `to_markdown()` function for quick conversions
- `convert()` function for format-to-format conversion
- `to_ast()` and `from_ast()` for AST manipulation
- Type-safe configuration with dataclass-based options
- Programmatic transform pipeline application
- Direct AST node manipulation for advanced use cases

#### Template System
- Jinja2 template renderer for custom output formats
- Example templates included:
  - DocBook XML
  - YAML metadata
  - ANSI terminal output
  - Custom outlines

#### Developer Features
- Comprehensive test suite with pytest markers (unit, integration, e2e, format-specific)
- Property-based testing with Hypothesis
- Golden/snapshot testing with Syrupy
- Type checking with mypy and custom type stubs
- Code quality enforcement with Ruff
- Pre-commit hooks
- Extensive documentation with Sphinx
- Entry point system for third-party plugins

#### Documentation
- Comprehensive README with examples
- API documentation with Sphinx
- Format-specific guides
- Security and threat model documentation
- Plugin development guide
- MCP server configuration guide
- Transform system documentation
- Contributing guidelines

### Security
- SSRF protection for remote resource fetching
- ZIP bomb detection and prevention
- Path traversal protection in archives
- Network security controls with allowlists/blocklists
- HTML sanitization with configurable policies
- URL validation and sanitization

### Technical Details
- Python 3.10+ required
- Hatchling build backend
- MIT License
- Comprehensive type hints throughout codebase
- NumPy-style docstrings
- Modular architecture with clear separation of concerns

[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.9.0...HEAD
[1.9.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.9.0
[1.8.2]: https://github.com/thomas-villani/all2md/releases/tag/v1.8.2
[1.8.1]: https://github.com/thomas-villani/all2md/releases/tag/v1.8.1
[1.8.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.8.0
[1.7.1]: https://github.com/thomas-villani/all2md/releases/tag/v1.7.1
[1.7.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.7.0
[1.6.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.6.0
[1.5.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.5.0
[1.4.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.4.0
[1.3.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.3.0
[1.2.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.2.0
[1.1.3]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.3
[1.1.2]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.2
[1.1.1]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.1
[1.1.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.1.0
[1.0.6]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.6
[1.0.5]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.5
[1.0.4]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.4
[1.0.3]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.3
[1.0.2]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.2
[1.0.1]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.1
[1.0.0]: https://github.com/thomas-villani/all2md/releases/tag/v1.0.0
