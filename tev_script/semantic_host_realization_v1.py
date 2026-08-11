from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping, cast

from .canonical import canonical_hash, canonical_json
from .lowering_receipt_v2 import verify_ir_v3_lowering_receipt
from .semantic_artifact_v0 import ArtifactDescriptorV0, ArtifactManifestV0
from .semantic_evidence_v0 import EvidenceItemV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_machine_v0 import ExecutableFormatV0, MachineCapabilityV0, MachineFieldV0
from .semantic_realization_v0 import RealizationCandidateV0
from .semantic_resource_algebra_v0 import ResourceVectorV0

HOST_RUNTIME_PROFILE_SCHEMA_V1 = "TEV_SCRIPT_HOST_RUNTIME_PROFILE_V1"
HOST_RUNTIME_MATERIALIZATION_SCHEMA_V1 = "TEV_SCRIPT_HOST_RUNTIME_MATERIALIZATION_V1"
HOST_EXECUTION_TRANSFORMATION_SCHEMA_V1 = "TEV_SCRIPT_EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_V1"
HOST_INTERFACE_SCHEMA_V1 = "TEV_SCRIPT_PROGRAM_IR_V3_HOST_INTERFACE_V1"
HOST_RUNTIME_ROLE_SCHEMA_V1 = "TEV_SCRIPT_HOST_RUNTIME_ROLE_V1"
HOST_CONFORMANCE_COVERAGE_SCHEMA_V1 = "TEV_SCRIPT_HOST_CONFORMANCE_COVERAGE_V1"
PROGRAM_IR_V3_MATERIALIZATION_SCHEMA_V1 = "TEV_SCRIPT_PROGRAM_IR_V3_MATERIALIZATION_V1"
HOST_EVIDENCE_AUTHORITY_SCHEMA_V1 = "TEV_SCRIPT_HOST_EVIDENCE_AUTHORITY_V1"
HOST_EXECUTION_EVIDENCE_SCHEMA_V1 = "TEV_SCRIPT_HOST_EXECUTION_EVIDENCE_V1"
HOST_EXECUTION_ADMISSION_SCHEMA_V1 = "TEV_SCRIPT_HOST_EXECUTION_ADMISSION_V1"
CROSS_HOST_EQUIVALENCE_SCHEMA_V1 = "TEV_SCRIPT_CROSS_HOST_EQUIVALENCE_V1"

EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1 = "CANONICAL_RECEIPT_HASH_PARITY"
EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1 = "CANONICAL_RECEIPT_BYTES_PARITY"

_EVIDENCE_LEVEL_RANK = {
    EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1: 1,
    EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1: 2,
}

_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class HostRealizationError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise HostRealizationError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise HostRealizationError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def _mapping(value: Mapping[str, Any] | None, what: str) -> dict[str, Any]:
    result = {} if value is None else dict(value)
    try:
        canonical_json(result)
    except Exception as error:
        raise HostRealizationError(f"{what} must be canonicalizable") from error
    return result


def _semantic_hash(kind: str, **payload: object) -> str:
    return canonical_hash({"schema": "TEV_SCRIPT_HOST_SEMANTIC_IDENTITY_V1", "kind": kind, **payload})


def _evidence_level(value: str) -> str:
    level = str(value)
    if level not in _EVIDENCE_LEVEL_RANK:
        raise HostRealizationError("unknown host execution evidence level")
    return level


EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1 = canonical_hash(
    {
        "schema": HOST_EXECUTION_TRANSFORMATION_SCHEMA_V1,
        "input_schema": "TEV_SCRIPT_PROGRAM_IR_V3",
        "language_version": "1.0.0",
        "obligations": [
            "validate_program_ir_v3_before_execution",
            "closed_runtime_type_table",
            "canonical_value_semantics",
            "least_authority_capability_bindings",
            "canonical_checkpoint_identity",
            "deterministic_observable_result_for_same_semantic_inputs",
        ],
        "outputs": [
            "runtime_state",
            "emitted_events",
            "observations",
            "receipts",
        ],
    }
)

PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1 = canonical_hash(
    {
        "schema": HOST_INTERFACE_SCHEMA_V1,
        "accepts": "TEV_SCRIPT_PROGRAM_IR_V3",
        "requires_validation": True,
        "capabilities": "explicit_least_authority_bindings",
        "checkpoint": "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2_OR_EQUIVALENT",
        "canonical_outputs": True,
    }
)

HOST_RUNTIME_ENTRYPOINT_ROLE_HASH_V1 = canonical_hash(
    {
        "schema": HOST_RUNTIME_ROLE_SCHEMA_V1,
        "role": "execute_program_ir_v3_runtime_closure",
    }
)

IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1 = _semantic_hash(
    "capability",
    operation="execute_program_ir_v3",
    contract_hash=EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
)


def _format_semantics(kind: str, **properties: object) -> str:
    return _semantic_hash("executable_format", format_kind=kind, **properties)


def _capability_semantics(kind: str, **properties: object) -> str:
    return _semantic_hash("substrate_capability", capability_kind=kind, **properties)


PYTHON_RUNTIME_CAPABILITY_HASH_V1 = _capability_semantics(
    "managed_language_runtime",
    language_family="python",
    minimum_language_contract="python_3_11",
)
ECMASCRIPT_ES2022_CAPABILITY_HASH_V1 = _capability_semantics(
    "managed_language_runtime",
    language_family="ecmascript",
    language_contract="es2022_modules",
)
DOTNET_MANAGED_RUNTIME_CAPABILITY_HASH_V1 = _capability_semantics(
    "managed_runtime",
    runtime_contract="dotnet_managed_assembly",
)
WEBASSEMBLY_CORE_CAPABILITY_HASH_V1 = _capability_semantics(
    "webassembly_core",
    module_contract="wasm_magic_and_valid_module",
)
BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1 = _capability_semantics(
    "browser_webassembly_host",
    execution_context="browser",
)
WASI_RUNTIME_CAPABILITY_HASH_V1 = _capability_semantics(
    "wasi_runtime",
    execution_context="wasi",
)
WASI_HTTP_LINKAGE_CAPABILITY_HASH_V1 = _capability_semantics(
    "wasi_http_linkage",
    interface_version="0.2",
    semantics="linkage_only_not_network_authority",
)
UNITY_WEBGL_RUNTIME_CAPABILITY_HASH_V1 = _capability_semantics(
    "unity_webgl_runtime",
    execution_context="browser_webgl",
)
WEBGL2_CAPABILITY_HASH_V1 = _capability_semantics(
    "graphics_context",
    contract="webgl2",
)

THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1 = canonical_hash(
    {
        "schema": HOST_EVIDENCE_AUTHORITY_SCHEMA_V1,
        "authority": "python_javascript_csharp_ir_v3_cross_runtime",
        "maximum_level": EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
        "obligations": [
            "execute_same_program_ir_v3",
            "execute_same_conformance_scenario",
            "compare_python_javascript_csharp_receipt_bytes_exactly",
        ],
    }
)
BROWSER_WASM_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1 = canonical_hash(
    {
        "schema": HOST_EVIDENCE_AUTHORITY_SCHEMA_V1,
        "authority": "browser_wasm_ir_v3_conformance",
        "maximum_level": EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
        "obligations": [
            "execute_program_ir_v3_in_browser_wasm",
            "compare_observed_receipt_hash_to_reference",
            "compare_checkpoint_hash_to_reference",
        ],
    }
)
WASI_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1 = canonical_hash(
    {
        "schema": HOST_EVIDENCE_AUTHORITY_SCHEMA_V1,
        "authority": "wasi_ir_v3_conformance",
        "maximum_level": EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
        "obligations": [
            "execute_program_ir_v3_in_wasi",
            "compare_observed_receipt_hash_to_reference",
            "compare_checkpoint_hash_and_canonical_bytes_to_reference",
            "verify_fresh_restore_identity",
        ],
    }
)


