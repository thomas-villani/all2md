# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Opt-in conversion cache (`--cache`).** `grep`, `search`, `chunk`, and `view`
  gain a `--cache` flag (and `--cache-dir DIR`) that stashes parsed documents on
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

[Unreleased]: https://github.com/thomas-villani/all2md/compare/v1.8.1...HEAD
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
