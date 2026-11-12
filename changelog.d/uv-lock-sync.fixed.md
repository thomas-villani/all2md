- `uv.lock` stays in step with `pyproject.toml`. Dependabot now watches the `uv`
  ecosystem, which updates both files in one PR, where the `pip` ecosystem changed only
  `pyproject.toml` and left the lock behind (ruff 0.17.3 in the lock, 0.17.4 pinned).
  CI runs `uv lock --check`, so a pin changed without re-locking fails on its own PR.
