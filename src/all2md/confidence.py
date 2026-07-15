#  Copyright (c) 2025 Tom Villani, Ph.D.
# src/all2md/confidence.py
"""Conversion confidence reporting — a structured "quality card".

Converters already compute a raft of sanity signals while parsing: how much
meaningful text a PDF page yielded, whether a detected "table" was really a
decorative frame (empty-cell ratio) or a table-of-contents (dot-leader ratio),
how many pages had to fall back to OCR, whether an archive entry could not be
parsed, and so on. Historically these were consumed for a single accept/reject
decision and then discarded (surviving only as a ``logger.debug`` line).

This module captures those signals as a structured :class:`ConfidenceReport`
that rides on ``Document.metadata["confidence"]``. It gives callers a
reference-free read on how much to trust a conversion, and — because it emits a
single ``0-100`` scalar ``score`` — doubles as the fitness function the
``optimize`` capstone hill-climbs on (no ground-truth reference needed).

Two kinds of evidence feed a report:

* **signals** — continuous per-document metrics (``meaningful_chars``,
  ``chars_per_page``, ``ocr_page_fraction``, table/image counts). The PDF parser
  is by far the richest producer; most other formats leave these empty.
* **degraded_events** — discrete incidents where the converter knowingly lost or
  approximated content (a table rejected as non-tabular, an archive member that
  would not parse, a readability/alt-text fallback taken, an OCR failure). Every
  parser can record these through ``BaseParser._record_degraded``.

The report is intentionally a plain, JSON-safe structure so it serializes with
the rest of the AST metadata and round-trips through ``ast_to_json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["info", "warn", "error"]
#: ``"not_assessed"`` is distinct from ``"high"``: it means the converter ran no
#: quality instrumentation at all (no scored signals, no degraded events), so the
#: vacuous 100 must not be read as "verified clean". See :func:`score_conversion`.
Band = Literal["high", "medium", "low", "not_assessed"]

# --- Scoring model -----------------------------------------------------------
#
# A conversion starts from a perfect 100 and loses points for evidence of lost
# or low-fidelity content. The weights are deliberately modest and exposed as
# module constants so the ``optimize`` capstone (and tests) can reason about —
# and tune — them. The score is reference-free: it only inspects what the
# converter itself observed, never a ground-truth original.
#
# A subtlety this creates: a converter that observed *nothing* (no scored signals,
# no degraded events) also starts and stays at 100. That is not a clean bill of
# health, it is the absence of a detector, so such a report is banded
# ``"not_assessed"`` rather than ``"high"`` — see ``score_conversion``.

#: Points a fully text-empty page-image document can lose to the text-density
#: penalty. Recovering that text (e.g. by enabling OCR) claws these points back,
#: which is what makes the score usable as an optimizer fitness function.
TEXT_DENSITY_MAX_PENALTY = 45.0

#: Meaningful characters per page at or above which the text-density penalty is
#: fully waived. Below it the penalty ramps linearly to ``TEXT_DENSITY_MAX_PENALTY``.
TEXT_DENSITY_FLOOR_CPP = 200.0

#: Points lost when the entire document had to be recovered via OCR. OCR text is
#: serviceable but lower-fidelity than a native text layer, so reliance on it is
#: a mild — not catastrophic — confidence hit, scaled by the OCR page fraction.
OCR_RELIANCE_MAX_PENALTY = 12.0

#: Per-event penalty by severity. ``info`` events are surfaced but never scored
#: (e.g. dropping a decorative sub-20px image is usually correct).
SEVERITY_PENALTY: dict[str, float] = {"info": 0.0, "warn": 4.0, "error": 10.0}

#: Ceiling on the total penalty from ``degraded_events`` so a single pathological
#: document (hundreds of unparsed archive members) cannot swamp every other
#: signal. The score is clamped to ``[0, 100]`` regardless.
DEGRADED_EVENT_PENALTY_CAP = 45.0

#: Score at or above which confidence is reported as ``"high"``.
BAND_HIGH_THRESHOLD = 80
#: Score at or above which confidence is reported as ``"medium"`` (below is ``"low"``).
BAND_MEDIUM_THRESHOLD = 50

#: Signal keys that actually feed the score: the text-density and OCR-reliance
#: penalties read exactly these. A report carrying none of them *and* no degraded
#: events was never quality-assessed -- its 100 is the absence of a detector, not
#: a clean bill of health -- so it is banded ``"not_assessed"``. Keep this in sync
#: with the signals :func:`_text_density_penalty` / :func:`_ocr_reliance_penalty` read.
SCORED_SIGNAL_KEYS: tuple[str, ...] = ("chars_per_page", "ocr_page_fraction")


@dataclass
class DegradedEvent:
    """A single incident where a converter knowingly lost or approximated content.

    Parameters
    ----------
    parser : str
        Short label of the producing parser (e.g. ``"pdf"``, ``"archive"``).
    kind : str
        Machine-readable event category (e.g. ``"table_rejected"``,
        ``"unparsed_member"``, ``"readability_fallback"``, ``"ocr_failed"``).
    count : int, default = 1
        How many times this event occurred. Repeated events of the same
        ``(parser, kind, detail, severity)`` are coalesced with their counts summed.
    detail : str or None, default = None
        Optional human-readable qualifier (e.g. the rejection reason).
    severity : {"info", "warn", "error"}, default = "warn"
        How much the event should weigh on the score.

    """

    parser: str
    kind: str
    count: int = 1
    detail: str | None = None
    severity: Severity = "warn"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict, omitting ``detail`` when unset."""
        data: dict[str, Any] = {
            "parser": self.parser,
            "kind": self.kind,
            "count": self.count,
            "severity": self.severity,
        }
        if self.detail is not None:
            data["detail"] = self.detail
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DegradedEvent":
        """Reconstruct a :class:`DegradedEvent` from its :meth:`to_dict` form."""
        return cls(
            parser=str(data.get("parser", "")),
            kind=str(data.get("kind", "")),
            count=int(data.get("count", 1)),
            detail=data.get("detail"),
            severity=data.get("severity", "warn"),
        )