@dataclass(frozen=True, slots=True, init=False)
class ProgramIRV3MaterializationV1:
    """Exact V1 linked-program -> IR V3 materialization authenticated by receipt V2.

    Program identity is deliberately independent from host runtime, machine,
    deployment location and provider identity. Construction succeeds only after
    the normative lowering-receipt verifier proves the exact linked source,
    IR V3 target and canonical bytes supplied by the caller.
    """

    receipt_profile: str
    lowering_profile: str
    source_semantic_hash: str
    target_semantic_hash: str
    source_artifact_sha256: str
    target_artifact_sha256: str
    lowering_receipt_hash: str

    def __init__(
        self,
        *,
        receipt: Mapping[str, object],
        source: Any,
        target: Any,
    ) -> None:
        verify_ir_v3_lowering_receipt(receipt, source, target)
        source_receipt = cast(Mapping[str, object], receipt["source"])
        target_receipt = cast(Mapping[str, object], receipt["target"])
        object.__setattr__(self, "receipt_profile", _stable(str(receipt["profile"]), "lowering receipt profile"))
        object.__setattr__(self, "lowering_profile", _stable(str(target_receipt["lowering_profile"]), "IR V3 lowering profile"))
        object.__setattr__(self, "source_semantic_hash", _hash64(str(source_receipt["semantic_hash"]), "source semantic hash"))
        object.__setattr__(self, "target_semantic_hash", _hash64(str(target_receipt["semantic_hash"]), "target semantic hash"))
        object.__setattr__(self, "source_artifact_sha256", _hash64(str(source_receipt["artifact_sha256"]), "source artifact sha256"))
        object.__setattr__(self, "target_artifact_sha256", _hash64(str(target_receipt["artifact_sha256"]), "target artifact sha256"))
        object.__setattr__(self, "lowering_receipt_hash", _hash64(str(receipt["receipt_hash"]), "lowering receipt hash"))

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": PROGRAM_IR_V3_MATERIALIZATION_SCHEMA_V1,
            "source_schema": "TEV_SCRIPT_LINKED_PROGRAM_V1",
            "target_schema": "TEV_SCRIPT_PROGRAM_IR_V3",
            "language_version": "1.0.0",
            "receipt_profile": self.receipt_profile,
            "lowering_profile": self.lowering_profile,
            "source_semantic_hash": self.source_semantic_hash,
            "target_semantic_hash": self.target_semantic_hash,
            "source_artifact_sha256": self.source_artifact_sha256,
            "target_artifact_sha256": self.target_artifact_sha256,
            "lowering_receipt_hash": self.lowering_receipt_hash,
        }

    @property
    def materialization_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {
            **self.semantic_object(),
            "materialization_hash": self.materialization_hash,
        }

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.program_ir_v3_materialization.v1", self.to_object())


