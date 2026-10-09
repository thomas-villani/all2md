- **`all2md read` opens a tree of a folder's documents.** Given a folder, a glob pattern
  or several files (or nothing, on a terminal: the current folder), the viewer starts on a
  file tree of the documents this installation of all2md can read there (a format whose
  parser needs a package that is not installed is left out); Enter opens one, and `t` goes
  back to the tree with that file marked. Hidden, symlinked and tool folders
  (`node_modules`, `__pycache__`, `venv`, `site-packages`) are skipped, and the tree stops
  at 5,000 files. The status bar names the key that shows the keys (`?`), and
  `all2md read --help` lists them all.
