# Scripts

This directory contains utility scripts for maintaining the all2md codebase.

## install.sh / install.ps1

One-click end-user installers. Each script installs [uv](https://docs.astral.sh/uv/)
if it isn't already present, then installs the `all2md` CLI as a uv-managed tool so
the `all2md` command is available from any terminal. Safe to re-run (upgrades in place).

These are meant to be run by end users, either straight from GitHub or from the copies
attached to each release:

```bash
# macOS / Linux (bash or zsh)
curl -LsSf https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.sh | sh

# Slim it down (default installs the "all" extra); "none" for base-only:
sh install.sh pdf,docx,html
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.ps1 | iex"
.\install.ps1 -Extras "pdf,docx,html"
```

`install.sh` is POSIX `sh` and covers both bash and zsh (no separate zsh script is
needed). Both are documented for users in `docs/source/installation.rst` and the
project README.

## update_document_formats.py

Manages the synchronization between the `DocumentFormat` Literal type hint in `constants.py` and the dynamically discovered formats in the converter registry.

### Usage

**Validate synchronization** (used by pre-commit hook):
```bash
python scripts/update_document_formats.py --validate
```

**Update constants.py** with current registry formats:
```bash
python scripts/update_document_formats.py --update
```

**Preview changes** without modifying files:
```bash
python scripts/update_document_formats.py --dry-run
```

### When to run

This script should be run whenever:
- A new parser or renderer is added to the project
- A format name is changed
- The `DocumentFormat` Literal appears out of sync with the registry

The pre-commit hook will automatically validate and update the Literal if needed.

## pre-commit-format-sync.sh

Pre-commit hook that validates `DocumentFormat` synchronization.

### Installation (manual)

```bash
ln -s ../../scripts/pre-commit-format-sync.sh .git/hooks/pre-commit
chmod +x scripts/pre-commit-format-sync.sh
```

Or use the `.pre-commit-config.yaml` configuration:

```bash
pip install pre-commit
pre-commit install
```

### What it does

1. Validates that `DocumentFormat` Literal matches the registry
2. If validation fails, automatically runs `update_document_formats.py --update`
3. Stages the updated `constants.py` file
4. Allows the commit to proceed

This ensures the format list never drifts out of sync.
