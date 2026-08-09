[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\mio\TEV-Script",
    [string]$UnityExe = "",
    [switch]$RequireClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Require-CleanGit {
    param([string]$Root)
    $dirty = @(git -C $Root status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw "GIT_STATUS_QUERY_FAILED" }
    if ($dirty.Count -ne 0) {
        $dirty | ForEach-Object { Write-Host "DIRTY=$_" }
        throw "WORKTREE_NOT_CLEAN"
    }
}

function Resolve-UnityExe {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw "UNITY_EXE_NOT_FOUND=$Requested"
        }
        return (Resolve-Path -LiteralPath $Requested).Path
    }

    $preferred =
        "C:\Program Files\Unity\Hub\Editor\6000.3.10f1\Editor\Unity.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }

    $hubRoot = "C:\Program Files\Unity\Hub\Editor"
    if (-not (Test-Path -LiteralPath $hubRoot -PathType Container)) {
        throw "UNITY_HUB_EDITOR_ROOT_NOT_FOUND"
    }

    $candidates = @(
        Get-ChildItem -LiteralPath $hubRoot -Directory |
        Where-Object { $_.Name -like "6000.3*" } |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "Editor\Unity.exe" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )
    if ($candidates.Count -lt 1) {
        throw "UNITY_6000_3_NOT_FOUND"
    }
    return $candidates[0]
}

function Require-Markers {
    param(
        [string]$Text,
        [string[]]$Markers,
        [string]$Code
    )
    foreach ($marker in $Markers) {
        if (-not $Text.Contains($marker)) {
            throw "$Code=$marker"
        }
        Write-Host "HOT_UPDATE_WITNESS_PASS=$marker"
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot ".git") -PathType Container)) {
    throw "REPOSITORY_NOT_FOUND=$RepositoryRoot"
}

Set-Location $RepositoryRoot
if ($RequireClean) {
    Require-CleanGit -Root $RepositoryRoot
}

$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse "HEAD^{tree}").Trim()
$branch = (git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "CURRENT_BRANCH_EMPTY"
}

python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PACKAGE.py")
if ($LASTEXITCODE -ne 0) {
    throw "HOT_UPDATE_UNITY_PACKAGE_STATIC_FAILED"
}
python (Join-Path $RepositoryRoot "tools\validate_hot_update_batch_5c_5e.py")
if ($LASTEXITCODE -ne 0) {
    throw "HOT_UPDATE_BATCH_STATIC_FAILED"
}

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorVersion = Split-Path -Leaf (
    Split-Path -Parent (
        Split-Path -Parent $resolvedUnity
    )
)
if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_BATCH_BOUNDARY=$editorVersion"
}
Write-Host "UNITY_EXE=$resolvedUnity"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

# Current portable C# regression with the new additive update Core surface.
& pwsh -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $RepositoryRoot "RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1") `
    -RepositoryRoot $RepositoryRoot
if ($LASTEXITCODE -ne 0) {
    throw "HOT_UPDATE_CURRENT_CSHARP_REGRESSION_FAILED"
}
Write-Host "HOT_UPDATE_CURRENT_CSHARP_REGRESSION=PASS"

# ------------------------------------------------------------
# Certified Gate-5B regression in isolated named-branch clone.
# ------------------------------------------------------------
$gate5bCertified = "8a560f349a8ca7ad7f893e16648c140d771020cb"
$regressionParent = Join-Path $env:LOCALAPPDATA `
    "TEV_SCRIPT_HOT_UPDATE_GATE5B_REGRESSION"