@dataclass
class ConfidenceReport:
    """Structured "quality card" summarizing how much to trust a conversion.

    Parameters
    ----------
    score : int
        Overall confidence, ``0`` (untrustworthy) to ``100`` (no problems observed).
    band : {"high", "medium", "low"}
        Coarse bucket derived from ``score`` for quick human/CLI display.
    producer : str
        Label of the primary producing parser (e.g. ``"pdf"``).
    signals : dict
        Continuous per-document metrics. Keys are producer-specific; common PDF
        keys include ``meaningful_chars``, ``chars_per_page``, ``page_count``,
        ``ocr_page_fraction``, ``tables_detected``, ``tables_rejected``,
        ``images_dropped`` and ``running_headings_demoted``.
    degraded_events : list of DegradedEvent
        Discrete lost/approximated-content incidents recorded during parsing.

    """

    score: int
    band: Band
    producer: str
    signals: dict[str, Any] = field(default_factory=dict)
    degraded_events: list[DegradedEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict suitable for ``Document.metadata['confidence']``."""
        return {
            "score": self.score,
            "band": self.band,
            "producer": self.producer,
            "signals": dict(self.signals),
            "degraded_events": [event.to_dict() for event in self.degraded_events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfidenceReport":
        """Reconstruct a :class:`ConfidenceReport` from its :meth:`to_dict` form."""
        return cls(
            score=int(data.get("score", 0)),
            band=data.get("band", "low"),
            producer=str(data.get("producer", "")),
            signals=dict(data.get("signals", {}) or {}),
            degraded_events=[DegradedEvent.from_dict(event) for event in data.get("degraded_events", []) or []],
        )


def coalesce_events(events: list[DegradedEvent]) -> list[DegradedEvent]:
    """Merge events sharing ``(parser, kind, detail, severity)``, summing counts.

    Keeps first-seen order so the most significant early events lead the list.
    """
    merged: dict[tuple[str, str, str | None, str], DegradedEvent] = {}
    for event in events:
        key = (event.parser, event.kind, event.detail, event.severity)
        existing = merged.get(key)
        if existing is None:
            merged[key] = DegradedEvent(
                parser=event.parser,
                kind=event.kind,
                count=event.count,
                detail=event.detail,
                severity=event.severity,
            )
        else:
            existing.count += event.count
    return list(merged.values())


def _text_density_penalty(signals: dict[str, Any]) -> float:
    """Penalty for a document that yielded little meaningful text per page.

    Ramps linearly from ``0`` at ``TEXT_DENSITY_FLOOR_CPP`` chars/page up to
    ``TEXT_DENSITY_MAX_PENALTY`` at zero. No-ops when the producer did not report
    ``chars_per_page`` (most non-PDF formats), so those keep a clean score.
    """
    cpp = signals.get("chars_per_page")
    if cpp is None:
        return 0.0
    try:
        cpp_val = float(cpp)
    except (TypeError, ValueError):
        return 0.0
    if cpp_val >= TEXT_DENSITY_FLOOR_CPP:
        return 0.0
    shortfall = (TEXT_DENSITY_FLOOR_CPP - cpp_val) / TEXT_DENSITY_FLOOR_CPP
    return max(0.0, min(1.0, shortfall)) * TEXT_DENSITY_MAX_PENALTY


def _ocr_reliance_penalty(signals: dict[str, Any]) -> float:
    """Penalty scaled by the fraction of pages recovered via OCR."""
    fraction = signals.get("ocr_page_fraction")
    if fraction is None:
        return 0.0
    try:
        fraction_val = float(fraction)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, fraction_val)) * OCR_RELIANCE_MAX_PENALTY


def _degraded_event_penalty(events: list[DegradedEvent]) -> float:
    """Total penalty from degraded events, capped at ``DEGRADED_EVENT_PENALTY_CAP``."""
    total = 0.0
    for event in events:
        total += SEVERITY_PENALTY.get(event.severity, SEVERITY_PENALTY["warn"]) * max(0, event.count)
    return min(total, DEGRADED_EVENT_PENALTY_CAP)


def band_for_score(score: int) -> Band:
    """Bucket a ``0-100`` score into ``"high"`` / ``"medium"`` / ``"low"``.

    Never returns ``"not_assessed"``: that band depends on *what evidence exists*,
    not on the score, so it is decided in :func:`score_conversion`.
    """
    if score >= BAND_HIGH_THRESHOLD:
        return "high"
    if score >= BAND_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _has_quality_evidence(signals: dict[str, Any], events: list[DegradedEvent]) -> bool:
    """Whether a report carries any input the score can actually assess.

    True when there is at least one degraded event or one scored signal
    (:data:`SCORED_SIGNAL_KEYS`). Non-scored signals (bare counts) do not count:
    they do not move the score, so a report carrying only those is still a
    vacuous 100.
    """
    if events:
        return True
    return any(signals.get(key) is not None for key in SCORED_SIGNAL_KEYS)


def score_conversion(signals: dict[str, Any], events: list[DegradedEvent]) -> tuple[int, Band]:
    """Compute the ``(score, band)`` for a conversion from its signals and events.

    Reference-free: the score starts at ``100`` and subtracts a text-density
    penalty, an OCR-reliance penalty, and a (capped) degraded-event penalty. The
    result is clamped to ``[0, 100]``.

    A conversion that produced no scored signals and no degraded events is banded
    ``"not_assessed"`` rather than ``"high"``. Formats without quality
    instrumentation (docx, pptx, html) hit this path: their score is a vacuous
    100 that means "no detector ran", not "verified clean", and conflating the two
    would let a mangled ``.docx`` report ``100/HIGH``.

    Parameters
    ----------
    signals : dict
        Continuous per-document metrics (see :class:`ConfidenceReport`).
    events : list of DegradedEvent
        Discrete degraded-content incidents.

    Returns
    -------
    tuple of (int, str)
        The integer score and its confidence band.

    """
    penalty = _text_density_penalty(signals) + _ocr_reliance_penalty(signals) + _degraded_event_penalty(events)
    score = int(round(max(0.0, min(100.0, 100.0 - penalty))))
    if not _has_quality_evidence(signals, events):
        return score, "not_assessed"
    return score, band_for_score(score)


def build_report(producer: str, signals: dict[str, Any], events: list[DegradedEvent]) -> ConfidenceReport:
    """Assemble a scored :class:`ConfidenceReport` from raw signals and events.

    Events are coalesced (see :func:`coalesce_events`) before scoring so repeated
    incidents count once with an aggregate ``count``.
    """
    coalesced = coalesce_events(events)
    score, band = score_conversion(signals, coalesced)
    return ConfidenceReport(score=score, band=band, producer=producer, signals=dict(signals), degraded_events=coalesced)
