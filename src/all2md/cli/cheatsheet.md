# all2md CLI Cheatsheet

Quick reference for the most common `all2md` commands. Run `all2md help` for the
tiered help, `all2md help full` for every option, or `all2md <command> --help` for a
specific subcommand.

## Convert

```bash
all2md document.pdf                      # convert to Markdown on stdout
all2md report.docx --out report.md       # write to a file
all2md page.html --output-format rst     # choose the output format
all2md slides.pptx | wc -w               # pipe Markdown into other tools

# Many files / directories
all2md ./docs -o ./out                   # convert a directory into ./out
all2md ./docs -o ./out --recursive       # recurse into subdirectories
all2md ./docs -o ./out -p 8              # parallel, 8 workers
all2md ./docs -o ./out --preserve-structure   # mirror the input tree

# Attachments / images
all2md report.pdf --attachment-mode save --attachment-output-dir ./images
all2md report.pdf --attachment-mode skip      # drop images entirely
```

## Read in the terminal

```bash
all2md document.pdf --rich               # render Markdown with colors (fancy cat)
rcat document.pdf                        # alias for `all2md ... --rich`
all2md document.pdf --pager              # page long output
```

## Preview, serve & edit

```bash
all2md view report.pdf                   # open an HTML preview in the browser
all2md view report.pdf --dark            # dark theme
all2md serve ./docs                      # serve a directory over HTTP with live preview
all2md serve ./docs --port 8080 --browse
all2md edit notes.md                     # browser-based Markdown/WYSIWYG editor, saves back
```

## Extract & navigate

```bash
all2md book.pdf --outline                # print the heading outline
all2md book.pdf --extract "Introduction" # extract a section by heading
all2md book.pdf --extract "#:1-3"        # extract sections 1-3 (1-based)
all2md book.pdf --extract table:2        # extract the 2nd table
all2md book.pdf --head 20                # first 20 rendered lines
all2md book.pdf --lines 40:80            # a line range
all2md book.pdf --slice 2/5              # the 2nd of 5 balanced slices
all2md book.pdf --split-by h1 -o parts/  # split into files at H1 boundaries
```

## Search

```bash
all2md grep "revenue" report.pdf         # grep through any document format
all2md grep -i "todo" ./specs/*.docx     # case-insensitive across many files
all2md search "machine learning" ./papers/        # ranked keyword search
all2md search "project timeline" --semantic ./docs/   # vector / semantic search
```

## Chunk for RAG / LLMs

```bash
all2md chunk report.pdf --strategy semantic --max-tokens 512 --overlap 64   # JSONL
all2md chunk report.pdf --strategy section --out chunks.jsonl
all2md chunk report.pdf --avoid-table-split --avoid-code-split   # keep tables/code whole
all2md chunk report.pdf --drop-elements image,table              # strip noise
all2md chunk report.pdf --format pretty                          # human-readable
```

Each chunk is JSONL with section + page provenance. `pip install all2md[chunk]` enables
real token counting (`--strategy semantic/token/char`).

## Compare, lint & minify

```bash
all2md diff old.pdf new.pdf              # unified diff of two documents (any format)
all2md diff old.docx new.docx --format html --output diff.html
all2md lint report.docx                  # lint structure/headings/links/tables/typography
all2md lint report.docx --profile prose  # a curated rule bundle
all2md llm-minify report.pdf             # strip tokens for cheaper LLM input
```

## Generate

```bash
all2md notes.md --output-format docx --out notes.docx   # Markdown -> DOCX/PDF/...
all2md generate-site ./docs --generator mkdocs          # build a static site
all2md arxiv paper.md                                   # ArXiv-ready LaTeX package
```

## Transform during conversion

```bash
all2md report.docx --transform remove-images
all2md report.docx --transform heading-offset --heading-offset 1
all2md list-transforms                   # list available transforms
```

## Stdin / pipes (use '-' for stdin)

```bash
cat report.html | all2md - --format html --rich
curl https://example.com/doc.pdf | all2md - | grep "important"
echo "<h1>Note</h1>" | all2md view -
cat doc.pdf | all2md grep "term" -
echo "<p>v1</p>" | all2md diff - v2.html
```

## Utilities

```bash
all2md list-formats                      # list supported input/output formats
all2md check-deps                        # check optional dependencies
all2md config generate --out .all2md.toml   # scaffold a config file
all2md completion bash                   # shell completion script (bash/zsh/powershell)
all2md install-skills                    # install bundled agent skills
all2md llm-help [topic]                  # print the CLI guide for LLMs/agents
all2md help cheatsheet                   # print this cheatsheet
```