New-Item -ItemType Directory -Path $regressionParent -Force | Out-Null
$regressionClone = Join-Path $regressionParent `
    ([Guid]::NewGuid().ToString("N"))

try {
    git clone --quiet --no-hardlinks --no-checkout `
        $RepositoryRoot $regressionClone
    if ($LASTEXITCODE -ne 0) {
        throw "HOT_UPDATE_GATE5B_CLONE_FAILED"
    }

    $ephemeral =
        "hot-update-gate5b-" + [Guid]::NewGuid().ToString("N")
    git -C $regressionClone switch --quiet -c `
        $ephemeral $gate5bCertified
    if ($LASTEXITCODE -ne 0) {
        throw "HOT_UPDATE_GATE5B_CHECKOUT_FAILED"
    }

    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $regressionClone `
            "RUN_TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE5B_V1.ps1") `
        -RepositoryRoot $regressionClone `
        -UnityExe $resolvedUnity `
        -RequireClean

    if ($LASTEXITCODE -ne 0) {
        throw "HOT_UPDATE_GATE5B_REGRESSION_FAILED"
    }
}
finally {
    if (Test-Path -LiteralPath $regressionClone) {
        Remove-Item -LiteralPath $regressionClone `
            -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "HOT_UPDATE_GATE5B_REGRESSION=PASS"
Write-Host "HOT_UPDATE_GATE5B_REGRESSION_HEAD=$gate5bCertified"

# ------------------------------------------------------------
# Fixture generation and Gate 5C/5D .NET campaign.
# ------------------------------------------------------------
$batchRoot = Join-Path $env:LOCALAPPDATA `
    "TEV_SCRIPT_HOT_UPDATE_BATCH_5C_5E"
New-Item -ItemType Directory -Path $batchRoot -Force | Out-Null
$runRoot = Join-Path $batchRoot ([Guid]::NewGuid().ToString("N"))
$fixtures = Join-Path $runRoot "fixtures"
$dotnetStore = Join-Path $runRoot "dotnet-installed-update.json"
New-Item -ItemType Directory -Path $fixtures -Force | Out-Null

$fixtureProject = Join-Path $RepositoryRoot `
    "runtimes\csharp\TevScript.HotUpdateFixtureTool\TevScript.HotUpdateFixtureTool.csproj"

dotnet build $fixtureProject `
    --configuration Release `
    --nologo `
    --no-incremental
if ($LASTEXITCODE -ne 0) {
    throw "HOT_UPDATE_FIXTURE_TOOL_BUILD_FAILED"
}
Write-Host "HOT_UPDATE_FIXTURE_TOOL_BUILD=PASS"

$fixtureOutput = @(
    dotnet run `
        --project $fixtureProject `
        --configuration Release `
        --no-build `
        -- `
        --base (Join-Path $RepositoryRoot "examples\Player.tevs.ir.json") `
        --out $fixtures 2>&1
)
$fixtureExit = $LASTEXITCODE
$fixtureOutput | ForEach-Object { Write-Host $_ }
if ($fixtureExit -ne 0) {
    throw "HOT_UPDATE_FIXTURE_GENERATION_FAILED run_root=$runRoot"
}

$fixtureText = $fixtureOutput -join "`n"
Require-Markers `
    -Text $fixtureText `
    -Code "HOT_UPDATE_FIXTURE_WITNESS_MISSING" `
    -Markers @(
        "GATE5C_FIXTURE_ES256_P256_SHA256=PASS"
        "GATE5C_SIGNATURE_FORMAT=IEEE_P1363_FIXED_64"
        "GATE5C_TEST_PRIVATE_KEY_SCOPE=FIXTURE_TOOL_ONLY"
        "GATE5D_MONOTONIC_FIXTURE_SET=PASS"
        "GATE5E_REMOTE_FIXTURE_SET=PASS"
    )

$gateProject = Join-Path $RepositoryRoot `
    "runtimes\csharp\TevScript.HotUpdateBatchGate\TevScript.HotUpdateBatchGate.csproj"

dotnet build $gateProject `
    --configuration Release `
    --nologo `
    --no-incremental
if ($LASTEXITCODE -ne 0) {
    throw "HOT_UPDATE_GATE5C_5D_BUILD_FAILED"
}
Write-Host "HOT_UPDATE_GATE5C_5D_BUILD=PASS"

$gateOutput = @(
    dotnet run `
        --project $gateProject `
        --configuration Release `
        --no-build `
        -- `
        --base (Join-Path $fixtures "base.json") `
        --fixtures $fixtures `
        --store $dotnetStore 2>&1
)
$gateExit = $LASTEXITCODE
$gateOutput | ForEach-Object { Write-Host $_ }
if ($gateExit -ne 0) {
    throw "HOT_UPDATE_GATE5C_5D_FAILED run_root=$runRoot"
}

