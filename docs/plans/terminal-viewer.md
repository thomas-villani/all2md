# Design: reading documents in the terminal

Status: stage 1 done (2026-10-05); stage 2 decided (2026-10-06), starting with fixes in Wijjit;
stages 3-4 proposed. Tracked in `ROADMAP.md` under **Next**.

`rcat report.docx` (or `all2md report.docx --rich`) is the path the README now leads
with, and a whole class of tools exists only to do this one thing: doxx for `.docx`,
glow and mdcat for Markdown. This note records what we learned from them, what our own
path loses today, and a four-stage plan.

## What the terminal path does today

```
parse → AST → MarkdownRenderer → Markdown text → rich.markdown.Markdown → ANSI
```

`cli/processors.py::_apply_rich_formatting` hands the *rendered Markdown string* to
`rich.markdown.Markdown`, which parses it again with markdown-it: CommonMark plus tables
and strikethrough, nothing else. The AST that already knows what every node is gets
flattened to text and re-guessed by a smaller dialect. A probe document through
`rcat --force-rich` on v1.16.0:

| Construct | What the terminal shows |
|---|---|
| Footnote | `footnote[^1]` … `[^1]: The footnote body.`, raw |
| Inline math | `$E=mc^2$`, raw |
| Display math | `$$ \int_0^1 x,dx $$`: the `\,` lost its backslash as a Markdown escape, so the formula is changed, not just unstyled |
| Task list | `• [x] done`, raw brackets |
| Definition list | `Term : Definition here`, run together on one line |
| `> [!NOTE]` admonition | `▌ [!NOTE] An admonition`, raw |
| Underline | plain text |
| Image | `🌆 A cat` |

Every one of these is a distinct node or attribute in our AST (`FootnoteReference`,
`FootnoteDefinition`, `MathInline`, `MathBlock`, `ListItem.task_status`,
`DefinitionList`, `Underline`, `Image`, admonition metadata on `BlockQuote`). The loss
is entirely in the second parse.

## What the other readers do

| | doxx | glow | mdcat | all2md today |
|---|---|---|---|---|
| Formats | `.docx` only | Markdown | Markdown | ~40 |
| Interactive viewer | yes: outline, search, keymaps | yes: pager, file browser | no | no |
| Outline navigation | yes (`o`) | — | — | no |
| Search with highlighting | yes (`n`/`p`) | in the pager | no | `all2md grep`, not in the view |
| Images | iTerm2, Kitty, WezTerm, Sixel, half-block fallback | no | iTerm2, Kitty, WezTerm | alt text |
| Clickable hyperlinks (OSC 8) | — | — | yes | yes |
| Math | LaTeX rendered | — | — | raw, and mangled |
| Color depth control | `--color-depth` 1/4/8/24 | auto | auto | auto |
| Readable width cap | — | yes, about 80 columns | — | full terminal width |
| Light/dark auto style | — | yes | — | no |
| Export | md, text, csv, json, ansi | — | — | every renderer; ANSI via `--force-rich` |

A dash means the project does not document the feature, as of 2026-10-05.

doxx's CSV/JSON table export needs no copy: `all2md --to csv/json` already does it. What
is worth taking is the interactive viewer, the outline, search, images where the
terminal can draw them, and the small comforts (width cap, color depth, light/dark).
The thing none of them has, and we can, is the same viewer over every format we parse.

## Plan

Four stages, each its own PR stream. Stage 1 stands alone and fixes `rcat` everywhere;
stages 2–4 build on it.

### Stage 1: a terminal renderer from the AST

A new renderer, `renderers/terminal.py`, that walks the AST and builds rich renderables
directly, with no Markdown string in between.

**Shape.**

- `TerminalRenderer.render_renderables(doc) -> list[RenderableType]` is the core; the
  viewer in stage 2 consumes it.
- `render_to_string` prints those into a captured `Console` and returns ANSI, like every
  other text renderer, so `--to terminal` and `from_ast(doc, "terminal")` work.
- A heading map comes back alongside: for each `Heading`, its level, text and the line
  it lands on at a given width. The outline in stage 2 needs it, and it can only be
  known after layout, so it is computed by rendering at that width.
- Options in `options/terminal.py`: `width` (cap), `code_theme`, `inline_code_theme`,
  `hyperlinks`, `justify`, `table_box` (rich box style), `color_system`, `image_mode`.
  The existing `--rich-*` flags map onto these one for one.
- Requires `rich`, through the existing `cli_extras` extra. No new dependency.

**Node mapping.**

