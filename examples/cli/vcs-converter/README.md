# VCS Document Converter

Make binary documents git-friendly by committing a markdown sidecar next to each
one, so `git diff` shows prose instead of:

```
Binary files a/docs/spec.docx and b/docs/spec.docx differ
```

A pre-commit hook keeps the sidecars in sync. Reviewers read the markdown; the
binary stays the source of truth.

## Pick the right approach first

"Make binary documents git-friendly" has three solutions and **none of them
dominates**. This example implements the first. Read the table before adopting
it, because the honest answer for many repositories is one of the others.

|                            | **This example**<br>(committed sidecar) | git `textconv` | CI diff comment |
| -------------------------- | --- | --- | --- |
| How                        | hook writes a parallel `.md`, both committed | `.gitattributes` + local git config | a CI job renders the diff |
| `git blame` on prose       | ✅ | ❌ ignores `textconv` entirely | ❌ |
| Diff visible on GitHub     | ✅ | ❌ local only | ✅ |
| Merge conflicts resolvable | ✅ in text | ❌ | ❌ |
| Repository stays clean     | ❌ duplicated content, noisier commits | ✅ | ✅ |
| Setup per clone            | install the hook | `git config` per clone | none |

**Choose the sidecar (this example)** when you need `git blame` on the prose or
need to resolve merge conflicts in text. Those are the two things nothing else
can give you, and you pay for them with duplicated content.

**Choose `textconv`** when you only want readable local diffs and want the repo
to stay clean. It needs no code at all:

```bash
# .gitattributes (committed)
echo '*.docx diff=all2md' >> .gitattributes

# per clone, in local git config
git config diff.all2md.textconv all2md
git config diff.all2md.cachetextconv true
```

## Requirements

```bash
pip install "all2md[all]"     # or narrow it: all2md[docx,pptx,pdf]
```

Python 3.10+, and `python-docx` if you want to run `demo.py`.

Supported inputs are **`.docx`, `.pptx`, and `.pdf`** — the formats all2md can
parse. Legacy OLE formats (`.doc`, `.ppt`) are not supported and are
deliberately not scanned; run `all2md list-formats` to see the current set.

## Quick start

```bash
# 1. Copy the converter into your repository
mkdir -p .vcs-converter
cp vcs_converter.py .vcs-converter/

# 2. Install the pre-commit hook
cp pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 3. Convert what you already have
python .vcs-converter/vcs_converter.py batch

# 4. Commit the sidecars
git add .vcs-docs/
git commit -m "Add markdown sidecars for binary documents"
```

From here it is automatic — edit `docs/spec.docx`, `git add` it, and the hook
writes and stages `.vcs-docs/docs/spec.vcs.md` as part of your commit.

`demo.py` runs the whole thing end to end in a temporary directory if you want
to see it work before installing anything.

## Commands

All commands accept `--root` (repository root that paths resolve against;
defaults to the working directory) and `--config`.

| Command | What it does |
| --- | --- |
| `batch [--force]` | Convert every supported document under the root. Skips documents whose content hash is unchanged; `--force` reconverts everything. |
| `to-md FILE [--staged]` | Convert one document. `--staged` reads from the git index rather than the working tree. Prints the generated paths on stdout. |
| `to-binary FILE [--output PATH] [--in-place]` | Render a sidecar back to its original format. |
| `scan` | List the documents that would be converted. |
| `clean` | Delete the generated markdown directory. |

### `to-binary` does not overwrite your document

By default it writes **alongside** the original:

```bash
python vcs_converter.py to-binary .vcs-docs/docs/spec.vcs.md
# -> docs/spec.rebuilt.docx     (docs/spec.docx untouched)
```

This matters. Rendering markdown back to DOCX/PPTX/PDF cannot restore what
markdown never carried — styles, images, layout, tracked changes, embedded
objects. Overwriting the source destroys all of it, irreversibly. Use
`--output` to choose a path, or `--in-place` to accept that loss explicitly.

The realistic workflow is: **read** the markdown, **edit** the binary. Treat
markdown→binary as a recovery tool, not a round trip.

## Configuration

Create `vcs-converter.config.json` and pass it with `--config`:

```json
{
  "markdown_dir": ".vcs-docs",
  "track_metadata": true,
  "store_ast": false,
  "exclude_patterns": ["*.tmp.docx", "~$*.docx", "**/build/**", "**/dist/**"]
}
```

