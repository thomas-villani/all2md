- **Python 3.10 is no longer supported; all2md needs Python 3.11 or later.** Python 3.10
  reached end of life on 2026-10-01, and PyMuPDF 2.0 already requires 3.11. The
  `tomli` and `typing_extensions` backports are gone from the core dependencies, so a
  bare install is four packages: `tomli-w`, `pyyaml`, `platformdirs` and `mistune`. The
  `tui` extra (`all2md read`) no longer needs a Python marker, and `check-deps read` no
  longer reports a minimum Python for it. CI tests 3.11 to 3.15.
