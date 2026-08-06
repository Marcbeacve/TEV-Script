[CmdletBinding()]
param(
    [string]$Python = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
    & $Python "RUN_PORTABLE_CONFORMANCE.py"
    if ($LASTEXITCODE -ne 0) {
        throw "TEV_SCRIPT_PORTABLE_RUN_FAILED=$LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
