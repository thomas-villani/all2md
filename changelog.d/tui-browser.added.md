- **`all2md read` opens a tree of a folder's documents.** Given a folder, a glob pattern
  or several files (or nothing, on a terminal: the current folder), the viewer starts on a
  file tree of the documents all2md can read there; Enter opens one, and `t` goes back to
  the tree with that file marked. Hidden, symlinked and tool folders (`node_modules`,
  `__pycache__`, `venv`, `site-packages`) are skipped, and the tree stops at 5,000 files.
