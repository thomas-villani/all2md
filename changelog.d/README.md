# changelog.d

Pending changelog entries, one file per pull request. **Add a fragment here instead
of editing `CHANGELOG.md`.**

`CHANGELOG.md` is a single file that every branch appends to at the same place, under
`## [Unreleased]`, which made it a guaranteed merge conflict in any sweep that landed
more than one PR. A fragment is a new file, so two branches never touch the same
lines. `scripts/compile_changelog.py` folds the fragments into `CHANGELOG.md` when a
release is cut, and deletes them.

## Filename

```
<slug>.<category>.md
```

- **slug** — anything that identifies the change: the branch name, the PR or issue
  number, a couple of words. It is only there to keep filenames distinct, and it does
  not appear in the compiled changelog.
- **category** — one of `added`, `changed`, `deprecated`, `removed`, `fixed`,
  `security`. It selects the `###` section the entry lands in.

Examples: `338-figure-captions.added.md`, `pdf-ruling-lines.fixed.md`,
`347.changed.md`.

## Contents

One or more complete Markdown bullets, written exactly as they should read in
`CHANGELOG.md` — the compiler copies them verbatim into the matching section. Match
the house style of the existing entries: a bolded sentence naming the change, then
prose explaining what was wrong, what it does now, and what was deliberately *not*
done. Wrap at the width the rest of the file uses and indent continuation lines by
two spaces. Link the issue where there is one.

```markdown
- **A PDF list no longer nests a parent item underneath its own child.**
  `_determine_list_level_from_x` assigned each newly seen indent the level
  `len(x_levels)` -- arrival order -- and never compared the x-coordinates to each
  other. Levels are now assigned by comparing x.
  ([#340](https://github.com/thomas-villani/all2md/issues/340))
```

Put several bullets in one fragment when a PR makes several distinct changes in the
same category, and add one fragment per category when it spans categories.

## Checking your fragment

```bash
python scripts/compile_changelog.py --check
```

This validates every fragment's category and shape and writes nothing. It fails on an
unknown category, an empty file, or content that does not begin with a `- ` bullet.

## At release time

```bash
python scripts/compile_changelog.py --version 1.13.0
```

Everything under `## [Unreleased]` — the fragments and any entries written into the
section by hand — moves into a new `## [1.13.0] - <today>` section, the link
references at the bottom of the changelog are updated, and the consumed fragments are
deleted. Add `--dry-run` to see what it would do first, or `--date YYYY-MM-DD` to set
the date explicitly.
