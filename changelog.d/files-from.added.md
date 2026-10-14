- **`--files-from` takes input paths from a list, so a picker can drive any command.**
  `fzf | all2md read --files-from -` opens the document you pick in the terminal
  viewer, and `fzf -m --print0 | all2md grep invoice --files-from - --null` searches
  the ones you pick. The flag follows `tar -T` and `rsync --files-from`: one path per
  line from a file or `-` (stdin), `#` comments, and `--null` for NUL-separated lists
  from `find -print0` or `fzf --print0`. It works on the conversion and on `read`,
  `view`, `grep`, `search`, `report`, `lint`, `chunk`, `roundtrip`, `optimize`,
  `llm-minify` and `generate-site`. `read` takes the keyboard back from the terminal
  after reading the list from stdin. On the conversion it is the new name of
  `--batch-from-list`, which keeps working.
