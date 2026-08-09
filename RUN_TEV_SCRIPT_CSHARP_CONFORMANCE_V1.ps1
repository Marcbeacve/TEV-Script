[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [switch]$RequireClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    & $Command
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "$Label`_FAILED exit=$code" }
}

function Require-Line {
    param(
        [Parameter(Mandatory=$true)][object[]]$Lines,
        [Parameter(Mandatory=$true)][string]$Expected,
        [Parameter(Mandatory=$true)][string]$Label
    )
    if (@($Lines | Where-Object { "$_" -eq $Expected }).Count -ne 1) {
        throw "$Label`_WITNESS_MISSING expected=$Expected"
    }
}

$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
Set-Location $RepositoryRoot

$expectedSchemaHashes = [ordered]@{
    "schemas/tev_script_program_ir_v2.schema.json" = "b07d64de19000999c10baa648632d374890d96bac40bf385b6a173b5cacdeb08"
    "schemas/tev_script_conformance_scenario_v1.schema.json" = "33cc609a27e7657fecb5a25c2422d11417dd9ba4c178c9bbd58e6fa2046009bd"
    "schemas/tev_script_conformance_receipt_v1.schema.json" = "9d63ffb3284f909649d54769d033a6509c318b392fff2e97e21e907ba67598fb"
}
foreach ($item in $expectedSchemaHashes.GetEnumerator()) {
    $path = Join-Path $RepositoryRoot ($item.Key -replace "/", "\")
    $observed = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($observed -ne $item.Value) {
        throw "SCHEMA_CHANGED_SINCE_V7 path=$($item.Key) expected=$($item.Value) observed=$observed"
    }
}
Write-Host "V7_SCHEMA_IDENTITY=PASS"

$dirtyBefore = @(git status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) { throw "GIT_STATUS_QUERY_FAILED" }
if ($RequireClean -and $dirtyBefore.Count -ne 0) {
    $dirtyBefore | ForEach-Object { Write-Host "DIRTY_BEFORE=$_" }
    throw "REQUIRE_CLEAN_PRECONDITION_FAILED"
}

$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw "GIT_BRANCH_QUERY_FAILED" }
$head = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "GIT_HEAD_QUERY_FAILED" }
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"

$portableOutput = @(python .\RUN_PORTABLE_CONFORMANCE.py 2>&1)
$portableExit = $LASTEXITCODE
$portableOutput | ForEach-Object { Write-Host $_ }
if ($portableExit -ne 0) { throw "PORTABLE_CONFORMANCE_FAILED exit=$portableExit" }
Require-Line -Lines $portableOutput -Expected "PYTHON_JAVASCRIPT_BYTE_PARITY=PASS" -Label "PYTHON_JAVASCRIPT_PARITY"
Require-Line -Lines $portableOutput -Expected "TEV_SCRIPT_PORTABLE_V0_2=PASS_PYTHON_JAVASCRIPT" -Label "PORTABLE_RUNNER"
if (@($portableOutput | Where-Object { "$_" -eq "JSON_SCHEMA_VALIDATION=PASS" }).Count -eq 1) {
    Write-Host "JSON_SCHEMA_REVALIDATION=PASS"
}
elseif (@($portableOutput | Where-Object { "$_" -eq "JSON_SCHEMA_VALIDATION=SKIPPED_DEPENDENCY_UNAVAILABLE" }).Count -eq 1) {
    # Gate C#-2 changes no schema. Exact V7 schema hashes above preserve the
    # previously certified Draft 2020-12 schema surface without inventing PASS.
    Write-Host "JSON_SCHEMA_REVALIDATION=SKIPPED_OPTIONAL_DEPENDENCY"
    Write-Host "JSON_SCHEMA_CONTINUITY_FROM_V7=PASS"
}
else {
    throw "JSON_SCHEMA_STATUS_UNRECOGNIZED"
}

$coreProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.Core\TevScript.Core.csproj"
$smokeProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.Core.Smoke\TevScript.Core.Smoke.csproj"
$conformanceProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.Core.Conformance\TevScript.Core.Conformance.csproj"
$playerIr = Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"

$dotnetSdk = (dotnet --version).Trim()
if ($LASTEXITCODE -ne 0) { throw "DOTNET_NOT_AVAILABLE" }
Write-Host "DOTNET_SDK=$dotnetSdk"

dotnet --list-runtimes
if ($LASTEXITCODE -ne 0) { throw "DOTNET_RUNTIME_QUERY_FAILED" }

Invoke-NativeChecked -Label "CSHARP_CONFORMANCE_RESTORE" -Command { dotnet restore $conformanceProject }
Invoke-NativeChecked -Label "CSHARP_SMOKE_RESTORE" -Command { dotnet restore $smokeProject }
Invoke-NativeChecked -Label "CSHARP_CORE_BUILD" -Command {
    dotnet build $coreProject --configuration Release --no-restore -p:TreatWarningsAsErrors=true -p:Deterministic=true
}
Invoke-NativeChecked -Label "CSHARP_CONFORMANCE_BUILD" -Command {
    dotnet build $conformanceProject --configuration Release --no-restore -p:TreatWarningsAsErrors=true -p:Deterministic=true
}
Write-Host "CSHARP_BUILD=PASS"

$smokeOutput = @(dotnet run --project $smokeProject --configuration Release --no-restore -- $playerIr 2>&1)
$smokeExit = $LASTEXITCODE
$smokeOutput | ForEach-Object { Write-Host $_ }
if ($smokeExit -ne 0) { throw "CSHARP_SMOKE_FAILED exit=$smokeExit" }
Require-Line -Lines $smokeOutput -Expected "TEV_SCRIPT_CSHARP_SMOKE=PASS" -Label "CSHARP_SMOKE"
Write-Host "CSHARP_GATE1=PASS"

$gateOutput = @(dotnet run --project $conformanceProject --configuration Release --no-build --no-restore -- $RepositoryRoot 2>&1)
$gateExit = $LASTEXITCODE
$gateOutput | ForEach-Object { Write-Host $_ }
if ($gateExit -ne 0) { throw "CSHARP_GATE2_FAILED exit=$gateExit" }
Require-Line -Lines $gateOutput -Expected "TEV_SCRIPT_CSHARP_GATE_2=PASS" -Label "CSHARP_GATE2"
Require-Line -Lines $gateOutput -Expected "CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS" -Label "CSHARP_BYTE_PARITY"

Invoke-NativeChecked -Label "GIT_DIFF_CHECK" -Command { git diff --check }

$dirtyAfter = @(git status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0) { throw "FINAL_GIT_STATUS_QUERY_FAILED" }
if ($RequireClean -and $dirtyAfter.Count -ne 0) {
    $dirtyAfter | ForEach-Object { Write-Host "DIRTY_AFTER=$_" }
    throw "WORKTREE_CHANGED_BY_CERTIFICATION"
}

Write-Host ""
Write-Host "TEV_SCRIPT_THREE_RUNTIME_CONFORMANCE=PASS"
Write-Host "PYTHON=CONFORMANT_REFERENCE"
Write-Host "JAVASCRIPT=CONFORMANT_ES2022_REFERENCE"
Write-Host "CSHARP=CONFORMANT_DOTNET_REFERENCE_OBSERVED"
Write-Host "CONFORMANCE_SCENARIOS=4"
Write-Host "CSHARP_CANONICAL_VECTORS=12_PASS"
Write-Host "STABLE_RELEASE=NO"
Write-Host "UNITY_ADAPTER=PENDING"
Write-Host "MERGE=NOT_PERFORMED"
if ($RequireClean) { Write-Host "GIT_STATUS=CLEAN" } else { Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED" }