| Node | Rendering |
|---|---|
| `Heading` | styled rule or line by level, as `rich.markdown` does today, so the look does not change |
| `Paragraph` and inlines | one `rich.text.Text` with spans: bold, italic, underline, strike, `Mark` as reverse or highlight, `Superscript`/`Subscript` as Unicode where a mapping exists, else `^x`/`_x` |
| `Link` | OSC 8 hyperlink when `hyperlinks` is on; the URL in parentheses when it is not and differs from the text |
| `Code`, `CodeBlock` | `rich.syntax.Syntax` with the code theme |
| `List`, `ListItem` | real nesting with hanging indents; ordered numbers from `start`; `task_status` as ☑/☐ |
| `BlockQuote` | left bar; with admonition metadata, a titled `Panel` colored by kind |
| `Table` | `rich.table.Table` with column alignment, header row, caption as title; merged cells repeated or blank (decide in review) |
| `DefinitionList` | term bold on its own line, descriptions indented beneath |
| `FootnoteReference` | `[1]`-style marker, numbered in order of first reference |
| `FootnoteDefinition` | collected and printed at the end under a rule, numbered to match |
| `MathInline`, `MathBlock` | LaTeX verbatim, styled, never re-escaped; display math in a box |
| `Image` | `[image: alt]` placeholder line (stage 4 draws pictures) |
| `Figure` | its image/table with the caption beneath |
| `ThematicBreak` | `rich.rule.Rule` |
| `HTMLBlock`, `HTMLInline` | dim verbatim |
| `Comment`, `CommentInline` | dim, prefixed with the author when there is one; hidden with an option |
| `LineBreak` | newline inside the `Text` |

**One finding to settle first.** Admonitions were not represented one way: the RST and
MkDocs (`!!!`) parsers put `admonition_type` and `admonition_title` in a `BlockQuote`'s
metadata, the AsciiDoc parser used `role`, and the Markdown parser does not recognize
GitHub's `> [!NOTE]` at all. The renderer should read one key. ✅ Normalized in its own
PR: every parser now writes `admonition_type` / `admonition_title` (the contract is on
`BlockQuote`'s docstring), and the AsciiDoc parser reads all three of its forms. ✅ The
Markdown parser reads GitHub alerts too, and GFM writes untitled admonitions back as
alerts.

**As built.** `renderers/terminal.py` and `options/terminal.py`, registered as the
render-only format `terminal` (open question 2). `render_renderables`, `render_to_string`
and `heading_positions(doc)` (the heading map, top-level headings only) are the API. A
merged table cell's content sits in its first cell and the cells it spans are blank (open
question 4). The `image_mode` option waits for stage 4. A whole document switched first
(#580); `--extract`, `--slice` and `--outline` followed by rendering their sub-document
(the outline as a nested list of the headings). Line windows still choose Markdown lines,
so the numbers agree with `--outline -ln`, then re-parse and draw them. `--line-numbers`
prints the numbered Markdown source unstyled, since the numbers count its lines; Rich's
Markdown reader used to reflow it into one paragraph.

**Switching `--rich` over.** When the CLI is rendering Markdown for the terminal, it uses
the terminal renderer on the AST instead of `rich.markdown.Markdown` on the text.
`--rich` with another `--to` target keeps today's behavior (syntax-highlighting that
output). The `[rich]` config table's style keys (`h1`, `block_quote`, …, prefixed
`markdown.`) keep working: the renderer looks its styles up by the same names, so
existing user themes still apply.

**Tests.**

- Snapshot tests at a fixed width with `color_system=None`, one per node kind, plus the
  probe document above as a regression.
- A no-loss invariant for the fuzzer: every `Text`, `Code` and math node's content
  appears in the plain export of the terminal rendering. That is the exact property the
  current path breaks: the `\,` that went missing above is such a loss.
- The README examples in the terminal section render unchanged in kind.

### Stage 2: an interactive viewer on Wijjit

[Wijjit](https://github.com/thomas-villani/wijjit) (ours: Jinja2 templates for layout,
Flask-style view and key decorators, reactive state, a virtual-DOM reconciler) supplies
nearly every piece:

