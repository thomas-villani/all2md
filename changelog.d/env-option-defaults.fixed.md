- **`ALL2MD_<OPTION>` environment variables now set converter options.** Each
  variable was read into the command-line default and then dropped, because only
  flags typed on the command line reached the options; `ALL2MD_PDF_PAGES`,
  `ALL2MD_ATTACHMENT_MODE` and the rest did nothing. They now apply as documented:
  above the built-in defaults, below a config file and explicit flags.
  `ALL2MD_FORMAT` and `ALL2MD_STRICT_ARGS`, which were never read, work too. A value
  that is not valid (a boolean that is not `true`/`false`/`1`/`0`/`yes`/`no`/`on`/`off`,
  a choice not on the list) is ignored with a warning instead of quietly becoming
  `false` or being passed through.
