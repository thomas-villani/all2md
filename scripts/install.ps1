<#
.SYNOPSIS
    One-click installer for all2md on Windows.

.DESCRIPTION
    Installs uv (https://docs.astral.sh/uv/) if it isn't already present, then
    installs all2md as a uv-managed tool so the `all2md` command is available
    from any terminal without activating a virtual environment.

    Safe to re-run: `uv tool install --upgrade` updates an existing install in place.

.PARAMETER Extras
    Comma-separated optional format extras to include (default: "all").
    Use "none" for a minimal base install with no optional formats.

.EXAMPLE
    # Run straight from GitHub (recommended for new users):
    powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/thomas-villani/all2md/main/scripts/install.ps1 | iex"

.EXAMPLE
    # Download and run with a slimmer extras set:
    .\install.ps1 -Extras "pdf,docx,html"

.EXAMPLE
    .\install.ps1 -Extras none
#>
param(
    [string]$Extras = "all"
)

$ErrorActionPreference = "Stop"

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }

# Build the package spec, e.g. "all2md[all]". "none"/blank => bare "all2md".
$spec = if ([string]::IsNullOrWhiteSpace($Extras) -or $Extras -ieq "none") {
    "all2md"
} else {
    "all2md[$Extras]"
}

function Test-Uv { [bool](Get-Command uv -ErrorAction SilentlyContinue) }

# The standalone uv installer drops the binary in %USERPROFILE%\.local\bin and
# updates the *persisted* user PATH, but not the current session. Add the
# well-known locations so we (and `uv tool`'s shims) are reachable right away.
function Add-LocalBinToPath {
    $dirs = @(
        (Join-Path $env:USERPROFILE ".local\bin"),
        (Join-Path $env:USERPROFILE ".cargo\bin")
    )
    foreach ($d in $dirs) {
        if ((Test-Path $d) -and ($env:PATH -notlike "*$d*")) {
            $env:PATH = "$d;$env:PATH"
        }
    }
}

if (-not (Test-Uv)) { Add-LocalBinToPath }

if (-not (Test-Uv)) {
    Write-Step "Installing uv (fast Python package manager)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Add-LocalBinToPath
}

if (-not (Test-Uv)) {
    throw "uv was installed but isn't on PATH yet. Open a NEW terminal and re-run this script."
}

Write-Step "Installing all2md ($spec) as a uv tool..."
uv tool install --upgrade $spec

# Ensure the uv tools bin directory is on PATH for future shells.
try { uv tool update-shell | Out-Null } catch { }

Write-Step "Done."
if (Get-Command all2md -ErrorAction SilentlyContinue) {
    try { all2md --version } catch { }
    Write-Host "`nTry it:  all2md --help"
} else {
    Write-Host "`nInstalled. Open a NEW terminal, then run:  all2md --help"
}
