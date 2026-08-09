from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

BASE = "3d0390d0071204410544a3989391283fd0b66bfa"
EXPECTED = {
    "RUN_TEV_SCRIPT_WASM_SIGNED_UPDATE_GATE6D_V1.ps1",
    "tools/serve_gate6d_browser.py",
    "tools/validate_wasm_signed_update_gate6d.py",
    "docs/WASM_SIGNED_UPDATE_GATE6D_V1.md",
    "runtimes/csharp/TevScript.Update/TevManagedEcdsaP256Sha256Verifier.cs",
    "unity/Package/Runtime/Update/TevManagedEcdsaP256Sha256Verifier.cs",
    "runtimes/csharp/TevScript.BrowserWasmUpdateGate/Program.cs",
    "runtimes/csharp/TevScript.BrowserWasmUpdateGate/TevScript.BrowserWasmUpdateGate.csproj",
    "runtimes/csharp/TevScript.BrowserWasmUpdateGate/index.html",
    "runtimes/csharp/TevScript.BrowserWasmUpdateGate/main.mjs",
    "runtimes/csharp/TevScript.WasiUpdateGate/Program.cs",
    "runtimes/csharp/TevScript.WasiUpdateGate/TevScript.WasiUpdateGate.csproj",
}
PRIVATE_FIXTURE_SECRET_SHA256 = {
    "5b1870479fda0f1c0833fb557ac988bcddec11c16cb489946bf3f081a3c87619",
    "0f1616d98d589afc75a6313facdfe14f9e75633185b6a5764ea655e9ab7386fd",
}