| Viewer need | Wijjit |
|---|---|
| Scrollable document body | `ContentView` in ANSI mode (see the spike: it needs a width hook) |
| Outline that jumps (doxx's `o`) | `Tree`, built from stage 1's heading map; selecting a node scrolls the body |
| Status line: file, position, match count | `StatusBar` |
| Key presets: default, vim, less | `@app.on_key`, one binding table per preset |
| Copy view / selection | built in, through `pyperclip` |
| Images | `ImageView` (`wijjit[images]`, Pillow) |

**The command.** `all2md read FILE`, with `rcat -i FILE` as a shortcut for it. It
parses once, renders once per terminal width (re-render on resize, keeping the scroll
position anchored to the nearest heading), and opens the viewer. The first version takes
one file or piped input; several files come later.

**Packaging.** Wijjit requires Python 3.11; all2md supports 3.10. A `tui` extra with a
marker: `wijjit>=0.1.2,<0.2; python_version >= "3.11"` (0.1.2 carries the fixes below). Without it the command exits
with an install hint (and on 3.10, says why); `rcat` keeps working everywhere. Pin below
0.2 until Wijjit's API settles.

**Tests.** Wijjit's headless harness (`wijjit.testing`, `wijjit render --keys`) drives
the real event loop without a terminal, so CI can script "open, press `o`, select the
third heading, assert the body scrolled" with no TTY.

**What a spike found (2026-10-06).** A throwaway app put the stage 1 renderer's output in
a `ContentView` beside an outline `Tree`, driven with `wijjit render --keys` and
`WijjitHarness`. The shape works: the ANSI output displays faithfully, picking a leaf
heading scrolls the body to it, a resize re-runs the view and re-wraps, and app-wide keys
fire while the tree has focus but not while a text input does. Five things need fixing in
Wijjit first, each a small PR there, released together as 0.1.2:

1. `ContentView` in ANSI mode neither wraps nor tells the app its inner width, so the app
   has to guess the borders, scrollbar and outer margin (the spike guessed one or two
   columns wide and clipped text). Fix: let it take a function of the width (or a rich
   renderable) and call it at its real width, which also handles resize.
2. Enter on a tree node with children only expands or collapses it, so an outline cannot
   jump to a section that has subsections. Fix: an option where Enter activates the node
   and the arrow keys expand and collapse.
3. The `tree` tag drops its `id`, so `get_element_by_id` and `focus_element_by_id` cannot
   find it.
4. `{% tree height="fill" %}` crashes, though the docstring allows `"fill"`. (An
   `expanded=[...]` list also seemed not to apply at start; check whether that was misuse.)
5. Rich and Wijjit measure some emoji differently (`⏸️`, `🌱`), so those lines pad wrong.

Note for the app itself: an element's `id` binds it to the state key of the same name, so
the viewer's element ids must not collide with its own state keys.

Speed, on `CHANGELOG.md` (372 KB): parsing 0.57 s, paging instant, a resize 1.46 s,
because the text and the heading positions were each laid out separately. One pass that
returns both, cached per width, should roughly halve that; a burst of resizes should
re-render once.

**Layout in all2md.** A `src/all2md/tui/` package:

- `layout.py`: document and width to lines plus heading positions, one pass, cached. No
  Wijjit import, so it is tested on 3.10 too.
- `keys.py`: the key presets as data.
- `app.py`: builds the Wijjit app from a `Document`, so tests drive it through
  `WijjitHarness` without a file. Tests that need Wijjit skip when it is not installed.

**First version.** Body and outline (`o` toggles it, Tab moves focus); a status bar with
the file, the current section and the position; default and less/vim presets (`j`/`k`,
Space/`b`, `g`/`G`, `[`/`]` for the previous or next heading, `q`); scroll anchored to the
nearest heading on resize. The outline uses the tree; if it proves clunky, a flat indented
list in the style of doxx replaces it. Search, images and several files wait.

### Stage 3: search

`ContentView` has no find. Doing it upstream in Wijjit is the better home, since every
Wijjit app gets it: find over the visible text of ANSI content, highlight all matches,
`n`/`p` to step, match count to the status bar. The all2md side is only the key binding
and the status text. If upstream is not ready, a local fallback searches the plain
export of the rendered lines and scrolls to the hit, without highlighting.

### Stage 4: images

Stage 1 prints a placeholder; the viewer can use `ImageView`, which draws with colored
half-block characters and works in any color terminal. Real pixels need the graphics
protocols (Kitty, iTerm2/WezTerm, Sixel), with terminal detection and a fallback chain
like doxx's. That is again a better fit upstream in `ImageView` than in all2md. Images
come from the AST (`Image.url`, including `data:` URIs from `attachment_mode`), so the
parser side needs nothing new.

### Smaller items, any time after stage 1

- **Width cap.** glow wraps at about 80 columns on a wide terminal; prose is easier to
  read that way. An option with a sensible default (for example `min(terminal, 100)`),
  and `0` for full width.
- **Color depth.** doxx's `--color-depth 1/4/8/24`; rich exposes it as
  `Console(color_system=...)`. One flag.
- **Light/dark.** Pick the code theme and a few element styles from the terminal's
  background where it can be detected, falling back to today's defaults.

## Open questions

1. ✅ Command name for the viewer: `all2md read`, with `rcat -i` as a shortcut.
2. ✅ Format name for stage 1's renderer: `terminal`, listed in `list-formats`, so
   `--to terminal > out.ans` is discoverable.
3. Stage 3 and 4 upstream in Wijjit, or local first and upstreamed later. (Stage 2's
   gaps go upstream first.)
4. ✅ Merged table cells in the terminal: the content sits in the first cell and the
   spanned cells are blank (rich has no spans; repeating the content reads as data).

## Sources

- doxx: <https://github.com/bgreenwell/doxx>
- glow: <https://github.com/charmbracelet/glow>
- mdcat: <https://github.com/swsnr/mdcat>
- Wijjit: <https://github.com/thomas-villani/wijjit> (0.1.1 on PyPI)
