"""Score the committed corpus and print the defect ledger.

    python -m benchmarks.docx
    python -m benchmarks.docx --family tracked --show-output

CI-safe. Loads the corpus (verifying every digest), converts each document with a
pinned options profile, runs the family checks, and reports failing checks grouped by
family. **Ungated on fidelity by design, crash-gated always** -- the exit status is
non-zero only when the lane itself breaks: a corpus that fails verification, a case
that crashes the parser, or a *control* that fails. A control failing means the lane
is wrong, not the parser.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.docx.corpus import Case, CorpusError, load_corpus, provenance  # noqa: E402
from benchmarks.docx.oracles import Finding, score_case  # noqa: E402

#: The one options profile every scoring run uses, recorded so a reading can be
#: reproduced. `attachment_mode` is pinned because the default makes image URLs
#: unstable between runs, which would show up as spurious churn.
PROFILE: dict[str, Any] = {
    "attachment_mode": "base64",
}


def convert(case: Case) -> str:
    import all2md

    return str(all2md.to_markdown(str(case.path), **PROFILE))


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the DOCX corpus and print the defect ledger.")
    parser.add_argument("--family", nargs="*", default=None, help="limit to these families")
    parser.add_argument("--show-output", action="store_true", help="print each conversion")
    args = parser.parse_args()

    try:
        cases = load_corpus()
    except CorpusError as exc:
        print(f"corpus verification failed: {exc}", file=sys.stderr)
        return 1

    if args.family:
        cases = [c for c in cases if c.family in set(args.family)]
        if not cases:
            print("no cases matched", file=sys.stderr)
            return 1

    meta = provenance()
    print(
        f"{len(cases)} case(s) | Word {meta.get('word_build', '?')} | "
        f"{meta.get('wordlive_version', '?')} | generated {meta.get('generated_utc', '?')}\n"
    )

    findings: list[Finding] = []
    crashed: list[str] = []
    for case in sorted(cases, key=lambda c: c.case_id):
        try:
            out = convert(case)
        except Exception as exc:  # noqa: BLE001 - a crash is the one hard failure
            crashed.append(f"{case.case_id}: {type(exc).__name__}: {exc}")
            continue
        if args.show_output:
            print(f"--- {case.case_id} ---\n{out}\n")
        findings.extend(score_case(case, out))

    by_family: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        by_family[finding.family].append(finding)

    print("=== defect ledger ===\n")
    print(f"{'family':13s} {'checks':>7s} {'failing':>8s}")
    total_failed = 0
    for family in sorted(by_family):
        failed = [f for f in by_family[family] if not f.ok]
        total_failed += len(failed)
        print(f"{family:13s} {len(by_family[family]):7d} {len(failed):8d}")
    print(f"{'TOTAL':13s} {len(findings):7d} {total_failed:8d}\n")

    if total_failed:
        print("=== failing checks ===\n")
        for family in sorted(by_family):
            for finding in by_family[family]:
                if not finding.ok:
                    print(f"  {finding}")
        print()

    controls = {c.case_id for c in cases if c.is_control}
    control_failures = [f for f in findings if not f.ok and f.case_id in controls]
    if control_failures:
        print("=== CONTROL FAILURES -- these are lane bugs, not parser defects ===\n", file=sys.stderr)
        for finding in control_failures:
            print(f"  {finding}", file=sys.stderr)

    if crashed:
        print("=== crashes ===\n", file=sys.stderr)
        for line in crashed:
            print(f"  {line}", file=sys.stderr)

    # Crash-gated, and control-gated. Never gated on the defect count itself: this lane
    # exists to open a defect stream, and a gate on it would punish finding things.
    return 1 if (crashed or control_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
