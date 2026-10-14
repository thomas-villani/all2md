- **The Org parser reads nested lists.** A sub-item is marked only by its indentation,
  and the parser stripped each line before reading its marker, so a nested bullet came
  back as a sibling of its parent and a nested numbered item was folded into the
  parent's text (`parent 1. child`). A nested list of either kind now stays under its
  item, text after a nested list returns to the parent, and bullets followed by
  numbered items at the same level read as two lists.
  ([#570](https://github.com/thomas-villani/all2md/issues/570))
