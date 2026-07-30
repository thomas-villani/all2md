# Markdown roundtrip fidelity benchmark

Measures whether `Markdown -> AST -> Markdown` preserves a document. Complements
the other benchmarks: `benchmarks/corpus/` times *to-markdown* conversion and
`benchmarks/startup.py` times cold start; this one checks **fidelity**.

## Run it

```bash
python -m benchmarks.roundtrip              # per-document pass/fail table
python -m benchmarks.roundtrip --show-diff   # + unified diffs for failures
python -m benchmarks.roundtrip --json out.json
```

Exit code is non-zero if any oracle failed (policy skips don't count), so it can
double as an ad-hoc check.

## It is a blocking CI gate

The `Roundtrip Fidelity Gate` job in `.github/workflows/ci.yml` runs this on every
push and PR, and `release` lists it in `needs:` — so a fidelity regression fails
the build and blocks a release rather than waiting for someone to notice. On red,
CI re-runs with `--show-diff` so the diffs are already in the log.

### Expected failures

`main` is green with one known failure, so the gate needs a way to say "this one
is accepted" without going blind. `EXPECTED_FAILURES` in `run.py` maps
`(document, oracle) -> reason`:

| Status | Meaning |
|---|---|
| `pass` / `FAIL` | not allowlisted; `FAIL` is red |
| `XFAIL` | allowlisted and still failing — green, as documented |
| `XPASS` | allowlisted but now **passing** — **red** |
| `SKIP` | a policy skip; never judged, never counted |

`XPASS` is red on purpose, and so is a **stale** entry (one no document/oracle
evaluates any more, e.g. after a rename or a newly-added policy skip). Both mean
the table has started lying about the codebase, so it must be updated in the same
commit that changes the behavior. Without that, an allowlist decays into a
permanent excuse list and the ratchet quietly stops being one.

Currently allowlisted: **`raw-html:idempotency`** — the escape policy
(`html_passthrough_mode="escape"`) turns `<div>` into `&lt;div&gt;` on the second
pass. That is a deliberate security posture, not a roundtrip bug; it is the same
root cause as the `html_equivalence` policy skip below. Never add an entry to
silence a genuine regression.

## Two oracles

Each document is judged by two independent oracles (`oracles.py`); a loss has to
slip past both:

- **idempotency** — render twice, assert the output is a fixed point
  (`once == twice`). Cheap, deterministic, reference-free. This is the exact
  criterion the recent list/footnote roundtrip fixes (#84/#85/#91) used.
- **html_equivalence** — render the original and the roundtripped Markdown both
  to HTML with a fixed reference renderer (mistune, configured with all2md's
  default plugin set) and diff a normalized form. Independent of all2md's AST
  model and Markdown renderer — where losses actually occur — so it catches
  first-render loss that idempotency can't see.

  *Caveat:* all2md also parses with mistune, so this oracle is independent of the
  AST + render halves of the pipeline, not of the parse half. That matches our
  failure surface but is not a fully third-party judge.

Documents containing raw HTML are **skipped** by the HTML oracle: all2md escapes
raw HTML by policy (`html_passthrough_mode="escape"`), so a difference there is
expected, not a bug.

## Corpus

Phase 0/1 ships the **synthetic** corpus only: labeled Markdown under
`corpus/synthetic/`, one construct family per file plus a `kitchen-sink`
document that combines them. It deliberately covers the extensions the
CommonMark / GFM spec suites don't (footnotes, definition lists, math,
admonitions, mark/insert/super/subscript) and the specific shapes behind
#84/#85/#91.

The CommonMark / GFM spec suites are a planned follow-up (Phase 2); the `Case`
shape in `corpus.py` is already source-agnostic to accommodate them.

## Guarding the judge

`tests/unit/test_roundtrip_benchmark.py` proves the oracles can both pass and
fail: each is exercised on a faithful case and a deliberately broken one, and the
HTML normalizer is checked to ignore incidental whitespace while still detecting
a collapsed paragraph (the #85 loss shape). An oracle that cannot fail is
worthless.

The same file pins the **gate's** three red paths (`gate_failed`): a real oracle
failure, an `XPASS`, and a stale allowlist entry. A gate that cannot go red is
worse than no gate, because it launders "we didn't measure" into "we measured and
it's fine."

Worth knowing when you extend this: dropping a construct *entirely* is trivially
idempotent — both passes lack it — so `idempotency` stays green and only
`html_equivalence` catches it. Verified by deleting thematic-break rendering,
which failed 2 documents on the HTML oracle and 0 on idempotency. Neither oracle
subsumes the other; keep both.
