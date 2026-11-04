- **`all2md serve` is gone, as announced in 1.18.** `all2md view` on a folder or a glob
  does what it did, so the command, its flags and its `[serve]` config section are
  removed, along with the server's single-document mode, which only `serve` could reach.
  Running `all2md serve` now prints an error pointing to `view`, rather than treating
  `serve` as a file name and converting the folder to stdout; a real file named `serve`
  still converts. A leftover `[serve]` section is ignored, and a Windows folder entry
  installed before 1.18 needs `all2md context-menu install` again.
