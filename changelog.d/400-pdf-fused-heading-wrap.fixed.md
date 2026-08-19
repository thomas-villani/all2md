- **PDF: a subsection heading printed directly under its section heading is no
  longer fused into it.** The wrap-merge that reassembles a long title set on
  two printed lines had no width test, so `Methods` over `Study design` became
  one heading — and both section titles went missing, the largest single class
  (~30%) of the heading residual on the PMC born-digital corpus
  ([#400](https://github.com/thomas-villani/all2md/issues/400)). A line only
  wraps because it filled its measure, so the merge now requires the first line
  to fill at least `HEADING_WRAP_MIN_FILL` (0.8) of the two lines' shared
  width — a threshold read off 307 labeled merges: true wraps fill 0.852–1.0,
  the separable fused band 0.22–0.84. Pairs whose first line is the wider one
  (`Methods and Design` over `Study design`) remain geometrically inseparable
  and still merge; that residual is documented on the issue.
