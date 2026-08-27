- **`SECURITY.md`'s hardening recipes now run.** Every one of the five "best
  practices" examples failed on import or construction: `validate_file_path` does
  not exist, `NetworkFetchOptions.enabled` is `allow_remote_fetch`,
  `HtmlOptions.network_fetch` is `network`, `HtmlOptions.sanitize_html` is
  `strip_dangerous_elements`, `BaseParserOptions.max_file_size` does not exist,
  and `ArchiveOptions` has none of `check_zip_bomb`/`max_archive_size`/
  `max_extracted_size`. A reader who copied the remote-fetch or sanitization
  recipe got a `TypeError`, not the hardening they asked for. All five now use
  the real API and are executed as written. The document also claimed a
  configurable per-file size limit, which the library has never had — the real
  cap is `max_asset_size_bytes` on extracted and fetched assets — and undercounted
  the core dependencies at two.
- **The documented GitHub Action pin moves with the release.** `README.md`,
  `docs/source/github_action.rst` and `action.yml` all showed
  `thomas-villani/all2md@v1.10.1`. The action resolves the library version from
  the tag it was referenced by, so copying the documented snippet gated your
  documents with all2md 1.10.1 — three releases behind — while the surrounding
  prose explained that the pin is what keeps thresholds meaningful. The pin is now
  a `bump-my-version` target, so it cannot fall behind again.
- **Sphinx no longer advertises image input.** `docs/source/index.rst` listed
  "Images (PNG/JPEG/GIF)" as a supported format. There is no image parser and
  `image` is not a `DocumentFormat`; a PNG falls through to the plain-text
  fallback and comes back as mojibake.
- **The converter comparison in `README.md` is dated and caveated.** It quoted the
  superseded 2026-08-19 reading (0.84% / 5.5% / 2.9%) as "the 2026-08 reading"
  when the lane now holds two, and described the corpus as one "the development
  work has never tuned against" — no longer true, since the column-layout work
  released since was developed against it. The figures are now the 2026-08-23
  reading, carrying both caveats.
