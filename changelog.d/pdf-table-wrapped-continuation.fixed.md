- **A wrapped table cell no longer leaves its second line standing as a row of its own.**
  Deciding which printed lines form one logical row is what a PDF table parser gets wrong
  when it gets a table wrong, and the five rules that decide it are precise but
  incomplete: measured against the best grouping any rule could reach, they make about
  nine in ten of their merges correctly and find only two thirds of the merges available.
  The rest leave a wrapped cell as an extra row, which interleaves the table column-wise
  and scrambles far more than the wrap itself. A sixth signal now runs as a post-pass: a
  line sitting within 0.28 of the table's median line height below the one above, not
  beginning with a capital, and filling at most 0.55 of the columns is a continuation.
  All three are required -- tight leading alone folds the dense rows of a table with no
  row padding, lower case alone folds a genuine row whose first cell is a unit or a gene
  name, and partial fill alone folds every half-empty row, which is a mistake this parser
  has made before. Because it is a post-pass it can only join lines the rules above left
  separate, and never overrides a merge one of them made.

  Both constants are taken from the middle of a joint plateau rather than an argmax. The
  fill share scores identically from 0.50 to 0.65 on both development corpora and 0.75
  splits them; the gap share is flat from 0.17 to 0.45 on the older corpus, plateaus
  between 0.22 and 0.35 on the newer one, and falls off a cliff at 0.45. The gap is read
  against the table's own line height and never in points: a variant fitted to absolute
  gaps scored 93% on the corpus it came from and below the majority baseline on a corpus
  held out from it. Measured against JATS ground truth, mean n-gram containment moves
  0.8689 to 0.8729 on the older corpus with two tables better and none worse, and 0.8439
  to 0.8473 on the newer one with eight better and three worse. The sealed holdout was
  not consulted.