| Key | Default | Meaning |
| --- | --- | --- |
| `markdown_dir` | `.vcs-docs` | Where sidecars are written, relative to the root. |
| `track_metadata` | `true` | Write the `.vcs.json` sidecar. Required for `to-binary` and for content-hash change detection. |
| `store_ast` | `false` | Embed the full serialised AST in the metadata. **Leave this off** unless you need it — it puts a large, churn-heavy blob in a file whose purpose is readable diffs. |
| `exclude_patterns` | `[]` | Globs matched against both the file name and the full path, so `~$*.docx` and `**/build/**` both work. |

## What gets committed

```
docs/
  spec.docx                    # source of truth
.vcs-docs/
  docs/
    spec.vcs.md                # readable, diffable, blameable
    spec.vcs.json              # source path, format, SHA-256, doc metadata
```

The `.vcs.json` sidecar stores a SHA-256 of the source bytes. `batch` compares
it to decide what needs reconverting — **not** modification times, because git
does not preserve mtimes and a fresh clone would otherwise skip documents that
genuinely changed.

### Tracking only the markdown

If the binaries are large or regenerable, gitignore them and commit only the
sidecars:

```gitignore
*.docx
*.pptx
!.vcs-docs/**
```

Be clear-eyed about the trade: you can no longer recover the original document,
only a `--in-place`-style regeneration of it. Do this for drafts, not contracts.

## The pre-commit hook

The hook converts the **staged** content, not what happens to be on disk:

```bash
python vcs_converter.py to-md "$file" --staged
```

That distinction is the whole reason it works. With `git add -p`, or an
unstaged edit made while the commit was in flight, the working tree and the
index differ — and converting the working tree would commit a sidecar
describing content that was never committed.

It stages exactly the files each conversion produced (the converter prints them
on stdout) rather than blanket-adding `.vcs-docs/`, so stale output from an
earlier run never rides along in an unrelated commit.

Configure it with environment variables:

```bash
PYTHON=/path/to/python          # defaults to python3, then python
CONVERTER_SCRIPT=path/to/vcs_converter.py
```

### Using the pre-commit framework instead

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: vcs-convert
        name: Convert binary documents to markdown
        entry: python .vcs-converter/vcs_converter.py to-md
        language: system
        files: \.(docx|pptx|pdf)$
```

Note that this form passes working-tree paths, so it does not get the
staged-content guarantee above. The bundled hook is the safer option.

## Checking sidecars in CI

Fail the build when a sidecar is stale — someone committed a document without
the hook installed:

```yaml
- run: |
    python .vcs-converter/vcs_converter.py batch
    git diff --exit-code .vcs-docs/ || {
      echo "::error::Sidecars are out of date. Run 'vcs_converter.py batch' and commit."
      exit 1
    }
```

For scoring conversion *quality* rather than freshness, see
`examples/workflows/` and the [conversion-quality
gate](https://all2md.readthedocs.io/en/latest/github_action.html).

## Troubleshooting

**Hook doesn't run.** Check `ls -l .git/hooks/pre-commit` and that it is
executable. Run it directly with `bash .git/hooks/pre-commit` to see the error.

**"No python interpreter found."** The hook looks for `python3`, then `python`.
Set `PYTHON` explicitly if yours is elsewhere — a virtualenv interpreter is
usually what you want, since it is the one with `all2md` installed.

**"... is outside the repository root."** Paths resolve against `--root`, which
defaults to the working directory. Pass `--root /path/to/repo` when running from
somewhere else.

**Merge conflict in a `.vcs.md` file.** Resolve it in the markdown as you would
any text conflict, then resolve the binary separately — the sidecar and the
document are conflicting independently, and fixing one does not fix the other.

## Limitations

- Complex layout, precise styling, and embedded objects do not survive
  conversion to markdown. The sidecar is for *review*, not fidelity.
- `git blame` works on the sidecar, not the binary.
- Scanned PDFs convert only as well as the OCR does; check
  `all2md report file.pdf` before trusting a sidecar.
- Every commit that touches a document also touches its sidecar, which roughly
  doubles the file count in those commits.

## See also

- `examples/workflows/` — CI workflows for conversion quality
- `examples/cli/diff-in-ci.sh` — semantic cross-format diffing
- [all2md documentation](https://all2md.readthedocs.io/)

Licensed under the MIT license, same as all2md — see the repository root
`LICENSE`.
