"""Named lint profiles — curated bundles of the built-in rules.

A *profile* is a pre-baked :class:`~all2md.linter.config.LintConfig` expressed
as a plain dict (the same shape :meth:`LintConfig.from_dict` accepts). It lets a
user opt into a coherent style policy with a single flag —
``all2md lint --profile accessibility`` — instead of hand-assembling a long
``--rule`` / ``--disable`` / ``[tool.all2md.lint]`` configuration.

Profiles ship as data only: every profile here is built exclusively from the
47 built-in rule codes, so adding one is config, not code. They mirror the
conversion-side presets in :mod:`all2md.cli.presets`.

Resolution precedence when the CLI builds a config is::

    profile  <  config file ([tool.all2md.lint])  <  explicit CLI flags

so a profile is a *base* a project file and ad-hoc flags can both refine.
:func:`merge_profile_dicts` implements the merge policy used for that layering.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List

# Canonical config keys understood by ``LintConfig.from_dict``. ``enable`` and
# ``disable`` also accept the ``enabled_rules`` / ``disabled_rules`` aliases; we
# normalise to the short forms before merging so the policy below is simple.
_SCALAR_KEYS = ("severity_threshold",)

_ALIASES = {
    "enabled_rules": "enable",
    "disabled_rules": "disable",
}


LINT_PROFILES: Dict[str, Dict[str, Any]] = {
    "accessibility": {
        "description": (
            "Accessibility-first: enforce alt text, descriptive link text, "
            "table headers, and a clean heading hierarchy. Stylistic typography "
            "is left out so the report stays focused on a11y blockers."
        ),
        "config": {
            "enable": [
                "STR001",  # document has a title / H1 landmark
                "STR003",  # heading hierarchy must not skip levels
                "STR004",  # no empty headings
                "HDG004",  # consistent heading capitalization
                "HDG005",  # heading not wrapped entirely in emphasis
                "IMG001",  # images need alt text
                "IMG005",  # alt text must be descriptive, not "image"
                "LNK001",  # links need visible text
                "LNK005",  # link text must not be "click here"
                "LNK007",  # link text must not just be the URL
                "TBL001",  # tables need a header row
            ],
            "severity": {
                "IMG001": "error",
                "LNK001": "error",
                "LNK005": "error",
                "TBL001": "error",
                "STR003": "error",
                "STR004": "error",
            },
        },
    },
    "technical-docs": {
        "description": (
            "Engineering / API documentation: enforce structure, valid links, "
            "and resolvable images, but relax prose-typography rules that fight "
            "code, identifiers, and reference-style writing."
        ),
        "config": {
            "disable": [
                "TYP003",  # straight quotes are correct in code-heavy docs
                "TYP004",  # double hyphens often appear in CLI flags (--foo)
                "TYP006",  # literal "..." is common in code and output
                "HDG006",  # reference headings legitimately read as phrases
                "STR006",  # stub/reference sections are intentionally short
                "LST001",  # single-item lists are common in step docs
                "TBL003",  # single-column tables are valid reference layouts
            ],
            "severity": {
                "STR003": "error",
                "LNK002": "error",
                "IMG002": "error",
                "LNK006": "warning",
                "TBL001": "warning",
            },
        },
    },
    "prose": {
        "description": (
            "Polished long-form prose (articles, blog posts, reports): typographic "
            "niceties, consistent heading style, and high-quality link text. Ideal "
            "for cleaning up a converted DOCX before publishing."
        ),
        "config": {
            "enable": [
                "STR001",
                "STR003",
                "HDG001",  # no trailing punctuation in headings
                "HDG003",  # no duplicate headings
                "HDG004",  # consistent heading capitalization
                "HDG006",  # headings should not read as full sentences
                "TYP001",  # no trailing whitespace
                "TYP002",  # no double spaces
                "TYP003",  # curly quotes
                "TYP004",  # em-dashes
                "TYP006",  # ellipsis character
                "TYP007",  # no space before punctuation
                "TYP008",  # no repeated punctuation
                "LNK004",  # wrap bare URLs
                "LNK005",  # quality link text
                "LNK007",  # link text is not the URL
                "IMG001",  # images need alt text
            ],
            "severity": {
                "TYP003": "warning",
                "TYP004": "warning",
                "TYP006": "warning",
                "HDG004": "warning",
            },
        },
    },
}


def available_profiles() -> List[str]:
    """Return the sorted names of every built-in lint profile."""
    return sorted(LINT_PROFILES.keys())


def profile_description(name: str) -> str:
    """Return the one-line description for ``name`` (raises ``KeyError`` if unknown)."""
    return str(LINT_PROFILES[name]["description"])


def get_profile_config(name: str) -> Dict[str, Any]:
    """Return a deep copy of the config dict for profile ``name``.

    Parameters
    ----------
    name : str
        A profile name (see :func:`available_profiles`).

    Returns
    -------
    dict
        A fresh, normalised config dict ready to feed to
        :meth:`LintConfig.from_dict` or :func:`merge_profile_dicts`. The copy is
        deep so callers can mutate it without corrupting the shared definition.

    Raises
    ------
    KeyError
        If ``name`` is not a known profile.

    """
    if name not in LINT_PROFILES:
        raise KeyError(name)
    return _normalize(LINT_PROFILES[name]["config"])


def describe_profiles() -> str:
    """Render a human-readable ``name — description`` listing for ``--list-profiles``."""
    width = max((len(n) for n in LINT_PROFILES), default=0)
    lines = [f"  {name.ljust(width)}  {profile_description(name)}" for name in available_profiles()]
    return "Available lint profiles:\n" + "\n".join(lines)


def _normalize(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of ``config`` with alias keys folded to canonical names."""
    out: Dict[str, Any] = {}
    for key, value in copy.deepcopy(config).items():
        out[_ALIASES.get(key, key)] = value
    return out


def merge_profile_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Layer ``override`` on top of ``base`` and return a new merged config dict.

    The merge policy is chosen so layering reads intuitively:

    - ``disable`` lists are **unioned** — disabling more rules is always additive.
    - ``enable`` whitelists are **replaced** when ``override`` supplies one;
      intersecting two independent whitelists almost never matches intent.
    - ``severity`` and ``rules`` tables are **shallow-merged per rule code**, with
      ``override`` winning on conflicts (``rules`` option dicts merge one level deep).
    - ``severity_threshold`` is **replaced** when present in ``override``.

    Both inputs are treated as read-only; alias keys (``enabled_rules`` /
    ``disabled_rules``) are accepted and normalised.
    """
    merged = _normalize(base)
    incoming = _normalize(override)

    # disable: union, order-stable
    if "disable" in incoming:
        union = list(merged.get("disable", []))
        seen = set(union)
        for code in incoming["disable"]:
            if code not in seen:
                union.append(code)
                seen.add(code)
        merged["disable"] = union

    # enable: replace
    if "enable" in incoming:
        merged["enable"] = list(incoming["enable"])

    # severity: per-code merge, override wins
    if "severity" in incoming:
        sev = dict(merged.get("severity", {}))
        sev.update(incoming["severity"])
        merged["severity"] = sev

    # rules: per-code merge, option dicts merged one level deep
    if "rules" in incoming:
        rules = {code: dict(opts) for code, opts in merged.get("rules", {}).items()}
        for code, opts in incoming["rules"].items():
            existing = dict(rules.get(code, {}))
            existing.update(opts)
            rules[code] = existing
        merged["rules"] = rules

    # severity_threshold: replace
    for key in _SCALAR_KEYS:
        if key in incoming:
            merged[key] = incoming[key]

    return merged
