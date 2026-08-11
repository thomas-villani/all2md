#  Copyright (c) 2025 Tom Villani, Ph.D.
"""We import PyMuPDF under its canonical name, and say so when it is too old.

`fitz` is PyMuPDF's legacy top-level alias. Some releases emit a DeprecationWarning
on `import fitz`, which surfaces to anyone running the CLI as noise they cannot act
on - all2md's dependency, not theirs. `pymupdf` has been the real module name since
1.24.3 and we require 1.27.2, so there is nothing to weigh up; these tests keep the
old name from creeping back.

The version guard is here too because it was unreachable in practice: it built its
own error message by joining a tuple of ints, so the one code path that exists to
tell a user "upgrade PyMuPDF" raised TypeError instead.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from all2md.constants import DEPS_PDF, PDF_MIN_PYMUPDF_VERSION
from all2md.exceptions import DependencyError

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

_FITZ = re.compile(r"\bfitz\b")

# `_pdf_layout.py` neutralizes the layout hook on both module objects on purpose,
# because the alias can be a distinct module object in some installs. Those are
# the only mentions that are *about* the alias rather than uses of it.
_ALIAS_IS_THE_POINT = {"src/all2md/parsers/_pdf_layout.py": 2}


def _tracked_python_sources() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "src/*.py"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[4],
    )
    root = Path(__file__).resolve().parents[4]
    return [root / line for line in listing.stdout.split()]


def test_the_scan_actually_reads_files() -> None:
    """Guard the guard: an empty file list would make the check below vacuous."""
    sources = _tracked_python_sources()
    assert len(sources) > 100, f"only found {len(sources)} source files"
    assert any("parsers/pdf.py" in source.as_posix() for source in sources)


def test_no_source_module_uses_the_legacy_fitz_alias() -> None:
    offenders: dict[str, int] = {}
    root = Path(__file__).resolve().parents[4]
    for source in _tracked_python_sources():
        hits = len(_FITZ.findall(source.read_bytes().decode("utf-8", "replace")))
        if hits:
            offenders[source.relative_to(root).as_posix()] = hits

    assert (
        offenders == _ALIAS_IS_THE_POINT
    ), "import PyMuPDF as `pymupdf`, not `fitz`: the alias is deprecated and some releases warn on import"


def test_the_declared_dependency_matches_the_runtime_guard() -> None:
    """Three different minimums used to be declared across the codebase."""
    (_install_name, import_name, spec), *rest = DEPS_PDF
    assert rest == []
    assert import_name == "pymupdf"
    assert spec == f">={PDF_MIN_PYMUPDF_VERSION}"


def test_an_old_pymupdf_is_reported_rather_than_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The version guard must name the installed version, not raise from inside itself."""
    import pymupdf

    from all2md.parsers.pdf import _check_pymupdf_version

    monkeypatch.setattr(pymupdf, "pymupdf_version_tuple", (1, 24, 3), raising=False)

    with pytest.raises(DependencyError) as excinfo:
        _check_pymupdf_version()

    message = str(excinfo.value)
    assert "1.24.3" in message, message
    assert PDF_MIN_PYMUPDF_VERSION in message, message


def test_a_current_pymupdf_passes_the_guard() -> None:
    """Control: the guard is not raising for everyone."""
    from all2md.parsers.pdf import _check_pymupdf_version

    _check_pymupdf_version()
