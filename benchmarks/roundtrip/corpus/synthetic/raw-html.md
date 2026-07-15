A paragraph with an inline <span class="hl">raw HTML span</span> element.

Text with an <u>underlined</u> word and a <br> hard break tag.

A raw HTML block:

<div class="callout">
  <p>A paragraph inside a raw HTML block.</p>
</div>

A paragraph after the block. Raw HTML is escaped by policy under all2md's
default `html_passthrough_mode="escape"`, so the HTML-equivalence oracle skips
this document; idempotency should still hold.
