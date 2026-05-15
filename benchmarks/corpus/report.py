"""Stratified markdown report from a benchmark results JSON."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence


@dataclass
class _Group:
    label: str
    timings: list[float]
    sizes: list[int]
    successes: int
    failures: int

    @property
    def total(self) -> int:
        return self.successes + self.failures


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _format_seconds(s: float) -> str:
    if s >= 60:
        return f"{s / 60:.1f}m"
    if s >= 1:
        return f"{s:.2f}s"
    return f"{s * 1000:.0f}ms"


def _format_size(b: int) -> str:
    if b >= 1 << 30:
        return f"{b / (1 << 30):.2f} GB"
    if b >= 1 << 20:
        return f"{b / (1 << 20):.2f} MB"
    if b >= 1 << 10:
        return f"{b / (1 << 10):.1f} KB"
    return f"{b} B"


def _group(rows: list[dict], key: str) -> dict[str, _Group]:
    groups: dict[str, _Group] = defaultdict(lambda: _Group("", [], [], 0, 0))
    for r in rows:
        bucket = r.get(key, "?")
        g = groups[bucket]
        g.label = bucket
        if r.get("error"):
            g.failures += 1
        else:
            g.successes += 1
            if r.get("duration_seconds") is not None:
                g.timings.append(float(r["duration_seconds"]))
                g.sizes.append(int(r["size_bytes"]))
    return groups


def _summary_table(groups: dict[str, _Group], header: str) -> list[str]:
    out = [
        "| " + header + " | n | ok | fail | total bytes | p50 | p95 | mean | MB/s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in sorted(groups):
        g = groups[name]
        if g.timings:
            p50 = _percentile(g.timings, 0.5)
            p95 = _percentile(g.timings, 0.95)
            mean = statistics.mean(g.timings)
            total_bytes = sum(g.sizes)
            total_seconds = sum(g.timings)
            mbps = (total_bytes / (1 << 20)) / total_seconds if total_seconds > 0 else 0.0
            out.append(
                f"| {name} | {g.total} | {g.successes} | {g.failures} | {_format_size(total_bytes)} "
                f"| {_format_seconds(p50)} | {_format_seconds(p95)} | {_format_seconds(mean)} | {mbps:.2f} |"
            )
        else:
            out.append(f"| {name} | {g.total} | {g.successes} | {g.failures} | - | - | - | - | - |")
    out.append("")
    return out


def _slowest(rows: list[dict], n: int = 10) -> list[str]:
    timed = [r for r in rows if r.get("error") is None and r.get("duration_seconds") is not None]
    timed.sort(key=lambda r: r["duration_seconds"], reverse=True)
    out: list[str] = []
    if not timed:
        out.append("_No successful conversions to rank._")
        out.append("")
        return out
    out.append("| # | source | format | size | time | doc |")
    out.append("|---:|---|---|---:|---:|---|")
    for i, r in enumerate(timed[:n], 1):
        out.append(
            f"| {i} | {r['source']} | {r['format']} | {_format_size(r['size_bytes'])} "
            f"| {_format_seconds(r['duration_seconds'])} | `{r['source_id']}` |"
        )
    out.append("")
    return out


def _failures(rows: list[dict]) -> list[str]:
    fails = [r for r in rows if r.get("error")]
    out: list[str] = []
    if not fails:
        out.append("_No failures._")
        out.append("")
        return out

    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in fails:
        by_type[r.get("error_type") or "Unknown"].append(r)

    for err_type in sorted(by_type, key=lambda k: -len(by_type[k])):
        rows_of_type = by_type[err_type]
        out.append(f"**{err_type}** ({len(rows_of_type)})")
        out.append("")
        for r in rows_of_type[:20]:
            out.append(f"- `{r['source']}/{r['source_id']}` ({_format_size(r['size_bytes'])}): {r['error']}")
        if len(rows_of_type) > 20:
            out.append(f"- _...and {len(rows_of_type) - 20} more_")
        out.append("")
    return out


def render_report(results_path: Path) -> str:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    rows: list[dict] = payload.get("results", [])
    run = payload.get("run", {})
    machine = run.get("machine", {})

    by_source = _group(rows, "source")
    by_format = _group(rows, "format")

    timed = [r for r in rows if r.get("error") is None and r.get("duration_seconds") is not None]
    total_seconds = sum(r["duration_seconds"] for r in timed)
    total_bytes = sum(r["size_bytes"] for r in timed)
    overall_mbps = (total_bytes / (1 << 20)) / total_seconds if total_seconds > 0 else 0.0

    lines: list[str] = []
    ts = run.get("timestamp", "")
    if ts:
        try:
            ts = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass
    lines += [
        "# all2md corpus benchmark",
        "",
        f"_Generated from `{results_path.name}` at {ts}_",
        "",
        f"- **all2md**: {machine.get('all2md_version', '?')} (`{machine.get('git_commit', '?')}`)",
        f"- **Python**: {machine.get('python', '?')}",
        f"- **Platform**: {machine.get('platform', '?')}",
        f"- **Documents**: {len(rows)} total, "
        f"{sum(1 for r in rows if not r.get('error'))} ok, "
        f"{sum(1 for r in rows if r.get('error'))} failed",
        f"- **Wall time** (successful conversions): {_format_seconds(total_seconds)} "
        f"over {_format_size(total_bytes)} = {overall_mbps:.2f} MB/s",
        "",
        "## Per-source",
        "",
    ]
    lines += _summary_table(by_source, "source")
    lines.append("## Per-format")
    lines.append("")
    lines += _summary_table(by_format, "format")
    n_slow = sum(1 for r in rows if r.get("error") is None and r.get("duration_seconds") is not None)
    lines.append(f"## Top {min(10, n_slow)} slowest")
    lines.append("")
    lines += _slowest(rows)
    n_fail = sum(1 for r in rows if r.get("error"))
    lines.append(f"## Failures ({n_fail})")
    lines.append("")
    lines += _failures(rows)
    return "\n".join(lines)


def write_report(results_path: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(results_path), encoding="utf-8")
    return out_path
