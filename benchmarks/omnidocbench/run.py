"""Run the pinned OmniDocBench AST fidelity benchmark end to end."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from .benchmark import evaluate_corpus, load_ground_truth, normalize_results, write_result
from .corpus import load_corpus
from .gate import compare, emit_baseline, format_verdict

HERE = Path(__file__).resolve().parent
DEFAULT_CACHE = HERE / ".cache"
DEFAULT_BASELINE = HERE / "baseline.json"
DEFAULT_RESULT = DEFAULT_CACHE / "results" / "current.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmarks.omnidocbench.run", description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="revision-qualified corpus cache")
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT, help="where to write the normalized result")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="committed ratchet baseline")
    parser.add_argument(
        "--download-workers",
        type=int,
        default=8,
        help="corpus download and first-pass validation parallelism; page conversion is always serial",
    )
    parser.add_argument("--limit", type=int, help="run a deterministic incomplete smoke subset")
    parser.add_argument("--ocr-languages", default="eng+chi_sim", help="Tesseract languages the pinned policy requests")
    parser.add_argument(
        "--skip-gate",
        action="store_true",
        help="measure without comparing the committed baseline",
    )
    parser.add_argument(
        "--allow-conversion-failures",
        action="store_true",
        help="allow a --skip-gate measurement to succeed with recorded conversion failures",
    )
    parser.add_argument("--write-baseline", type=Path, help="write a baseline from a complete run")
    parser.add_argument(
        "--default-tolerance",
        type=float,
        default=0.005,
        help="per-metric tolerance recorded in an emitted baseline",
    )
    parser.add_argument("--download-only", action="store_true", help="populate and validate the cache, then stop")
    return parser


def _git_identity() -> tuple[str, bool]:
    """Record the source commit and whether the worktree differs from it."""
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot record the all2md source identity: {exc}") from exc
    commit = commit_result.stdout.strip()
    if len(commit) != 40:
        raise RuntimeError(f"git returned an invalid all2md commit: {commit!r}")
    return commit, bool(status_result.stdout.strip())


def _tessdata_dir() -> Path:
    """Resolve the Tesseract language-data directory the OCR engine will actually load."""
    try:
        completed = subprocess.run(
            ["tesseract", "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot list the installed Tesseract languages: {exc}") from exc
    listing = completed.stdout + completed.stderr
    match = re.search(r'available languages in "?([^"\n]+?)"? \(', listing)
    if match is None:
        raise RuntimeError(f"cannot resolve the Tesseract language-data directory from: {listing!r}")
    return Path(match.group(1))


def _language_digests(languages: str) -> dict[str, str]:
    """Digest every requested traineddata file so OCR model drift changes ratchet identity."""
    tessdata = _tessdata_dir()
    digests: dict[str, str] = {}
    for language in sorted({name for name in languages.split("+") if name}):
        path = tessdata / f"{language}.traineddata"
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(f"cannot read pinned OCR language data {path}: {exc}") from exc
        digests[f"tessdata_{language}_sha256"] = hashlib.sha256(payload).hexdigest()
    if not digests:
        raise RuntimeError("no OCR languages were requested")
    return digests


def _parser_runtime(ocr_languages: str) -> dict[str, str]:
    """Record the parser binaries, locked packages, and OCR models that affect the AST."""
    distributions = {
        "pymupdf": "PyMuPDF",
        "pymupdf_layout": "pymupdf-layout",
        "pytesseract": "pytesseract",
        "pillow": "Pillow",
    }
    try:
        versions = {name: metadata.version(distribution) for name, distribution in distributions.items()}
        completed = subprocess.run(
            ["tesseract", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (metadata.PackageNotFoundError, OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "cannot identify the pinned PDF/OCR runtime; install the pdf_layout and ocr extras " f"and Tesseract: {exc}"
        ) from exc
    first_line = completed.stdout.splitlines()
    if not first_line or not first_line[0].strip():
        raise RuntimeError("tesseract --version returned no version")
    versions["tesseract"] = first_line[0].strip()
    versions.update(_language_digests(ocr_languages))
    return versions


def _read_json(path: Path) -> dict[str, Any]:
    """Read the baseline through the ratchet's strict loader, not permissive json.loads.

    The production entrypoint is the only path CI runs, so rejecting duplicate keys and non-finite
    literals has to happen here or it never happens where the baseline is trusted.
    """
    from .gate import _load_json

    try:
        payload = _load_json(path)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected a JSON object in {path}")
    return payload


def run(args: argparse.Namespace) -> int:
    """Execute the requested benchmark operation."""
    if args.download_workers < 1:
        raise ValueError("--download-workers must be a positive integer")
    if args.limit is not None and not args.skip_gate:
        raise ValueError("--limit requires --skip-gate because an incomplete corpus cannot pass the ratchet")
    if args.limit is not None and args.write_baseline:
        raise ValueError("--write-baseline requires the complete 981-page corpus")

    git_commit = ""
    worktree_dirty = False
    if not args.download_only:
        git_commit, worktree_dirty = _git_identity()
        if args.write_baseline and worktree_dirty:
            raise RuntimeError("cannot write a baseline from a dirty worktree")

    baseline = None
    if not args.skip_gate and not args.write_baseline and not args.download_only:
        # Before the first accepted baseline the gate must report ABSENT_BASELINE
        # red, not an unreadable-file error: bootstrap runs record one instead.
        baseline = _read_json(args.baseline) if args.baseline.is_file() else {}

    snapshot = load_corpus(args.cache_dir, limit=args.limit, workers=args.download_workers)
    print(
        f"OmniDocBench {snapshot.revision}: validated {len(snapshot.pages)}/{snapshot.expected_pages} PDFs",
        flush=True,
    )
    if args.download_only:
        return 0
    parser_runtime = _parser_runtime(args.ocr_languages)

    ground_truth = load_ground_truth(snapshot)
    evaluations = evaluate_corpus(
        snapshot,
        ground_truth,
        ocr_languages=args.ocr_languages,
    )
    failures = sum(result.error_type is not None for result in evaluations)
    print(
        f"Projected and scored {len(evaluations) - failures}/{len(evaluations)} pages; failures={failures}",
        flush=True,
    )
    normalized = normalize_results(
        snapshot=snapshot,
        ground_truth=ground_truth,
        evaluations=evaluations,
        all2md_commit=git_commit,
        worktree_dirty=worktree_dirty,
        parser_runtime=parser_runtime,
        ocr_languages=args.ocr_languages,
    )
    write_result(normalized, args.output)
    print(f"Wrote {args.output}", flush=True)

    if args.write_baseline:
        if not snapshot.complete:
            raise RuntimeError("cannot write a baseline from an incomplete corpus")
        candidate = emit_baseline(normalized, default_tolerance=args.default_tolerance)
        candidate_verdict = compare(normalized, candidate)
        if candidate_verdict.failed:
            raise RuntimeError("refusing to write an invalid baseline:\n" + format_verdict(candidate_verdict))
        write_result(candidate, args.write_baseline)
        print(f"Wrote reviewable baseline {args.write_baseline}", flush=True)
        return 0
    if args.skip_gate:
        return 1 if failures and not args.allow_conversion_failures else 0

    verdict = compare(normalized, baseline)
    print(format_verdict(verdict))
    return 1 if verdict.failed else 0


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the benchmark."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"OMNIDOCBENCH ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