$gateText = $gateOutput -join "`n"
Require-Markers `
    -Text $gateText `
    -Code "HOT_UPDATE_GATE5C_5D_WITNESS_MISSING" `
    -Markers @(
        "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_GATE_5C=PASS"
        "GATE5C_TAMPER_FAIL_CLOSED=PASS"
        "GATE5C_WRONG_KEY_FAIL_CLOSED=PASS"
        "GATE5C_ALGORITHM_DOWNGRADE_FAIL_CLOSED=PASS"
        "GATE5C_TEST_PRIVATE_KEY_RUNTIME=ABSENT_PASS"
        "TEV_SCRIPT_ANTI_REPLAY_GATE_5D=PASS_WITH_DURABLE_STATE_BOUNDARY"
        "GATE5D_DURABLE_RESTART_RESTORE=PASS"
        "GATE5D_REPLAY_AFTER_RESTORE_FAIL_CLOSED=PASS"
        "GATE5D_EPOCH_ROLLBACK_FAIL_CLOSED=PASS"
        "GATE5D_STALE_UPDATE_PLAN_FAIL_CLOSED=PASS"
        "GATE5D_RUNTIME_AND_DURABLE_COMMIT_COUPLING=PASS"
        "GATE5D_HOSTILE_STORE_ROLLBACK=NOT_IN_SCOPE"
        "TEV_SCRIPT_HOT_UPDATE_BATCH_GATE_5C_5D=PASS"
    )

# ------------------------------------------------------------
# Gate 5E: loopback HTTP bytes -> IL2CPP Player -> verified update.
# ------------------------------------------------------------
$projectRoot = Join-Path $runRoot "unity"
$buildRoot = Join-Path $projectRoot "Build"
$playerExe = Join-Path $buildRoot "TEVScriptRemoteUpdateGate.exe"
$buildLog = Join-Path $projectRoot "unity-gate5e-build.log"
$firstLog = Join-Path $projectRoot "unity-gate5e-first.log"
$restoreLog = Join-Path $projectRoot "unity-gate5e-restore.log"
$remoteStore = Join-Path $runRoot "unity-installed-update.json"

New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Assets\Gate5E\Runtime"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Assets\Gate5E\Editor"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Assets\Resources"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Packages"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "ProjectSettings"
) -Force | Out-Null
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

$stagedPackageRoot = Join-Path $projectRoot `
    "LocalPackages\com.marcbeacve.tev-script"
New-Item -ItemType Directory -Path (
    Split-Path -Parent $stagedPackageRoot
) -Force | Out-Null
Copy-Item -LiteralPath (
    Join-Path $RepositoryRoot "unity\Package"
) -Destination $stagedPackageRoot -Recurse -Force

