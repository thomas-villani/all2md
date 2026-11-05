- `--template-docx` now warns on stderr when the output isn't Word, for example with no `--out` or with
  `--out answer.pdf`, instead of silently ignoring the template. The conversion still runs. A template set
  in a config file doesn't trigger the warning.
