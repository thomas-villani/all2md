- **PDF: a single block printed across the gutter no longer erases a two-column page**
  (#440). The channel test merges the blocks' x-intervals and reads the complement as the
  gutter, which is all-or-nothing: one block bridging it fuses the two runs, the page has
  no channel at all, and it is read line by line in y — so both columns interleave and
  every adjacency dies, even though dozens of blocks on each side agree where the gutter
  is. #445 and #450 handled the common culprit, page *furniture*, by trimming bands off
  the ends; a block in the middle of the body is not reachable that way, because no band
  trim will ever discard it. A last-resort search now asks the question the other way
  round — for each candidate x, how many blocks does it cut? — and tolerates one crosser.
  Three guards keep it honest. The page must name exactly **one** gutter: several is the
  signature of an undetected table rather than a layout, and one held-out page offers
  twelve. The two sides must be **columns**, comparable in width: a title page sets its
  affiliations 123pt wide beside a 317pt abstract, and reading that as two columns hoists
  the introduction above the article's own title (distance from the page centre does *not*
  separate the two — the sidebar and a genuinely repaired reference page sit 8.9% off it
  each). And it runs only after every other detector has read the page as a **single
  column**, because that single-column reading is the defect it repairs; run any earlier
  it overrides the gap fallback on five pages and costs 20 supported n-grams. Across the
  110-article held-out corpus it moves 4 pages of 1,184, all of them from one column to
  two, for **+31 supported n-grams and one block's containment rising 0.93 → 1.00**, with
  no article and no block worse. Nothing is discarded: the crossing block is still
  emitted, and every block on the page still votes.
