- **`all2md view` shows what it used to drop.** Footnotes: the HTML renderer wrote the
  footnotes section only for a standalone page, so with any template (`replace`, `inject`
  or `jinja`, and so in `view` and `serve`) each `[1]` linked to a definition the page
  never had; the section now closes the content. Math: the page loaded no math library,
  so LaTeX showed as `$...$` source; `view` and `serve` now load KaTeX when a page has
  math and typeset exactly the renderer's math elements, so a dollar sign in prose stays
  text (offline, the source shows as before). Images: a DOCX's or PDF's pictures came out
  as `<img src="">`, because `view` left attachments at their default of alt text; it now
  embeds them, unless the config sets `attachment_mode`. And an image named by path
  (`![](img/a.png)`) broke once the page was written to a temporary file; `view` now
  embeds local images, reading relative paths against the source's folder.