@dataclass(frozen=True, slots=True)
class HostRuntimeProfileV1:
    """Provider-neutral target profile for an IR V3 execution host.

    A profile describes semantic requirements; it does not by itself prove that
    an implementation exists or has passed a gate. `profile_id` and `metadata`
    are records only. Semantic identity comes from the common execution
    Transformation, executable-format semantics, interface and substrate
    capability semantics.
    """

    profile_id: str
    executable_format_semantics_hash: str
    required_substrate_capability_semantic_hashes: tuple[str, ...]
    interface_hash: str = PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1
    semantic_properties: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _stable(self.profile_id, "host profile_id"))
        object.__setattr__(self, "executable_format_semantics_hash", _hash64(self.executable_format_semantics_hash, "executable format semantics hash"))
        object.__setattr__(
            self,
            "required_substrate_capability_semantic_hashes",
            _hashes(self.required_substrate_capability_semantic_hashes, "host substrate capability semantic hash"),
        )
        object.__setattr__(self, "interface_hash", _hash64(self.interface_hash, "host interface_hash"))
        object.__setattr__(self, "semantic_properties", _mapping(self.semantic_properties, "host semantic_properties"))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "host metadata"))

    @property
    def executable_format(self) -> ExecutableFormatV0:
        return ExecutableFormatV0(
            format_id=self.profile_id + ".runtime_bundle",
            semantics_hash=self.executable_format_semantics_hash,
            semantic_properties={
                "input_schema": "TEV_SCRIPT_PROGRAM_IR_V3",
                "host_interface_hash": self.interface_hash,
            },
            metadata={"profile_id": self.profile_id},
        )

    @property
    def machine(self) -> MachineFieldV0:
        common = MachineCapabilityV0(
            capability_id=self.profile_id + ".execute_ir_v3",
            semantic_hash=IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1,
            capability_class="execution",
            semantic_properties={"transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1},
        )
        substrate = tuple(
            MachineCapabilityV0(
                capability_id=f"{self.profile_id}.substrate.{index}",
                semantic_hash=semantic_hash,
                capability_class="substrate",
            )
            for index, semantic_hash in enumerate(self.required_substrate_capability_semantic_hashes)
        )
        return MachineFieldV0(
            machine_id=self.profile_id + ".machine_profile",
            capabilities=(common, *substrate),
            executable_formats=(self.executable_format,),
            semantic_properties={
                "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
                "host_interface_hash": self.interface_hash,
                **dict(self.semantic_properties or {}),
            },
            metadata={"profile_id": self.profile_id, **dict(self.metadata or {})},
        )

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": HOST_RUNTIME_PROFILE_SCHEMA_V1,
            "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            "interface_hash": self.interface_hash,
            "executable_format": self.executable_format.profile_object(),
            "required_substrate_capability_semantic_hashes": list(self.required_substrate_capability_semantic_hashes),
            "machine_profile_hash": self.machine.machine_hash,
            "semantic_properties": dict(self.semantic_properties or {}),
        }

    @property
    def profile_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {
            **self.semantic_object(),
            "profile_hash": self.profile_hash,
            "profile_id": self.profile_id,
            "metadata": dict(self.metadata or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.host_runtime_profile.v1", self.to_object())


@dataclass(frozen=True, slots=True)
class HostRuntimeMaterializationV1:
    """Exact deployment closure for one host runtime target profile.

    `runtime_closure_sha256` must hash the complete deployable closure consumed
    by the host gate, not a convenient source file. Physical locations and
    filenames remain outside semantic identity.
    """

    profile: HostRuntimeProfileV1
    runtime_closure_sha256: str
    provenance_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_closure_sha256", _hash64(self.runtime_closure_sha256, "runtime closure sha256"))
        object.__setattr__(self, "provenance_hashes", _hashes(self.provenance_hashes, "host provenance hash"))

    @property
    def artifact_manifest(self) -> ArtifactManifestV0:
        descriptor = ArtifactDescriptorV0(
            role_id=self.profile.profile_id + ".runtime_closure",
            role_semantics_hash=HOST_RUNTIME_ENTRYPOINT_ROLE_HASH_V1,
            format_hash=self.profile.executable_format.format_hash,
            content_hash=self.runtime_closure_sha256,
            interface_hash=self.profile.interface_hash,
            entrypoint=True,
            required_machine_capability_semantic_hashes=(
                IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1,
                *self.profile.required_substrate_capability_semantic_hashes,
            ),
        )
        return ArtifactManifestV0((descriptor,))

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": HOST_RUNTIME_MATERIALIZATION_SCHEMA_V1,
            "host_profile_hash": self.profile.profile_hash,
            "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            "machine_hash": self.profile.machine.machine_hash,
            "artifact_manifest_hash": self.artifact_manifest.manifest_hash,
            "runtime_closure_sha256": self.runtime_closure_sha256,
        }

    @property
    def materialization_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {
            **self.semantic_object(),
            "materialization_hash": self.materialization_hash,
            "profile": self.profile.to_object(),
            "artifact_manifest": self.artifact_manifest.to_object(),
            "provenance_hashes": list(self.provenance_hashes),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.host_runtime_materialization.v1", self.to_object())

    def candidate(
        self,
        *,
        transformation_regime_binding_hash: str,
        resource_estimate_claim_hash: str,
        regime_preservation_claim_hash: str,
        evidence_hashes: Iterable[str],
        assumption_hashes: Iterable[str] = (),
        predicted_resources: ResourceVectorV0 = ResourceVectorV0(),
    ) -> RealizationCandidateV0:
        return RealizationCandidateV0(
            transformation_semantic_hash=EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            transformation_regime_binding_hash=_hash64(transformation_regime_binding_hash, "transformation regime binding hash"),
            realization_kind="host_runtime",
            machine_hash=self.profile.machine.machine_hash,
            artifact_manifest_hash=self.artifact_manifest.manifest_hash,
            semantic_relation="EXACT_EQUIVALENT",
            assumption_hashes=tuple(assumption_hashes),
            provenance_hashes=(self.record_hash, *self.provenance_hashes),
            predicted_resources=predicted_resources,
            resource_estimate_claim_hash=_hash64(resource_estimate_claim_hash, "resource estimate claim hash"),
            evidence_hashes=tuple(evidence_hashes),
            regime_preservation_claim_hash=_hash64(regime_preservation_claim_hash, "regime preservation claim hash"),
        )


def conformance_evidence_for_candidate(
    *,
    candidate: RealizationCandidateV0,
    profile: HostRuntimeProfileV1,
    evidence_id: str,
    scope_hash: str,
    verifier_hash: str,
    witness_hash: str,
    method: str = "DIFFERENTIAL_TEST",
    assumption_hashes: Iterable[str] = (),
    status: str = "ACTIVE",
) -> EvidenceItemV0:
    if candidate.transformation_semantic_hash != EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1:
        raise HostRealizationError("host conformance evidence candidate transformation mismatch")
    if candidate.machine_hash != profile.machine.machine_hash:
        raise HostRealizationError("host conformance evidence machine mismatch")
    if status == "ACTIVE" and not is_ir_v3_admitted_host_profile_v1(profile):
        raise HostRealizationError("active IR V3 conformance evidence requires an admitted host profile")
    return EvidenceItemV0(
        evidence_id=evidence_id,
        claim_hash=candidate.semantic_claim_hash,
        scope_hash=_hash64(scope_hash, "host conformance scope hash"),
        method=method,
        verifier_hash=_hash64(verifier_hash, "host conformance verifier hash"),
        witness_hash=_hash64(witness_hash, "host conformance witness hash"),
        assumption_hashes=tuple(assumption_hashes),
        coverage={
            "schema": HOST_CONFORMANCE_COVERAGE_SCHEMA_V1,
            "host_profile_hash": profile.profile_hash,
            "machine_hash": profile.machine.machine_hash,
            "artifact_manifest_hash": candidate.artifact_manifest_hash,
            "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
        },
        status=status,
    )


def python_reference_host_profile_v1() -> HostRuntimeProfileV1:
    return HostRuntimeProfileV1(
        "python.reference.ir_v3",
        _format_semantics("python_distribution_bundle", interface="program_ir_v3_host_v1"),
        (PYTHON_RUNTIME_CAPABILITY_HASH_V1,),
        semantic_properties={"production_input": "IR_ONLY", "source_compilation_at_runtime": False},
    )


def javascript_reference_host_profile_v1() -> HostRuntimeProfileV1:
    return HostRuntimeProfileV1(
        "javascript.es2022.reference.ir_v3",
        _format_semantics("ecmascript_es2022_module_bundle", interface="program_ir_v3_host_v1"),
        (ECMASCRIPT_ES2022_CAPABILITY_HASH_V1,),
        semantic_properties={"module_contract": "ES2022", "production_input": "IR_ONLY"},
    )


def csharp_reference_host_profile_v1() -> HostRuntimeProfileV1:
    return HostRuntimeProfileV1(
        "csharp.dotnet.reference.ir_v3",
        _format_semantics("dotnet_managed_runtime_bundle", interface="program_ir_v3_host_v1"),
        (DOTNET_MANAGED_RUNTIME_CAPABILITY_HASH_V1,),
        semantic_properties={"deterministic_build_required": True, "production_input": "IR_ONLY"},
    )


def browser_wasm_host_profile_v1() -> HostRuntimeProfileV1:
    return HostRuntimeProfileV1(
        "browser.wasm.reference.ir_v3",
        _format_semantics("browser_webassembly_publish_bundle", interface="program_ir_v3_host_v1"),
        (WEBASSEMBLY_CORE_CAPABILITY_HASH_V1, BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1),
        semantic_properties={"execution_context": "browser", "aot_compatible": True},
    )


def wasi_host_profile_v1() -> HostRuntimeProfileV1:
    return HostRuntimeProfileV1(
        "wasi.wasmtime.reference.ir_v3",
        _format_semantics("wasi_webassembly_publish_bundle", interface="program_ir_v3_host_v1"),
        (
            WEBASSEMBLY_CORE_CAPABILITY_HASH_V1,
            WASI_RUNTIME_CAPABILITY_HASH_V1,
            WASI_HTTP_LINKAGE_CAPABILITY_HASH_V1,
        ),
        semantic_properties={"execution_context": "wasi", "browser_dependency": False},
    )


def unity_webgl_host_profile_v1() -> HostRuntimeProfileV1:
    """IR V3 target profile for Unity-WebGL.

    Gate 6A currently exercises the legacy portable Unity surface, so this
    target is intentionally excluded from IR V3 admission until a V3 Unity
    runtime gate supplies matching evidence.
    """
    return HostRuntimeProfileV1(
        "unity.webgl.reference.ir_v3",
        _format_semantics("unity_webgl_deployment_bundle", interface="program_ir_v3_host_v1"),
        (
            WEBASSEMBLY_CORE_CAPABILITY_HASH_V1,
            BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1,
            UNITY_WEBGL_RUNTIME_CAPABILITY_HASH_V1,
            WEBGL2_CAPABILITY_HASH_V1,
        ),
        semantic_properties={"execution_context": "browser_webgl", "unity_adapter": True},
    )


def known_v1_host_profiles() -> tuple[HostRuntimeProfileV1, ...]:
    """All known R1 host target profiles, including targets not yet admitted."""
    return (
        python_reference_host_profile_v1(),
        javascript_reference_host_profile_v1(),
        csharp_reference_host_profile_v1(),
        browser_wasm_host_profile_v1(),
        wasi_host_profile_v1(),
        unity_webgl_host_profile_v1(),
    )


def admitted_ir_v3_host_profiles_v1() -> tuple[HostRuntimeProfileV1, ...]:
    """Profiles backed by an existing IR V3 execution/parity gate."""
    return (
        python_reference_host_profile_v1(),
        javascript_reference_host_profile_v1(),
        csharp_reference_host_profile_v1(),
        browser_wasm_host_profile_v1(),
        wasi_host_profile_v1(),
    )


def ir_v3_evidence_authority_for_profile_v1(profile: HostRuntimeProfileV1) -> tuple[str, str] | None:
    profile_hash = profile.profile_hash
    byte_parity = (
        python_reference_host_profile_v1(),
        javascript_reference_host_profile_v1(),
        csharp_reference_host_profile_v1(),
    )
    if any(profile_hash == item.profile_hash for item in byte_parity):
        return (
            EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1,
        )
    browser = browser_wasm_host_profile_v1()
    if profile_hash == browser.profile_hash:
        return (
            EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            BROWSER_WASM_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1,
        )
    wasi = wasi_host_profile_v1()
    if profile_hash == wasi.profile_hash:
        return (
            EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            WASI_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1,
        )
    return None


def ir_v3_evidence_ceiling_for_profile_v1(profile: HostRuntimeProfileV1) -> str | None:
    authority = ir_v3_evidence_authority_for_profile_v1(profile)
    return None if authority is None else authority[0]


def is_ir_v3_admitted_host_profile_v1(profile: HostRuntimeProfileV1) -> bool:
    return ir_v3_evidence_authority_for_profile_v1(profile) is not None


def _verify_ir_v3_conformance_receipt_identity(
    receipt: Mapping[str, object],
    program: ProgramIRV3MaterializationV1,
) -> tuple[str, str]:
    item = dict(receipt)
    required = {
        "schema",
        "scenario_id",
        "scenario_hash",
        "program_semantic_hash",
        "source_semantic_hash",
        "initial_state_hash",
        "steps",
        "capability_calls",
        "final_state",
        "final_state_hash",
        "receipt_hash",
    }
    if set(item) != required:
        raise HostRealizationError("IR V3 conformance receipt field set mismatch")
    if item["schema"] != "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1":
        raise HostRealizationError("IR V3 conformance receipt schema mismatch")
    _stable(str(item["scenario_id"]), "IR V3 conformance scenario id")
    scenario_hash = _hash64(str(item["scenario_hash"]), "IR V3 conformance scenario hash")
    program_hash = _hash64(str(item["program_semantic_hash"]), "IR V3 conformance program hash")
    if program_hash != program.target_semantic_hash:
        raise HostRealizationError("IR V3 conformance receipt program mismatch")
    source_hash = _hash64(str(item["source_semantic_hash"]), "IR V3 conformance source hash")
    if source_hash != program.source_semantic_hash:
        raise HostRealizationError("IR V3 conformance receipt source mismatch")
    _hash64(str(item["initial_state_hash"]), "IR V3 conformance initial state hash")
    _hash64(str(item["final_state_hash"]), "IR V3 conformance final state hash")
    receipt_hash = _hash64(str(item["receipt_hash"]), "IR V3 conformance receipt hash")
    body = {key: value for key, value in item.items() if key != "receipt_hash"}
    if canonical_hash(body) != receipt_hash:
        raise HostRealizationError("IR V3 conformance receipt integrity mismatch")
    return scenario_hash, receipt_hash


@dataclass(frozen=True, slots=True, init=False)
class HostExecutionEvidenceV1:
    """Content-addressed host witness record, not yet admitted to a program receipt.

    The semantic verifier contract is derived from the host profile; callers
    can only supply the concrete verifier artifact hash and witness hash.
    """

    program_materialization_hash: str
    host_profile_hash: str
    host_materialization_hash: str
    scenario_hash: str
    evidence_level: str
    observed_receipt_hash: str
    verifier_contract_hash: str
    verifier_artifact_sha256: str
    witness_hash: str

    def __init__(
        self,
        *,
        program: ProgramIRV3MaterializationV1,
        host: HostRuntimeMaterializationV1,
        scenario_hash: str,
        evidence_level: str,
        observed_receipt_hash: str,
        verifier_artifact_sha256: str,
        witness_hash: str,
    ) -> None:
        authority = ir_v3_evidence_authority_for_profile_v1(host.profile)
        if authority is None:
            raise HostRealizationError("host profile is not admitted for IR V3 execution evidence")
        ceiling, verifier_contract_hash = authority
        level = _evidence_level(evidence_level)
        if _EVIDENCE_LEVEL_RANK[level] > _EVIDENCE_LEVEL_RANK[ceiling]:
            raise HostRealizationError("host execution evidence exceeds the profile gate ceiling")
        object.__setattr__(self, "program_materialization_hash", program.materialization_hash)
        object.__setattr__(self, "host_profile_hash", host.profile.profile_hash)
        object.__setattr__(self, "host_materialization_hash", host.materialization_hash)
        object.__setattr__(self, "scenario_hash", _hash64(scenario_hash, "host execution scenario hash"))
        object.__setattr__(self, "evidence_level", level)
        object.__setattr__(self, "observed_receipt_hash", _hash64(observed_receipt_hash, "observed conformance receipt hash"))
        object.__setattr__(self, "verifier_contract_hash", verifier_contract_hash)
        object.__setattr__(self, "verifier_artifact_sha256", _hash64(verifier_artifact_sha256, "host execution verifier artifact sha256"))
        object.__setattr__(self, "witness_hash", _hash64(witness_hash, "host execution witness hash"))

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": HOST_EXECUTION_EVIDENCE_SCHEMA_V1,
            "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            "program_materialization_hash": self.program_materialization_hash,
            "host_profile_hash": self.host_profile_hash,
            "host_materialization_hash": self.host_materialization_hash,
            "scenario_hash": self.scenario_hash,
            "evidence_level": self.evidence_level,
            "observed_receipt_hash": self.observed_receipt_hash,
            "verifier_contract_hash": self.verifier_contract_hash,
            "verifier_artifact_sha256": self.verifier_artifact_sha256,
            "witness_hash": self.witness_hash,
        }

    @property
    def evidence_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {**self.semantic_object(), "evidence_hash": self.evidence_hash}

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.host_execution_evidence.v1", self.to_object())


@dataclass(frozen=True, slots=True, init=False)
class HostExecutionAdmissionV1:
    """Admission of one host witness against the exact canonical V3 receipt identity."""

    program_materialization_hash: str
    host_profile_hash: str
    host_materialization_hash: str
    scenario_hash: str
    evidence_hash: str
    receipt_hash: str
    admitted_level: str

    def __init__(
        self,
        *,
        program: ProgramIRV3MaterializationV1,
        host: HostRuntimeMaterializationV1,
        evidence: HostExecutionEvidenceV1,
        reference_receipt: Mapping[str, object],
    ) -> None:
        if evidence.program_materialization_hash != program.materialization_hash:
            raise HostRealizationError("host execution evidence program binding mismatch")
        if evidence.host_profile_hash != host.profile.profile_hash:
            raise HostRealizationError("host execution evidence profile binding mismatch")
        if evidence.host_materialization_hash != host.materialization_hash:
            raise HostRealizationError("host execution evidence materialization binding mismatch")
        authority = ir_v3_evidence_authority_for_profile_v1(host.profile)
        if authority is None or evidence.verifier_contract_hash != authority[1]:
            raise HostRealizationError("host execution evidence verifier contract mismatch")
        scenario_hash, receipt_hash = _verify_ir_v3_conformance_receipt_identity(reference_receipt, program)
        if evidence.scenario_hash != scenario_hash:
            raise HostRealizationError("host execution evidence scenario binding mismatch")
        if evidence.observed_receipt_hash != receipt_hash:
            raise HostRealizationError("host execution evidence observed receipt mismatch")
        object.__setattr__(self, "program_materialization_hash", program.materialization_hash)
        object.__setattr__(self, "host_profile_hash", host.profile.profile_hash)
        object.__setattr__(self, "host_materialization_hash", host.materialization_hash)
        object.__setattr__(self, "scenario_hash", scenario_hash)
        object.__setattr__(self, "evidence_hash", evidence.evidence_hash)
        object.__setattr__(self, "receipt_hash", receipt_hash)
        object.__setattr__(self, "admitted_level", evidence.evidence_level)

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": HOST_EXECUTION_ADMISSION_SCHEMA_V1,
            "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            "program_materialization_hash": self.program_materialization_hash,
            "host_profile_hash": self.host_profile_hash,
            "host_materialization_hash": self.host_materialization_hash,
            "scenario_hash": self.scenario_hash,
            "evidence_hash": self.evidence_hash,
            "receipt_hash": self.receipt_hash,
            "admitted_level": self.admitted_level,
        }

    @property
    def admission_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {**self.semantic_object(), "admission_hash": self.admission_hash}

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.host_execution_admission.v1", self.to_object())


