from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "runtimes" / "csharp" / "TevScript.Core"
UNITY_CORE = ROOT / "unity" / "Package" / "Runtime" / "Core"
UPDATE = ROOT / "runtimes" / "csharp" / "TevScript.Update"
UNITY_UPDATE = ROOT / "unity" / "Package" / "Runtime" / "Update"

CORE_IDENTITY_SCHEMA = "TEV_SCRIPT_UNITY_CORE_SOURCE_IDENTITY_V1"
CANONICAL_CORE_PREFIX = PurePosixPath("runtimes/csharp/TevScript.Core")
UNITY_CORE_PREFIX = PurePosixPath("unity/Package/Runtime/Core")
HOST_ONLY_CORE_FILES = frozenset(
    {
        "CompilerCompatibility.V3.cs",
        "GlobalUsings.V3.cs",
    }
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity_path(
    root: Path,
    raw: object,
    *,
    prefix: PurePosixPath,
    label: str,
) -> tuple[Path, str]:
    require(isinstance(raw, str) and bool(raw), f"{label}_path")
    path = PurePosixPath(raw)
    require(
        not path.is_absolute()
        and ".." not in path.parts
        and "." not in path.parts,
        f"{label}_path",
    )
    require(path.parent == prefix, f"{label}_path")
    require(path.suffix == ".cs", f"{label}_extension")
    return root.joinpath(*path.parts), path.name


def validate_core_mirror(root: Path) -> int:
    root = Path(root)
    identity_path = root / "unity" / "CORE_SOURCE_IDENTITY.json"
    require(identity_path.is_file(), "identity_missing")
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"identity_invalid:{type(error).__name__}") from error

    require(isinstance(identity, dict), "identity_object")
    require(identity.get("schema") == CORE_IDENTITY_SCHEMA, "identity_schema")
    files = identity.get("files")
    require(isinstance(files, list) and bool(files), "identity_files")

    canonical_names: set[str] = set()
    package_names: set[str] = set()
    for index, row in enumerate(files):
        require(
            isinstance(row, dict)
            and set(row) == {"canonical", "package", "sha256"},
            f"identity_row:{index}",
        )
        canonical, canonical_name = _identity_path(
            root,
            row["canonical"],
            prefix=CANONICAL_CORE_PREFIX,
            label="canonical",
        )
        package, package_name = _identity_path(
            root,
            row["package"],
            prefix=UNITY_CORE_PREFIX,
            label="package",
        )
        require(canonical_name == package_name, f"identity_name:{index}")
        require(canonical_name not in canonical_names, f"canonical_duplicate:{canonical_name}")
        require(package_name not in package_names, f"package_duplicate:{package_name}")
        canonical_names.add(canonical_name)
        package_names.add(package_name)

        expected_sha = row["sha256"]
        require(
            isinstance(expected_sha, str)
            and len(expected_sha) == 64
            and all(character in "0123456789abcdef" for character in expected_sha),
            f"identity_sha256:{canonical_name}",
        )
        require(canonical.is_file(), f"canonical_missing:{canonical_name}")
        require(package.is_file(), f"package_missing:{package_name}")
        canonical_bytes = canonical.read_bytes()
        package_bytes = package.read_bytes()
        require(canonical_bytes == package_bytes, f"core_mirror:{canonical_name}")
        require(
            _sha256(canonical_bytes) == expected_sha,
            f"core_identity_hash:{canonical_name}",
        )

    core_dir = root / CANONICAL_CORE_PREFIX
    unity_dir = root / UNITY_CORE_PREFIX
    observed_core = {path.name for path in core_dir.glob("*.cs")}
    observed_unity = {path.name for path in unity_dir.glob("*.cs")}

    require(
        observed_unity == package_names,
        "unity_identity_set:"
        f"identity={sorted(package_names)}:observed={sorted(observed_unity)}",
    )
    unclassified = observed_core - canonical_names - HOST_ONLY_CORE_FILES
    require(
        not unclassified,
        f"core_unclassified:{sorted(unclassified)}",
    )
    require(
        canonical_names <= observed_core,
        "core_identity_set:"
        f"identity={sorted(canonical_names)}:observed={sorted(observed_core)}",
    )
    return len(files)


def main() -> int:
    mirror_count = validate_core_mirror(ROOT)

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

    print(f"HOT_UPDATE_CORE_MIRROR={mirror_count}_BYTE_IDENTICAL_PASS")
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
