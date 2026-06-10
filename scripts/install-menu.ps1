<#
.SYNOPSIS
    Install or remove the Windows "View with all2md" right-click context-menu entry.

.DESCRIPTION
    Thin convenience wrapper around the built-in CLI command:

        all2md context-menu install
        all2md context-menu uninstall

    The CLI command is the source of truth — it registers the per-user entry
    (HKCU, no admin needed), points it at the console-less `all2mdw` launcher,
    and copies the bundled icon to %LOCALAPPDATA%. This script just locates the
    all2md executable and forwards to it, which is handy when all2md isn't on
    PATH (e.g. running straight from a cloned repo's virtual environment).

.PARAMETER Uninstall
    Remove the entry instead of installing it.

.PARAMETER Extensions
    Comma/space separated list of file extensions the entry shows on
    (overrides the built-in default set). Ignored when -Uninstall is set.

.EXAMPLE
    .\scripts\install-menu.ps1
    .\scripts\install-menu.ps1 -Extensions "md,pdf,docx"
    .\scripts\install-menu.ps1 -Uninstall
#>
param(
    [switch]$Uninstall,
    [string]$Extensions
)

$ErrorActionPreference = "Stop"

function Get-All2MdExe {
    # 1) On PATH (preferred for an installed tool).
    $cmd = Get-Command "all2md" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandType -eq 'Application' } |
        Select-Object -First 1
    if ($cmd -and $cmd.Path) { return $cmd.Path }

    # 2) Common local / repo locations.
    $candidates = @(
        (Join-Path $PSScriptRoot "..\.venv\Scripts\all2md.exe"),
        (Join-Path $env:USERPROFILE ".local\bin\all2md.exe")
    )
    if ($env:UV_TOOL_BIN_DIR) {
        $candidates += (Join-Path $env:UV_TOOL_BIN_DIR "all2md.exe")
    }
    foreach ($path in $candidates) {
        if ($path -and (Test-Path $path)) { return (Resolve-Path $path).Path }
    }
    return $null
}

$exe = Get-All2MdExe
if (-not $exe) {
    throw "Could not find all2md.exe. Install all2md (e.g. 'uv tool install all2md') or run from the repo's .venv."
}

if ($Uninstall) {
    & $exe context-menu uninstall
}
else {
    $cliArgs = @("context-menu", "install")
    if ($Extensions) { $cliArgs += @("--extensions", $Extensions) }
    & $exe @cliArgs
}

exit $LASTEXITCODE