$gate5eRoot = Join-Path $RepositoryRoot `
    "unity\PlayerGates\RemoteUpdate"

Copy-Item -LiteralPath (
    Join-Path $gate5eRoot `
        "Runtime\Marcbeacve.TevScript.Gate5E.RemoteUpdate.asmdef"
) -Destination (
    Join-Path $projectRoot `
        "Assets\Gate5E\Runtime\Marcbeacve.TevScript.Gate5E.RemoteUpdate.asmdef"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate5eRoot `
        "Runtime\TevScriptRemoteUpdateGate.cs"
) -Destination (
    Join-Path $projectRoot `
        "Assets\Gate5E\Runtime\TevScriptRemoteUpdateGate.cs"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate5eRoot `
        "Editor\Marcbeacve.TevScript.Gate5E.RemoteUpdate.Editor.asmdef"
) -Destination (
    Join-Path $projectRoot `
        "Assets\Gate5E\Editor\Marcbeacve.TevScript.Gate5E.RemoteUpdate.Editor.asmdef"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate5eRoot `
        "Editor\TevScriptRemoteUpdateBuildGate.cs"
) -Destination (
    Join-Path $projectRoot `
        "Assets\Gate5E\Editor\TevScriptRemoteUpdateBuildGate.cs"
) -Force

Copy-Item -LiteralPath (
    Join-Path $fixtures "base.json"
) -Destination (
    Join-Path $projectRoot `
        "Assets\Resources\TevScriptGate5EBase.json"
) -Force
Copy-Item -LiteralPath (
    Join-Path $fixtures "authority.json"
) -Destination (
    Join-Path $projectRoot `
        "Assets\Resources\TevScriptGate5EAuthority.json"
) -Force

$packageUri = (
    Resolve-Path -LiteralPath $stagedPackageRoot
).Path.Replace("\", "/")
$manifest = [ordered]@{
    dependencies = [ordered]@{
        "com.marcbeacve.tev-script" = "file:$packageUri"
        "com.unity.modules.jsonserialize" = "1.0.0"
        "com.unity.modules.unitywebrequest" = "1.0.0"
    }
}
Write-Host "GATE5E_BUILTIN_MODULE_JSONSERIALIZE=ENABLED"
Write-Host "GATE5E_BUILTIN_MODULE_UNITYWEBREQUEST=ENABLED"
$manifest | ConvertTo-Json -Depth 8 | Set-Content `
    -LiteralPath (Join-Path $projectRoot "Packages\manifest.json") `
    -Encoding utf8

"m_EditorVersion: $editorVersion`n" | Set-Content `
    -LiteralPath (Join-Path $projectRoot `
        "ProjectSettings\ProjectVersion.txt") `
    -Encoding utf8

$oldBuildExe = $env:TEV_SCRIPT_GATE5E_BUILD_EXE
$env:TEV_SCRIPT_GATE5E_BUILD_EXE = $playerExe
try {
    $unityArgs = @(
        "-batchmode"
        "-nographics"
        "-quit"
        "-projectPath"
        ('"' + $projectRoot + '"')
        "-executeMethod"
        "Marcbeacve.TevScript.Gate5E.RemoteUpdate.Editor.TevScriptRemoteUpdateBuildGate.Build"
        "-logFile"
        ('"' + $buildLog + '"')
    )

    $build = Start-Process `
        -FilePath $resolvedUnity `
        -ArgumentList $unityArgs `
        -Wait `
        -PassThru
    $buildExit = $build.ExitCode
}
finally {
    $env:TEV_SCRIPT_GATE5E_BUILD_EXE = $oldBuildExe
}

Write-Host "GATE5E_BUILD_PROCESS_EXIT_CODE=$buildExit"
if ($buildExit -ne 0) {
    if (Test-Path -LiteralPath $buildLog) {
        Get-Content -LiteralPath $buildLog -Tail 300 |
            ForEach-Object { Write-Host $_ }
    }
    throw "GATE5E_IL2CPP_BUILD_FAILED run_root=$runRoot"
}

$buildText = Get-Content -LiteralPath $buildLog -Raw
Require-Markers `
    -Text $buildText `
    -Code "GATE5E_BUILD_WITNESS_MISSING" `
    -Markers @(
        "UNITY_GATE5E_BUILD_BACKEND=IL2CPP"
        "UNITY_GATE5E_BUILD_TARGET=STANDALONE_WINDOWS64"
        "UNITY_GATE5E_BUILD_RESULT=PASS"
    )

$gameAssembly = Join-Path $buildRoot "GameAssembly.dll"
if (-not (Test-Path -LiteralPath $gameAssembly -PathType Leaf)) {
    throw "GATE5E_GAMEASSEMBLY_MISSING"
}

$metadata = @(
    Get-ChildItem -LiteralPath $buildRoot `
        -Recurse -File -Filter "global-metadata.dat" |
    Where-Object {
        $_.FullName -match "[\\/]il2cpp_data[\\/]Metadata[\\/]global-metadata\.dat$"
    }
)
if ($metadata.Count -ne 1) {
    throw "GATE5E_GLOBAL_METADATA_INVALID count=$($metadata.Count)"
}

$mono = @(
    Get-ChildItem -LiteralPath $buildRoot `
        -Recurse -Directory -Filter "MonoBleedingEdge" `
        -ErrorAction SilentlyContinue
)
if ($mono.Count -ne 0) {
    throw "GATE5E_MONO_RUNTIME_PRESENT"
}
Write-Host "GATE5E_GAMEASSEMBLY=PASS"
Write-Host "GATE5E_GLOBAL_METADATA=PASS"
Write-Host "GATE5E_MONO_RUNTIME=ABSENT_PASS"

# Loopback server is intentionally untrusted and HTTP-only.
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$portFile = Join-Path $runRoot "gate5e-port.txt"
$serverOut = Join-Path $runRoot "gate5e-http.log"
$serverErr = Join-Path $runRoot "gate5e-http.err.log"

$server = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @(
        (Join-Path $RepositoryRoot "tools\serve_hot_update_gate5e.py")
        "--fixtures"
        ('"' + $fixtures + '"')
        "--port-file"
        ('"' + $portFile + '"')
    ) `
    -RedirectStandardOutput $serverOut `
    -RedirectStandardError $serverErr `
    -PassThru

try {
    $deadline = (Get-Date).AddSeconds(15)
    while (-not (Test-Path -LiteralPath $portFile -PathType Leaf)) {
        if ($server.HasExited) {
            throw "GATE5E_HTTP_SERVER_EXITED"
        }
        if ((Get-Date) -gt $deadline) {
            throw "GATE5E_HTTP_SERVER_PORT_TIMEOUT"
        }
        Start-Sleep -Milliseconds 100
    }

    $port = (Get-Content -LiteralPath $portFile -Raw).Trim()
    if ($port -notmatch "^[0-9]+$") {
        throw "GATE5E_HTTP_PORT_INVALID=$port"
    }
    $baseUrl = "http://127.0.0.1:$port"
    Write-Host "GATE5E_LOOPBACK_BASE_URL=$baseUrl"

    $oldBase = $env:TEV_SCRIPT_GATE5E_BASE_URL
    $oldStore = $env:TEV_SCRIPT_GATE5E_STORE_PATH
    $oldMode = $env:TEV_SCRIPT_GATE5E_MODE

    try {
        $env:TEV_SCRIPT_GATE5E_BASE_URL = $baseUrl
        $env:TEV_SCRIPT_GATE5E_STORE_PATH = $remoteStore
        $env:TEV_SCRIPT_GATE5E_MODE = "first"

        $first = Start-Process `
            -FilePath $playerExe `
            -ArgumentList @(
                "-batchmode"
                "-nographics"
                "-logFile"
                ('"' + $firstLog + '"')
            ) `
            -Wait `
            -PassThru

        if ($first.ExitCode -ne 0) {
            Get-Content -LiteralPath $firstLog -Tail 300 |
                ForEach-Object { Write-Host $_ }
            throw "GATE5E_FIRST_PLAYER_FAILED exit=$($first.ExitCode)"
        }

        $firstText = Get-Content -LiteralPath $firstLog -Raw
        Require-Markers `
            -Text $firstText `
            -Code "GATE5E_FIRST_WITNESS_MISSING" `
            -Markers @(
                "UNITY_GATE5E_REMOTE_PLAYER_ACTIVE=PASS"
                "UNITY_GATE5E_SIGNATURE_PROVIDER_WINDOWS_CNG=PASS"
                "UNITY_GATE5E_REMOTE_PACKAGE1_ACTIVATED=PASS"
                "UNITY_GATE5E_REMOTE_REPLAY_FAIL_CLOSED=PASS"
                "UNITY_GATE5E_REMOTE_TAMPER_FAIL_CLOSED=PASS"
                "UNITY_GATE5E_TRUNCATED_PACKAGE_FAIL_CLOSED=PASS"
                "UNITY_GATE5E_HTTP_ERROR_FAIL_CLOSED=PASS"
                "UNITY_GATE5E_REMOTE_PACKAGE2_ACTIVATED=PASS"
                "UNITY_GATE5E_DURABLE_INSTALL_WRITTEN=PASS"
                "TEV_SCRIPT_REMOTE_TRANSPORT_GATE_5E=PASS"
            )

        $env:TEV_SCRIPT_GATE5E_MODE = "restore"

        $restore = Start-Process `
            -FilePath $playerExe `
            -ArgumentList @(
                "-batchmode"
                "-nographics"
                "-logFile"
                ('"' + $restoreLog + '"')
            ) `
            -Wait `
            -PassThru

        if ($restore.ExitCode -ne 0) {
            Get-Content -LiteralPath $restoreLog -Tail 300 |
                ForEach-Object { Write-Host $_ }
            throw "GATE5E_RESTORE_PLAYER_FAILED exit=$($restore.ExitCode)"
        }

        $restoreText = Get-Content -LiteralPath $restoreLog -Raw
        Require-Markers `
            -Text $restoreText `
            -Code "GATE5E_RESTORE_WITNESS_MISSING" `
            -Markers @(
                "UNITY_GATE5E_RESTART_PACKAGE_RESTORE=PASS"
                "UNITY_GATE5E_REPLAY_AFTER_RESTART_FAIL_CLOSED=PASS"
                "UNITY_GATE5E_REMOTE_EPOCH2_ACTIVATED=PASS"
                "UNITY_GATE5E_DURABLE_REPLAY_STATE=PASS"
                "TEV_SCRIPT_REMOTE_TRANSPORT_GATE_5E=PASS"
            )
    }
    finally {
        $env:TEV_SCRIPT_GATE5E_BASE_URL = $oldBase
        $env:TEV_SCRIPT_GATE5E_STORE_PATH = $oldStore
        $env:TEV_SCRIPT_GATE5E_MODE = $oldMode
    }
}
finally {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
        $server.WaitForExit()
    }
}

$exeSha = (
    Get-FileHash -LiteralPath $playerExe -Algorithm SHA256
).Hash.ToLowerInvariant()
$gameAssemblySha = (
    Get-FileHash -LiteralPath $gameAssembly -Algorithm SHA256
).Hash.ToLowerInvariant()
$metadataSha = (
    Get-FileHash -LiteralPath $metadata[0].FullName -Algorithm SHA256
).Hash.ToLowerInvariant()
$buildSha = (
    Get-FileHash -LiteralPath $buildLog -Algorithm SHA256
).Hash.ToLowerInvariant()
$firstSha = (
    Get-FileHash -LiteralPath $firstLog -Algorithm SHA256
).Hash.ToLowerInvariant()
$restoreSha = (
    Get-FileHash -LiteralPath $restoreLog -Algorithm SHA256
).Hash.ToLowerInvariant()

$evidenceDir = Join-Path $RepositoryRoot `
    "receipts\hot-update-batch-5c-5e"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$buildEvidence = Join-Path $evidenceDir "GATE5E_BUILD_$stamp.log"
$firstEvidence = Join-Path $evidenceDir "GATE5E_FIRST_$stamp.log"
$restoreEvidence = Join-Path $evidenceDir "GATE5E_RESTORE_$stamp.log"

Copy-Item -LiteralPath $buildLog -Destination $buildEvidence -Force
Copy-Item -LiteralPath $firstLog -Destination $firstEvidence -Force
Copy-Item -LiteralPath $restoreLog -Destination $restoreEvidence -Force

if ((Get-FileHash $buildEvidence -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $buildSha) {
    throw "GATE5E_BUILD_EVIDENCE_COPY_MISMATCH"
}
if ((Get-FileHash $firstEvidence -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $firstSha) {
    throw "GATE5E_FIRST_EVIDENCE_COPY_MISMATCH"
}
if ((Get-FileHash $restoreEvidence -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $restoreSha) {
    throw "GATE5E_RESTORE_EVIDENCE_COPY_MISMATCH"
}

$summary = Join-Path $evidenceDir "HOT_UPDATE_BATCH_$stamp.txt"
@(
    "TEV_SCRIPT_HOT_UPDATE_BATCH_EVIDENCE_V1"
    "BRANCH=$branch"
    "HEAD=$head"
    "TREE=$tree"
    "UNITY_EDITOR_VERSION=$editorVersion"
    "GATE5C=PASS"
    "GATE5D=PASS_WITH_DURABLE_STATE_BOUNDARY"
    "GATE5E=PASS_LOOPBACK_HTTP_IL2CPP"
    "PLAYER_EXE_SHA256=$exeSha"
    "GAMEASSEMBLY_SHA256=$gameAssemblySha"
    "GLOBAL_METADATA_SHA256=$metadataSha"
    "BUILD_LOG_SHA256=$buildSha"
    "FIRST_PLAYER_LOG_SHA256=$firstSha"
    "RESTORE_PLAYER_LOG_SHA256=$restoreSha"
    "PUBLIC_WAN=NOT_PROBED"
    "HOSTILE_STORE_ROLLBACK=NOT_IN_SCOPE"
) | Set-Content -LiteralPath $summary -Encoding utf8

$summarySha = (
    Get-FileHash -LiteralPath $summary -Algorithm SHA256
).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "TEV_SCRIPT_HOT_UPDATE_BATCH_5C_5E=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
Write-Host "HOT_UPDATE_GATE5B_REGRESSION=PASS"
Write-Host "GATE5C_SIGNED_PACKAGE=PASS"
Write-Host "GATE5C_ALGORITHM=ES256_P256_SHA256"
Write-Host "GATE5C_SIGNATURE_FORMAT=IEEE_P1363_FIXED_64"
Write-Host "GATE5C_TEST_PRIVATE_KEY_RUNTIME=ABSENT_PASS"
Write-Host "GATE5C_PRODUCTION_KEY_PROVISIONING=NOT_IN_SCOPE"
Write-Host "GATE5D_ANTI_REPLAY=DURABLE_STATE_PASS"
Write-Host "GATE5D_RESTART_RESTORE=PASS"
Write-Host "GATE5D_HOSTILE_STORE_ROLLBACK=NOT_IN_SCOPE"
Write-Host "GATE5E_REMOTE_TRANSPORT=LOOPBACK_HTTP_PASS_INSIDE_IL2CPP"
Write-Host "GATE5E_SIGNATURE_PROVIDER=WINDOWS_CNG_PASS"
Write-Host "GATE5E_BACKEND=IL2CPP"
Write-Host "GATE5E_AOT=PASS"
Write-Host "GATE5E_NETWORK_BYTES=UNTRUSTED_UNTIL_VERIFIED_PASS"
Write-Host "GATE5E_TAMPER_FAIL_CLOSED=PASS"
Write-Host "GATE5E_TRUNCATION_FAIL_CLOSED=PASS"
Write-Host "GATE5E_HTTP_ERROR_FAIL_CLOSED=PASS"
Write-Host "GATE5E_REPLAY_AFTER_RESTART_FAIL_CLOSED=PASS"
Write-Host "GATE5E_PUBLIC_WAN=NOT_PROBED"
Write-Host "GATE5E_PLAYER_EXE_SHA256=$exeSha"
Write-Host "GATE5E_GAMEASSEMBLY_SHA256=$gameAssemblySha"
Write-Host "GATE5E_GLOBAL_METADATA_SHA256=$metadataSha"
Write-Host "HOT_UPDATE_BATCH_EVIDENCE=$summary"
Write-Host "HOT_UPDATE_BATCH_EVIDENCE_SHA256=$summarySha"
Write-Host "WASM=NOT_IN_SCOPE"
Write-Host "STABLE_RELEASE=NO"
Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED"
