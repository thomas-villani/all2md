"""Which scored dimensions may support a verdict, and which may only be evidence.

This is one declaration shared by both external-ground-truth lanes, and it exists because
they disagreed. The born-digital lane measured `block_structure_similarity` against
deliberately damaged output, found it unfit, and refused to gate on it. The scanned-page
gate went on comparing the same dimension against its baseline every month. One project
cannot hold both positions, and the one supported by measurement is the refusal.

Kept deliberately free of heavy imports. `benchmarks.omnidocbench.gate` is a pure JSON
validator that never imports the parser it is judging, and importing the oracle module here
would drag `all2md.ast` into it and give the gate an opinion about the code under test.
"""

from __future__ import annotations

from typing import Mapping

#: Dimensions the oracle records but no lane may gate on, mapped to the measurement that
#: disqualified each.
#:
#: A dimension named here is still computed, still recorded, and still fails the gate when it
#: is missing, malformed, or internally inconsistent with its own sample scores. What is
#: skipped is the comparison of its *value* against the baseline: a number that moves the
#: wrong way under damage cannot support a verdict in either direction, so a drift in it is
#: not evidence of a regression and a rise in it is not evidence of an improvement.
UNGATEABLE: Mapping[str, str] = {
    "block_structure_similarity": (
        "compares kind sequences without inspecting the text under a block, so content-free "
        "output scores 1.0 (issue #256); eleven text categories collapse to `text_block`, so "
        "fully reversed output scores exactly 1.0 on 153 of the 981 pinned pages; and on the "
        "born-digital lane it separates own-page from wrong-page output by only ~0.06 while "
        "*rising* when half the emitted content is deleted, which rewards dropping blocks"
    ),
}
