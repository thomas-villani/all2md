# Fixture Management

`tests/fixtures/documents/` combines two kinds of assets:

- **Manual fixtures** (e.g. `basic.docx`, `basic.pdf`) that were authored with
  third-party tools such as Microsoft Word or Acrobat. These files are kept
  under version control and regenerated manually when needed. Their provenance
  should be documented in pull requests when they change.
- **Deterministic fixtures** under `tests/fixtures/documents/generated/` that can
  be reproduced from code. Use the CLI provided in
  `tests/fixtures/generators/__main__.py` to (re)build them.

## Regenerating deterministic fixtures

```bash
python -m fixtures.generators            # generate everything
python -m fixtures.generators --list     # list targets
python -m fixtures.generators csv        # specific fixture group/name
python -m fixtures.generators csv-basic --force
```

The command writes files into `documents/generated/`. When optional libraries
such as `odfpy`, `ebooklib`, or `openpyxl` are missing, the generator will skip
those fixtures and report the missing dependency.

## Manual fixtures

Manual assets remain in `documents/` (outside the `generated/` directory). Do
not overwrite them from the CLI. If you need to update a manual fixture, follow
the documented steps for the tool that created it and describe the changes so
the provenance remains clear.