@dataclass(frozen=True, slots=True, init=False)
class CrossHostEquivalenceV1:
    """Fail-closed equivalence claim over independently admitted host evidence."""

    program_materialization_hash: str
    scenario_hash: str
    receipt_hash: str
    equivalence_level: str
    member_bindings: tuple[tuple[str, str, str, str], ...]

    def __init__(
        self,
        *,
        admissions: Iterable[HostExecutionAdmissionV1],
        claimed_level: str,
    ) -> None:
        members = tuple(admissions)
        if len(members) < 2:
            raise HostRealizationError("cross-host equivalence requires at least two host admissions")
        program_hashes = {item.program_materialization_hash for item in members}
        if len(program_hashes) != 1:
            raise HostRealizationError("cross-host admissions mix program materializations")
        scenario_hashes = {item.scenario_hash for item in members}
        if len(scenario_hashes) != 1:
            raise HostRealizationError("cross-host admissions mix scenarios")
        receipt_hashes = {item.receipt_hash for item in members}
        if len(receipt_hashes) != 1:
            raise HostRealizationError("cross-host admissions disagree on canonical receipt")
        profile_hashes = [item.host_profile_hash for item in members]
        if len(set(profile_hashes)) != len(profile_hashes):
            raise HostRealizationError("cross-host admissions repeat one host profile")
        floor = min(members, key=lambda item: _EVIDENCE_LEVEL_RANK[item.admitted_level]).admitted_level
        claim = _evidence_level(claimed_level)
        if claim != floor:
            raise HostRealizationError("cross-host equivalence level must equal the weakest admitted member")
        bindings = tuple(
            sorted(
                (
                    item.host_profile_hash,
                    item.host_materialization_hash,
                    item.admission_hash,
                    item.admitted_level,
                )
                for item in members
            )
        )
        object.__setattr__(self, "program_materialization_hash", next(iter(program_hashes)))
        object.__setattr__(self, "scenario_hash", next(iter(scenario_hashes)))
        object.__setattr__(self, "receipt_hash", next(iter(receipt_hashes)))
        object.__setattr__(self, "equivalence_level", claim)
        object.__setattr__(self, "member_bindings", bindings)

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": CROSS_HOST_EQUIVALENCE_SCHEMA_V1,
            "execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            "program_materialization_hash": self.program_materialization_hash,
            "scenario_hash": self.scenario_hash,
            "receipt_hash": self.receipt_hash,
            "equivalence_level": self.equivalence_level,
            "members": [
                {
                    "host_profile_hash": profile_hash,
                    "host_materialization_hash": materialization_hash,
                    "admission_hash": admission_hash,
                    "admitted_level": admitted_level,
                }
                for profile_hash, materialization_hash, admission_hash, admitted_level in self.member_bindings
            ],
        }

    @property
    def equivalence_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {**self.semantic_object(), "equivalence_hash": self.equivalence_hash}

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.cross_host_equivalence.v1", self.to_object())


