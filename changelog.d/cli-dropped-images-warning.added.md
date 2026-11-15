- **The CLI says when it leaves images out.** Images stay off by default (secure by default), so a
  document's pictures used to vanish without a word. A conversion that drops any now prints
  "N images were dropped, use `--attachment-mode base64` to include." on stderr. Typing any
  `--attachment-mode` (or a format's own) is a choice and silences it.
