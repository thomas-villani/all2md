#!/bin/sh
# shellcheck shell=sh
# all2md one-click installer for macOS / Linux (works in bash and zsh).
#
# What it does:
#   1. Installs uv (https://docs.astral.sh/uv/) if it isn't already present.
#   2. Installs all2md as a uv-managed tool, so the `all2md` command is available
#      from any terminal without activating a virtual environment.
#
# Safe to re-run: `uv tool install --upgrade` updates an existing install in place.
#
# Usage:
#   # Run straight from GitHub (recommended for new users):
#   curl -LsSf https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.sh | sh
#
#   # Or download and run, choosing which optional formats to include:
#   sh install.sh pdf,docx,html          # only these extras
#   sh install.sh none                   # base install, no optional formats
#   ALL2MD_EXTRAS="all" sh install.sh    # same as the default
#
# The default installs the "all" extra (every optional format that ships in the
# aggregate). Pass a comma-separated extras list to slim it down.
set -eu

EXTRAS="${1:-${ALL2MD_EXTRAS:-all}}"

info() { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
err() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; }

# Build the package spec, e.g. "all2md[all]". "none"/empty => bare "all2md".
case "$EXTRAS" in
    "" | none | None | NONE) SPEC="all2md" ;;
    *) SPEC="all2md[$EXTRAS]" ;;
esac

# The standalone uv installer drops the binary in ~/.local/bin (or a couple of
# other well-known spots) and updates future shells' PATH -- but not the shell
# we're running in right now. Prepend those dirs so we can call uv immediately.
ensure_uv_on_path() {
    for d in "$HOME/.local/bin" "$HOME/.cargo/bin" "${XDG_BIN_HOME:-}"; do
        [ -n "$d" ] && [ -d "$d" ] || continue
        case ":$PATH:" in
            *":$d:"*) ;;
            *) PATH="$d:$PATH" ;;
        esac
    done
    export PATH
}

has_uv() { command -v uv >/dev/null 2>&1; }

if ! has_uv; then
    ensure_uv_on_path
fi

if ! has_uv; then
    info "Installing uv (fast Python package manager)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        err "Need either curl or wget to download uv. Install one and re-run."
        exit 1
    fi
    ensure_uv_on_path
fi

if ! has_uv; then
    err "uv was installed but isn't on PATH yet. Open a NEW terminal and re-run this script,"
    err "or add \$HOME/.local/bin to your PATH."
    exit 1
fi

info "Installing all2md ($SPEC) as a uv tool..."
uv tool install --upgrade "$SPEC"

# Make sure the uv tools bin directory is on PATH in future shells.
uv tool update-shell >/dev/null 2>&1 || true

info "Done."
if command -v all2md >/dev/null 2>&1; then
    all2md --version || true
    printf '\nTry it:  all2md --help\n'
else
    printf '\nInstalled. Open a NEW terminal, then run:  all2md --help\n'
fi