__all__ = [
    "HOST_RUNTIME_PROFILE_SCHEMA_V1",
    "HOST_RUNTIME_MATERIALIZATION_SCHEMA_V1",
    "HOST_EXECUTION_TRANSFORMATION_SCHEMA_V1",
    "HOST_INTERFACE_SCHEMA_V1",
    "HOST_RUNTIME_ROLE_SCHEMA_V1",
    "HOST_CONFORMANCE_COVERAGE_SCHEMA_V1",
    "PROGRAM_IR_V3_MATERIALIZATION_SCHEMA_V1",
    "HOST_EVIDENCE_AUTHORITY_SCHEMA_V1",
    "HOST_EXECUTION_EVIDENCE_SCHEMA_V1",
    "HOST_EXECUTION_ADMISSION_SCHEMA_V1",
    "CROSS_HOST_EQUIVALENCE_SCHEMA_V1",
    "EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1",
    "EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1",
    "HostRealizationError",
    "EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1",
    "PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1",
    "HOST_RUNTIME_ENTRYPOINT_ROLE_HASH_V1",
    "IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1",
    "PYTHON_RUNTIME_CAPABILITY_HASH_V1",
    "ECMASCRIPT_ES2022_CAPABILITY_HASH_V1",
    "DOTNET_MANAGED_RUNTIME_CAPABILITY_HASH_V1",
    "WEBASSEMBLY_CORE_CAPABILITY_HASH_V1",
    "BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1",
    "WASI_RUNTIME_CAPABILITY_HASH_V1",
    "WASI_HTTP_LINKAGE_CAPABILITY_HASH_V1",
    "UNITY_WEBGL_RUNTIME_CAPABILITY_HASH_V1",
    "WEBGL2_CAPABILITY_HASH_V1",
    "THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1",
    "BROWSER_WASM_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1",
    "WASI_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1",
    "ProgramIRV3MaterializationV1",
    "HostRuntimeProfileV1",
    "HostRuntimeMaterializationV1",
    "HostExecutionEvidenceV1",
    "HostExecutionAdmissionV1",
    "CrossHostEquivalenceV1",
    "conformance_evidence_for_candidate",
    "python_reference_host_profile_v1",
    "javascript_reference_host_profile_v1",
    "csharp_reference_host_profile_v1",
    "browser_wasm_host_profile_v1",
    "wasi_host_profile_v1",
    "unity_webgl_host_profile_v1",
    "known_v1_host_profiles",
    "admitted_ir_v3_host_profiles_v1",
    "ir_v3_evidence_authority_for_profile_v1",
    "ir_v3_evidence_ceiling_for_profile_v1",
    "is_ir_v3_admitted_host_profile_v1",
]
