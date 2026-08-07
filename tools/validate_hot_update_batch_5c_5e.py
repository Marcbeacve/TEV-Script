from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "runtimes" / "csharp" / "TevScript.Core"
UNITY_CORE = ROOT / "unity" / "Package" / "Runtime" / "Core"
UPDATE = ROOT / "runtimes" / "csharp" / "TevScript.Update"
UNITY_UPDATE = ROOT / "unity" / "Package" / "Runtime" / "Update"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    core_names = sorted(p.name for p in CORE.glob("*.cs"))
    unity_names = sorted(p.name for p in UNITY_CORE.glob("*.cs"))
    require(core_names == unity_names, "core_name_set")
    require(len(core_names) == 11, f"core_count:{len(core_names)}")

    for name in core_names:
        require(
            (CORE / name).read_bytes() ==
            (UNITY_CORE / name).read_bytes(),
            f"core_mirror:{name}",
        )

    identity = json.loads(
        (ROOT / "unity/CORE_SOURCE_IDENTITY.json").read_text(
            encoding="utf-8"
        )
    )
    require(len(identity["files"]) == 11, "identity_count")

    security = UPDATE / "TevScriptUpdateSecurity.cs"
    unity_security = UNITY_UPDATE / "TevScriptUpdateSecurity.cs"
    require(security.is_file(), "security_missing")
    require(unity_security.is_file(), "unity_security_missing")
    require(
        security.read_bytes() == unity_security.read_bytes(),
        "security_mirror",
    )

    core_update = (
        CORE / "TevScriptUpdate.cs"
    ).read_text(encoding="utf-8")
    security_text = security.read_text(encoding="utf-8")
    fixture_tool = (
        ROOT /
        "runtimes/csharp/TevScript.HotUpdateFixtureTool/Program.cs"
    ).read_text(encoding="utf-8")

    for marker in (
        "TEVS_CS_UPDATE_SIGNATURE_INVALID",
        "TEVS_CS_UPDATE_REPLAY",
        "TEVS_CS_UPDATE_EPOCH_ROLLBACK",
        "TEVS_CS_UPDATE_PLAN_STALE",
        "TryRestoreInstalled",
        "RollbackLastCommit",
    ):
        require(marker in core_update, f"core_marker:{marker}")

    for marker in (
        "ECCurve.NamedCurves.nistP256",
        "HashAlgorithmName.SHA256",
        "VerifyData",
        "File.Replace",
        "Flush(true)",
    ):
        require(marker in security_text, f"security_marker:{marker}")

    require(
        "DSASignatureFormat" not in security_text,
        "product_netstandard_dsasignatureformat_dependency",
    )
    for marker in (
        "TevWindowsCngEcdsaP256Sha256Verifier",
        '"bcrypt.dll"',
        "BCryptOpenAlgorithmProvider",
        "BCryptImportKeyPair",
        "BCryptVerifySignature",
        'AlgorithmProvider = "ECDSA_P256"',
        'EccPublicBlob = "ECCPUBLICBLOB"',
        "signature.Length != 64",
    ):
        require(marker in security_text, f"cng_marker:{marker}")
    require(
        "signature.Length != 64" in security_text,
        "product_p1363_fixed_length_guard",
    )
    require(
        "DSASignatureFormat.IeeeP1363FixedFieldConcatenation"
        in fixture_tool,
        "fixture_signature_format",
    )

    runtime_product = core_update + security_text
    for forbidden in (
        "BEGIN PRIVATE KEY",
        "BEGIN EC PRIVATE KEY",
        "PrimaryD",
        "WrongD",
        "System.Reflection",
        "Assembly.Load",
        "Microsoft.CodeAnalysis",
        "CSharpCodeProvider",
        "UnityWebRequest",
        "HttpClient",
    ):
        require(
            forbidden not in runtime_product,
            f"forbidden_product:{forbidden}",
        )

    gate5e = (
        ROOT /
        "unity/PlayerGates/RemoteUpdate/Runtime/TevScriptRemoteUpdateGate.cs"
    ).read_text(encoding="utf-8")
    require(
        "yield return RunGate();" not in gate5e,
        "gate5e_cs1626_pattern_present",
    )
    require(
        "Stack<IEnumerator>" in gate5e
        and "currentRoutine.MoveNext()" in gate5e
        and "yield return current;" in gate5e,
        "gate5e_guarded_coroutine_driver_missing",
    )
    require(
        "TevWindowsCngEcdsaP256Sha256Verifier" in gate5e,
        "gate5e_cng_provider_missing",
    )
    require(
        "TevEcdsaP256Sha256Verifier(" not in gate5e,
        "gate5e_managed_ecdsa_provider_still_bound",
    )

    for marker in (
        "UnityWebRequest.Get",
        "UNITY_GATE5E_SIGNATURE_PROVIDER_WINDOWS_CNG=PASS",
        "UNITY_GATE5E_REMOTE_PACKAGE1_ACTIVATED=PASS",
        "UNITY_GATE5E_REMOTE_TAMPER_FAIL_CLOSED=PASS",
        "UNITY_GATE5E_RESTART_PACKAGE_RESTORE=PASS",
        "UNITY_GATE5E_REPLAY_AFTER_RESTART_FAIL_CLOSED=PASS",
        "TEV_SCRIPT_REMOTE_TRANSPORT_GATE_5E=PASS",
    ):
        require(marker in gate5e, f"gate5e_marker:{marker}")

    runner = (
        ROOT / "RUN_TEV_SCRIPT_HOT_UPDATE_BATCH_5C_5E_V1.ps1"
    ).read_text(encoding="utf-8")
    require(
        '"com.unity.modules.jsonserialize" = "1.0.0"' in runner,
        "gate5e_jsonserialize_module_missing",
    )
    require(
        '"com.unity.modules.unitywebrequest" = "1.0.0"' in runner,
        "gate5e_unitywebrequest_module_missing",
    )

    print("HOT_UPDATE_CORE_MIRROR=11_BYTE_IDENTICAL_PASS")
    print("HOT_UPDATE_SECURITY_MIRROR=BYTE_IDENTICAL_PASS")
    print("GATE5C_ES256_P1363_STATIC=PASS")
    print("GATE5D_DURABLE_STORE_STATIC=PASS")
    print("GATE5E_UNITYWEBREQUEST_STATIC=PASS")
    print("GATE5E_JSONSERIALIZE_STATIC=PASS")
    print("GATE5E_COROUTINE_DRIVER_STATIC=PASS")
    print("GATE5E_SIGNATURE_PROVIDER_STATIC=WINDOWS_CNG_PASS")
    print("HOT_UPDATE_TEST_PRIVATE_KEY_PRODUCT_RUNTIME=ABSENT_PASS")
    print("TEV_SCRIPT_HOT_UPDATE_BATCH_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
