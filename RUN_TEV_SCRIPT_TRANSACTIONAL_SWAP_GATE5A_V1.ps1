[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\mio\TEV-Script"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot ".git") -PathType Container)) {
    throw "REPOSITORY_NOT_FOUND=$RepositoryRoot"
}

Set-Location $RepositoryRoot
$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse "HEAD^{tree}").Trim()
$branchLines = @(git branch --show-current)
$branch = ($branchLines -join "").Trim()

python (Join-Path $RepositoryRoot "tools\validate_transactional_swap_gate5a.py")
if ($LASTEXITCODE -ne 0) {
    throw "GATE5A_STATIC_VALIDATION_FAILED"
}

# Existing C# semantic conformance must remain intact.
& pwsh -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $RepositoryRoot "RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1") `
    -RepositoryRoot $RepositoryRoot
if ($LASTEXITCODE -ne 0) {
    throw "GATE5A_CSHARP_REGRESSION_FAILED"
}
Write-Host "GATE5A_EXISTING_CSHARP_CONFORMANCE=PASS"

$gateSource = Join-Path $RepositoryRoot `
    "runtimes\csharp\TevScript.TransactionalSwapGate\Program.cs"
$gateSourceText = Get-Content -LiteralPath $gateSource -Raw
if (-not $gateSourceText.Contains("GATE5A_GATE_BINARY_VERSION=V4")) {
    throw "GATE5A_GATE_SOURCE_VERSION_MISMATCH"
}
$gateSourceSha = (
    Get-FileHash -LiteralPath $gateSource -Algorithm SHA256
).Hash.ToLowerInvariant()
Write-Host "GATE5A_GATE_SOURCE_VERSION=V4"
Write-Host "GATE5A_GATE_SOURCE_SHA256=$gateSourceSha"

$fixtureRoot = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_GATE5A"
New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null
$runRoot = Join-Path $fixtureRoot ([Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

try {
    $baseFixture = Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"

    $fixtureOutput = @(
        python (Join-Path $RepositoryRoot "tools\generate_transactional_swap_gate5a_fixtures.py") `
            --base $baseFixture `
            --out $runRoot 2>&1
    )
    $fixtureExit = $LASTEXITCODE
    $fixtureOutput | ForEach-Object { Write-Host $_ }
    if ($fixtureExit -ne 0) {
        throw "GATE5A_FIXTURE_GENERATION_FAILED"
    }
    $fixtureText = $fixtureOutput -join "`n"
    if (-not $fixtureText.Contains(
            "GATE5A_NEGATIVE_PROGRAM_ID_VALID_IR=GENERATED")) {
        throw "GATE5A_PROGRAM_ID_VALID_IR_FIXTURE_WITNESS_MISSING"
    }
    Write-Host "GATE5A_PROGRAM_ID_VALID_IR_FIXTURE=PASS"

    $project = Join-Path $RepositoryRoot `
        "runtimes\csharp\TevScript.TransactionalSwapGate\TevScript.TransactionalSwapGate.csproj"

    dotnet build $project --configuration Release --nologo --no-incremental
    if ($LASTEXITCODE -ne 0) {
        throw "GATE5A_DOTNET_BUILD_FAILED"
    }
    Write-Host "GATE5A_DOTNET_BUILD=PASS"

    $gateOutput = Join-Path $runRoot "gate5a-output.txt"
    $gateArgs = @(
        "run",
        "--project", $project,
        "--configuration", "Release",
        "--no-build",
        "--",
        "--base", $baseFixture,
        "--good", (Join-Path $runRoot "candidate.good.json"),
        "--removed", (Join-Path $runRoot "candidate.state_removed.json"),
        "--escalated", (Join-Path $runRoot "candidate.capability_escalated.json"),
        "--wrong-program", (Join-Path $runRoot "candidate.program_id_changed.json")
    )

    $output = @(& dotnet @gateArgs 2>&1)
    $exit = $LASTEXITCODE
    $output | Set-Content -LiteralPath $gateOutput -Encoding utf8
    $output | ForEach-Object { Write-Host $_ }
    if ($exit -ne 0) {
        throw "GATE5A_EXECUTION_FAILED exit=$exit"
    }

    $text = $output -join "`n"
    $markers = @(
        "GATE5A_GATE_BINARY_VERSION=V4",
        "GATE5A_PREPARE_NON_AUTHORITATIVE=PASS",
        "GATE5A_COMMIT_ATOMIC_REFERENCE_SWAP=PASS",
        "GATE5A_EXISTING_STATE_MIGRATION=PASS",
        "GATE5A_ADDITIVE_STATE_INITIALIZATION=PASS",
        "GATE5A_PLAN_REUSE_FAIL_CLOSED=PASS",
        "GATE5A_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS",
        "GATE5A_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS",
        "GATE5A_STATE_REMOVAL_FAIL_CLOSED=PASS",
        "GATE5A_CAPABILITY_CEILING_FAIL_CLOSED=PASS",
        "GATE5A_PROGRAM_ID_CONTINUITY_FAIL_CLOSED=PASS",
        "GATE5A_STALE_PLAN_FAIL_CLOSED=PASS",
        "GATE5A_TRANSACTION_BOUNDARY=PASS",
        "GATE5A_NO_NETWORK=PASS",
        "GATE5A_NO_SIGNATURE_AUTHORITY=PASS",
        "GATE5A_NO_DYNAMIC_CODE=PASS",
        "TEV_SCRIPT_TRANSACTIONAL_PROGRAM_SWAP_GATE_5A=PASS"
    )
    foreach ($marker in $markers) {
        if (-not $text.Contains($marker)) {
            throw "GATE5A_WITNESS_MISSING=$marker"
        }
        Write-Host "GATE5A_WITNESS_PASS=$marker"
    }

    $evidenceDir = Join-Path $RepositoryRoot "receipts\transactional-swap-gate5a"
    New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $evidence = Join-Path $evidenceDir "GATE5A_$stamp.log"
    Copy-Item -LiteralPath $gateOutput -Destination $evidence -Force
    $evidenceSha = (Get-FileHash -LiteralPath $evidence -Algorithm SHA256).Hash.ToLowerInvariant()
}
finally {
    Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "TEV_SCRIPT_TRANSACTIONAL_PROGRAM_SWAP_GATE_5A=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "GATE5A_GATE_BINARY_VERSION=V4"
Write-Host "GATE5A_GATE_SOURCE_SHA256=$gateSourceSha"
Write-Host "GATE5A_BUILD_MODE=NO_INCREMENTAL"
Write-Host "GATE5A_PROGRAM_REPLACEMENT=TRANSACTIONAL_PASS"
Write-Host "GATE5A_STATE_MIGRATION=EXACT_EXISTING_TYPES_PASS"
Write-Host "GATE5A_ADDITIVE_STATE=PASS"
Write-Host "GATE5A_CAPABILITY_CEILING=EXPLICIT_PASS"
Write-Host "GATE5A_STALE_PLAN=FAIL_CLOSED_PASS"
Write-Host "GATE5A_ROLLBACK=EXACT_PREVIOUS_RUNTIME_PASS"
Write-Host "GATE5A_DYNAMIC_CODE=ABSENT_PASS"
Write-Host "GATE5A_NETWORK=NOT_IN_SCOPE"
Write-Host "GATE5A_SIGNATURE_AUTHORITY=NOT_IN_SCOPE"
Write-Host "GATE5A_WASM=NOT_IN_SCOPE"
Write-Host "GATE5A_EVIDENCE=$evidence"
Write-Host "GATE5A_EVIDENCE_SHA256=$evidenceSha"
Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED"
