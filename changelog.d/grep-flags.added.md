- **`all2md grep` gains grep's `-q`, `-l`, `-c`, `-v` and `-w`.** `-q` prints nothing and
  answers by exit status, `-l` names each document with a match, `-c` counts matching
  lines per document (0 included), `-v` selects the lines that do not match, and `-w`
  matches whole words only. Piped input is now named `(standard input)`; it used to be
  shown as the raw bytes it held.
