- **Rich output's install hint named an extra that does not exist.** The CLI said
  `pip install all2md[rich]`, in the warning printed when rich is missing, the `--rich`
  option group's help and the `config generate` template; `rich` comes with `cli_extras`
  (and `all`), and the hints now say so. The docs had the same mistake.
- **The example Jinja templates render with the default options.** All four
  (`ansi-terminal`, `custom-outline`, `docbook`, `metadata.yaml`) read `metadata.title`,
  which `strict_undefined` (on by default) turns into an error for any document without a
  title. They now use `metadata.get(...)`, and a test renders each one.
- **Docs: reading documents in the terminal.** The README introduces `rcat` (`all2md FILE
  --rich`) as a terminal reader for every supported format, and `cli.rst` documents it,
  along with `-f` for `--force-rich`, `ALL2MD_PAGER`, the correct `ALL2MD_RICH_NO_WORD_WRAP`
  (it said `ALL2MD_RICH_WORD_WRAP`) and PowerShell's `$env:PAGER`. `--pager` is described as
  the explicit opt-in it is, not as automatic paging for long documents.
