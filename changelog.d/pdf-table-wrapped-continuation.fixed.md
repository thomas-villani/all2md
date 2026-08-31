Recovered table rows whose wrapped cell text was left standing as a row of its own. A
printed line that sits at wrap leading, does not begin with a capital and fills only part
of the grid is now folded into the row above, as a post-pass over the existing grouping
rules -- so it can only join lines those rules left separate, never split what they joined.
Measured against the JATS ground truth on both PMC development corpora: mean table
containment 0.8689 to 0.8729 on dev (2 tables better, none worse) and 0.8439 to 0.8473 on
the held-out tuned corpus (8 better, 3 worse).