def run(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE)
    return result.stdout


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{label}_MISSING:{needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise RuntimeError(f"{label}_FORBIDDEN:{needle}")


def require_no_private_fixture_secret(text: str, label: str) -> None:
    import re
    for token in re.findall(r"[A-Za-z0-9+/]{40,}={0,2}", text):
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        if digest in PRIVATE_FIXTURE_SECRET_SHA256:
            raise RuntimeError(f"{label}_FORBIDDEN_SHA256:{digest}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    repo = Path(args.repo_root).resolve()

    head = run(repo, "rev-parse", "HEAD").strip()
    closure = {
        "PROJECT_STATE.md",
        "docs/STATUS.md",
        "descriptor.json",
        "evidence/reference-v0.2/wasm-signed-update-gate6d-windows-dotnet10.json",
        "MANIFEST_SHA256.json",
    }
    status_lines = [line for line in run(
        repo, "status", "--porcelain=v1", "--untracked-files=all").splitlines() if line.strip()]

    if head == BASE:
        changed = {line.strip().replace("\\", "/") for line in status_lines}
        paths = {line[3:] if len(line) >= 4 else line for line in changed}
        paths = {p.replace("\\", "/") for p in paths}
        if paths != EXPECTED:
            print("EXPECTED_ONLY:", sorted(EXPECTED - paths))
            print("OBSERVED_EXTRA:", sorted(paths - EXPECTED))
            raise RuntimeError(f"GATE6D_CHANGESET_MISMATCH expected={len(EXPECTED)} observed={len(paths)}")
        validation_mode = "PRECOMMIT_DIRTY_12"
    else:
        parent = run(repo, "rev-parse", "HEAD^").strip()
        if parent != BASE:
            raise RuntimeError(f"GATE6D_COMMITTED_PARENT_MISMATCH expected={BASE} observed={parent}")
        if status_lines:
            raise RuntimeError("GATE6D_COMMITTED_WORKTREE_NOT_CLEAN")
        committed = {line.strip().replace("\\", "/") for line in run(
            repo, "diff", "--name-only", BASE, "HEAD").splitlines() if line.strip()}
        expected_commit = EXPECTED | closure
        if committed != expected_commit:
            print("COMMIT_EXPECTED_ONLY:", sorted(expected_commit - committed))
            print("COMMIT_OBSERVED_EXTRA:", sorted(committed - expected_commit))
            raise RuntimeError(
                f"GATE6D_COMMITTED_CHANGESET_MISMATCH expected={len(expected_commit)} observed={len(committed)}")
        paths = set(EXPECTED)
        validation_mode = "CLEAN_CHILD_COMMIT_17"

    core_changes = run(repo, "diff", "--name-only", BASE, "--", "runtimes/csharp/TevScript.Core", "unity/Package/Runtime/Core").strip()
    if core_changes:
        raise RuntimeError("GATE6D_CORE_PRODUCT_CHANGES_NONZERO:" + core_changes.replace("\n", ","))

    verifier_a = repo / "runtimes/csharp/TevScript.Update/TevManagedEcdsaP256Sha256Verifier.cs"
    verifier_b = repo / "unity/Package/Runtime/Update/TevManagedEcdsaP256Sha256Verifier.cs"
    if verifier_a.read_bytes() != verifier_b.read_bytes():
        raise RuntimeError("GATE6D_UPDATE_VERIFIER_MIRROR_MISMATCH")
    verifier = verifier_a.read_text(encoding="utf-8")
    require_no_private_fixture_secret(verifier, "GATE6D_PRIVATE_KEY")
    for forbidden in ("System.Security.Cryptography", "DllImport", "ECDsa.Create", "SHA256.Create"):
        forbid(verifier, forbidden, "GATE6D_HOST_CRYPTO_DEPENDENCY")
    for required in (
        'AlgorithmId = "ES256"', "signature.Length != 64", "P-256 public key is not on the curve",
        "FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF",
        "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
    ):
        require(verifier, required, "GATE6D_MANAGED_VERIFIER")

    expected_update = {
        "runtimes/csharp/TevScript.Update/TevManagedEcdsaP256Sha256Verifier.cs",
        "unity/Package/Runtime/Update/TevManagedEcdsaP256Sha256Verifier.cs",
    }
    update_changes = {p for p in paths if p.startswith("runtimes/csharp/TevScript.Update/") or p.startswith("unity/Package/Runtime/Update/")}
    tracked_update_drift = run(
        repo, "diff", "--name-only", BASE, "--",
        "runtimes/csharp/TevScript.Update/TevScriptUpdateSecurity.cs",
        "runtimes/csharp/TevScript.Update/TevScript.Update.csproj",
        "unity/Package/Runtime/Update/TevScriptUpdateSecurity.cs",
        "unity/Package/Runtime/Update/Marcbeacve.TevScript.Update.asmdef").strip()
    if tracked_update_drift:
        raise RuntimeError("GATE6D_EXISTING_UPDATE_PRODUCT_DRIFT:" + tracked_update_drift.replace("\n", ","))
    if update_changes != expected_update:
        raise RuntimeError("GATE6D_UPDATE_PRODUCT_CHANGESET_MISMATCH:" + ",".join(sorted(update_changes)))

    browser = (repo / "runtimes/csharp/TevScript.BrowserWasmUpdateGate/Program.cs").read_text(encoding="utf-8")
    main_js = (repo / "runtimes/csharp/TevScript.BrowserWasmUpdateGate/main.mjs").read_text(encoding="utf-8")
    wasi = (repo / "runtimes/csharp/TevScript.WasiUpdateGate/Program.cs").read_text(encoding="utf-8")
    for text, label in ((browser, "BROWSER"), (wasi, "WASI")):
        require(text, "TevManagedEcdsaP256Sha256Verifier", f"GATE6D_{label}")
        require(text, "TevScriptUpdateAuthority", f"GATE6D_{label}")
        require(text, "TEVS_CS_UPDATE_STORE_COMMIT", f"GATE6D_{label}")
        require(text, "TEVS_CS_UPDATE_REPLAY", f"GATE6D_{label}")
    require(browser, "BrowserInstalledUpdateStore", "GATE6D_BROWSER")
    require(browser, "TryRestoreInstalled", "GATE6D_BROWSER")
    require(main_js, "crypto.subtle.verify", "GATE6D_WEBCRYPTO_ORACLE")
    require(main_js, "localStorage.setItem", "GATE6D_BROWSER_DURABLE_STORE")
    require(main_js, "DOTNET_GATE_FAIL", "GATE6D_BROWSER_DIAGNOSTIC_BASE")
    require(main_js, "_RESTORE_STORE_MISSING", "GATE6D_BROWSER_DIAGNOSTIC_SUFFIX")
    require(browser, "GATE6D_BROWSER_RESTORE_STORE_RECORD=MISSING", "GATE6D_BROWSER_RESTORE_DIAGNOSTIC")
    require(wasi, "TevFileInstalledUpdateStore", "GATE6D_WASI_DURABLE_STORE")
    require(wasi, "TryRestoreInstalled", "GATE6D_WASI")

    for rel in EXPECTED:
        text = (repo / rel).read_text(encoding="utf-8", errors="ignore")
        require_no_private_fixture_secret(text, "GATE6D_PRIVATE_KEY_PAYLOAD")

    runner = (repo / "RUN_TEV_SCRIPT_WASM_SIGNED_UPDATE_GATE6D_V1.ps1").read_text(encoding="utf-8")
    require(runner, "--enable-aggressive-domstorage-flushing", "GATE6D_BROWSER_DURABLE_FLUSH")
    require(runner, "GATE6D_BROWSER_STORAGE_FLUSH_POLICY=AGGRESSIVE_DOMSTORAGE", "GATE6D_BROWSER_DURABLE_FLUSH")
    require(runner, "taskkill.exe /PID $Process.Id /T 2>$null", "GATE6D_BROWSER_GRACEFUL_SHUTDOWN")
    for forbidden in ("git push", "git merge", "--force-with-lease", "gh pr", "release create"):
        forbid(runner.lower(), forbidden.lower(), "GATE6D_REMOTE_WRITE")

    print("GATE6D_VALIDATION_MODE=" + validation_mode)
    print("GATE6D_R3_BROWSER_DIAGNOSTIC_VALIDATION=PASS")
    print("GATE6D_STATIC_VALIDATION=PASS")
    print("GATE6D_EXPECTED_REPO_CHANGES=12")
    print("GATE6D_CORE_PRODUCT_CHANGES=0")
    print("GATE6D_UPDATE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL")
    print("GATE6D_UPDATE_VERIFIER_MIRROR=BYTE_IDENTICAL_PASS")
    print("GATE6D_PRIVATE_KEY_PRODUCT=ABSENT_PASS")
    print("GATE6D_MANAGED_ES256_PROVIDER=HOST_INDEPENDENT_PASS")
    print("GATE6D_BROWSER_WEBCRYPTO=INDEPENDENT_ORACLE")
    print("GATE6D_SIGNED_UPDATE_AUTHORITY=UNCHANGED_CORE_PASS")
    print("GATE6D_VERIFIER_SHA256=" + sha(verifier_a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
