- **A detected PDF figure caption now reaches `Image.caption` instead of being
  discarded.** The caption was routed through `fallback_alt_text`, a dead path:
  extraction writes a non-empty placeholder alt text (`Image from page N`), so
  the fallback never fired and `include_image_captions=True` could not affect
  output in any attachment mode. The caption now rides on the node's `caption`
  field — visible page content set beside the figure, not a substitute for it —
  and the Markdown renderer already round-trips it as an italic line plus a
  marker comment. The default `alt_text` mode still extracts nothing; that is
  the remaining half of the defect and is tracked separately.
  ([#340](https://github.com/thomas-villani/all2md/issues/340))
