from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
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


@dataclass(frozen=True, slots=True)
class HostRuntimeProfileV1:
    """Provider-neutral execution profile for an existing V1 host.

    `profile_id` and `metadata` are records only. Semantic identity comes from
    the common execution Transformation, executable-format semantics,
    interface and substrate-capability semantics.
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
    """Exact deployment closure for one host runtime profile.

    `runtime_closure_sha256` must hash the complete deployable closure consumed
    by the host gate (wheel/tarball/publish bundle/WebGL build closure), not a
    convenient source filename. Physical paths and filenames remain outside
    semantic identity.
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
    return (
        python_reference_host_profile_v1(),
        javascript_reference_host_profile_v1(),
        csharp_reference_host_profile_v1(),
        browser_wasm_host_profile_v1(),
        wasi_host_profile_v1(),
        unity_webgl_host_profile_v1(),
    )


__all__ = [
    "HOST_RUNTIME_PROFILE_SCHEMA_V1",
    "HOST_RUNTIME_MATERIALIZATION_SCHEMA_V1",
    "HOST_EXECUTION_TRANSFORMATION_SCHEMA_V1",
    "HOST_INTERFACE_SCHEMA_V1",
    "HOST_RUNTIME_ROLE_SCHEMA_V1",
    "HOST_CONFORMANCE_COVERAGE_SCHEMA_V1",
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
    "HostRuntimeProfileV1",
    "HostRuntimeMaterializationV1",
    "conformance_evidence_for_candidate",
    "python_reference_host_profile_v1",
    "javascript_reference_host_profile_v1",
    "csharp_reference_host_profile_v1",
    "browser_wasm_host_profile_v1",
    "wasi_host_profile_v1",
    "unity_webgl_host_profile_v1",
    "known_v1_host_profiles",
]
