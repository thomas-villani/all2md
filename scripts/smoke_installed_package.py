#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Smoke-test an installed all2md, as a user gets it from PyPI.

CI tests an editable install with every extra. Nothing used to install the wheel
that ships, so a data file missing from the package, a broken entry point, or a
core import of an optional dependency would have reached PyPI. This script is run
by the interpreter of a clean virtual environment holding only the built wheel
(and, in a second pass, a few extras); it must not import anything from the
repository.

Usage::

    python scripts/smoke_installed_package.py --source src/all2md --version 1.17.0
    python scripts/smoke_installed_package.py --source src/all2md --extras

``--extras`` adds the checks that need ``all2md[markdown,docx]``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

#: Files under the package that are never shipped.
_SKIPPED_SUFFIXES = {".py", ".pyc", ".pyo"}


def _run(*args: str, stdin: str | None = None) -> str:
    """Run the installed ``all2md`` command, failing loudly on a non-zero exit."""
    executable = shutil.which("all2md", path=str(Path(sys.executable).parent))
    if executable is None:
        raise SystemExit("FAIL: the all2md console script is not installed next to this interpreter")
    result = subprocess.run(
        [executable, *args], input=stdin, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        raise SystemExit(f"FAIL: all2md {' '.join(args)} exited {result.returncode}\n{result.stdout}{result.stderr}")
    return result.stdout


def check_import_is_not_the_checkout(version: str | None) -> Path:
    """Import the installed package and return its directory."""
    import all2md

    package_dir = Path(all2md.__file__).resolve().parent
    if "site-packages" not in package_dir.parts:
        raise SystemExit(f"FAIL: imported all2md from {package_dir}, not from an installed wheel")
    if version is not None and all2md.__version__ != version:
        raise SystemExit(f"FAIL: installed version {all2md.__version__} != expected {version}")
    print(f"ok  import all2md {all2md.__version__} from {package_dir}")
    return package_dir


def check_package_data(source: Path, package_dir: Path) -> None:
    """Check that every non-Python file in the source package is installed."""
    missing = [
        path.relative_to(source).as_posix()
        for path in sorted(source.rglob("*"))
        if path.is_file()
        and path.suffix not in _SKIPPED_SUFFIXES
        and "__pycache__" not in path.parts
        and not (package_dir / path.relative_to(source)).is_file()
    ]
    if missing:
        raise SystemExit("FAIL: package data missing from the wheel:\n  " + "\n  ".join(missing))
    print("ok  package data complete")


def check_core(workdir: Path) -> None:
    """Check what a bare ``pip install all2md`` promises: the CLI, text and Markdown input, grep, check-deps."""
    print("ok  " + _run("--version").strip())
    sample = workdir / "notes.txt"
    sample.write_text("Quarterly report\n\nRevenue grew in every region.\n", encoding="utf-8")
    if "Revenue grew" not in _run(str(sample)):
        raise SystemExit("FAIL: converting a .txt file lost its text")
    print("ok  .txt -> markdown")
    if "Revenue" not in _run("grep", "Revenue", str(sample)):
        raise SystemExit("FAIL: grep did not find a word in a .txt file")
    print("ok  grep")
    # mistune is a core dependency, so a bare install parses Markdown; --outline only
    # works from the parsed document, so it proves the parser ran.
    markdown = workdir / "notes.md"
    markdown.write_text("# Quarterly report\n\n## Revenue\n\nGrew in every region.\n", encoding="utf-8")
    outline = _run(str(markdown), "--outline")
    if "Quarterly report" not in outline or "Revenue" not in outline:
        raise SystemExit(f"FAIL: the outline of a .md file lost its headings:\n{outline}")
    print("ok  .md -> outline")
    # check-deps exits non-zero when extras are missing, which is the expected state of
    # a bare install; it must still run and report.
    executable = shutil.which("all2md", path=str(Path(sys.executable).parent))
    report = subprocess.run(
        [str(executable), "check-deps"], capture_output=True, text=True, encoding="utf-8", check=False
    )
    if "Traceback" in report.stderr or not report.stdout.strip():
        raise SystemExit(f"FAIL: check-deps crashed\n{report.stdout}{report.stderr}")
    print("ok  check-deps")


def check_extras(workdir: Path) -> None:
    """Check Markdown to Word and back, which needs ``[markdown,docx]``."""
    source = workdir / "brief.md"
    source.write_text("# Project brief\n\nShip the **wheel** we tested.\n\n- one\n- two\n", encoding="utf-8")
    target = workdir / "brief.docx"
    _run(str(source), "--out", str(target))
    if not target.is_file() or target.stat().st_size == 0:
        raise SystemExit("FAIL: md -> docx wrote no file")
    back = _run(str(target))
    for expected in ("Project brief", "wheel", "two"):
        if expected not in back:
            raise SystemExit(f"FAIL: md -> docx -> md lost {expected!r}:\n{back}")
    print("ok  md -> docx -> md")


def main() -> int:
    """Run the smoke checks."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="the repository's src/all2md, for package data")
    parser.add_argument("--version", help="the version the installed package must report")
    parser.add_argument("--extras", action="store_true", help="also run the [markdown,docx] checks")
    args = parser.parse_args()

    package_dir = check_import_is_not_the_checkout(args.version)
    check_package_data(args.source.resolve(), package_dir)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        check_core(workdir)
        if args.extras:
            check_extras(workdir)
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
