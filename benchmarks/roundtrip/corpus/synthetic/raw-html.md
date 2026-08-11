A paragraph with an inline <span class="hl">raw HTML span</span> element.

Text with an <u>underlined</u> word and a <br> hard break tag.

A raw HTML block:

<div class="callout">
  <p>A paragraph inside a raw HTML block.</p>
</div>

A paragraph after the block. Raw HTML passes through by default, so both
oracles judge this document: it must be idempotent and must agree with the
reference renderer.
