- **The `archive` and `all` extras now require brotli 1.2.1, and the `mcp` and `all`
  extras require fastmcp 3.4.10.** brotli 1.2.0 and older can write out of bounds while
  decoding (CVE-2026-111497, GHSA-9v8h-qqgm-4m35), and a 7z archive compressed with
  Brotli reaches that decoder through py7zr, which itself only requires brotli 1.2.0.
  brotli is now a direct requirement of the `archive` extra, or brotlicffi 1.2.1.0 on PyPy,
  so an upgrade pulls it forward. fastmcp 3.0 to 3.4.9 skip component authorization after
  transforms (GHSA-7xgj-8392-5q4r). The fastmcp floor rises from 2.11.3, so fastmcp 2.x
  is no longer supported. The other alerts fixed in the lock this release (filelock,
  virtualenv, setuptools) affect only development tooling and do not reach an install
  from PyPI.
