from __future__ import annotations

from .canonical import canonical_hash
from .contracts_v1 import V1_LANGUAGE_VERSION
from .pipeline_v1 import (
    V1AnalysisBundle,
    V1AutoCompilationBundle,
    V1IrV2CompilationBundle,
    V1IrV3CompilationBundle,
    analyze_v1_mapping,
    analyze_v1_paths,
    analyze_v1_sources,
    compile_v1_mapping_auto,
    compile_v1_mapping_to_ir_v2,
    compile_v1_mapping_to_ir_v3,
    compile_v1_paths_auto,
    compile_v1_paths_to_ir_v2,
    compile_v1_paths_to_ir_v3,
    compile_v1_sources_auto,
    compile_v1_sources_to_ir_v2,
    compile_v1_sources_to_ir_v3,
)
from .lowering_receipt_v2 import (
    LoweringReceiptBundleV2,
    build_ir_v3_lowering_receipt,
    verify_ir_v3_lowering_receipt,
)
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_conformance import IrV3ConformanceReceiptBundle, run_ir_v3_conformance
from .runtime_v3 import EmittedEventV3, ScriptRuntimeV3
from .runtime_checkpoint_v2 import RuntimeCheckpointV2
from .semantic_kernel_v0 import FactV0, SemanticFieldV0, field_from_mapping
from .semantic_apply_v0 import RuleOpV0, apply_rule, commit_prepared, rule_field
from .semantic_artifact_v0 import ArtifactDescriptorV0, ArtifactManifestV0
from .semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
    evaluate_evidence,
)
from .semantic_machine_v0 import (
    ExecutableFormatV0,
    MachineCapabilityV0,
    MachineFieldV0,
    evaluate_machine_compatibility,
)
from .semantic_regime_v0 import (
    RegimeContractV0,
    RegimePreservationClaimV0,
    TransformationRegimeBindingV0,
    evaluate_regime_preservation,
)
from .semantic_resource_algebra_v0 import (
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceCeilingV0,
    ResourceDimensionV0,
    ResourceVectorV0,
)
from .semantic_resource_evidence_v0 import ResourceEstimateClaimV0
from .semantic_realization_v0 import (
    RealizationAdmissionReceiptV0,
    RealizationCandidateV0,
    RealizationPolicyV0,
    RealizationProblemV0,
    admit_realization,
    pareto_front,
)
from .semantic_realization_selection_v0 import (
    RealizationSelectionDecisionV0,
    RealizationSelectionPolicyV0,
    RealizationSelectionProblemV0,
    RealizationSelectionReceiptV0,
    evaluate_realization_selection,
)
from .semantic_realization_resolution_v0 import (
    RealizationSelectionResolutionV0,
    resolve_realization_selection,
)
from .semantic_realization_search_v0 import (
    RealizationPlanningClaimV0,
    RealizationPlanningEvaluationV0,
    SearchCoverageClaimV0,
    SearchCoverageEvaluationV0,
    SearchCoveragePolicyV0,
    SearchCoverageRecordV0,
    evaluate_realization_planning,
    evaluate_search_coverage,
)
from .semantic_host_realization_v1 import (
    EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
    PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1,
    CrossHostEquivalenceV1,
    HostExecutionAdmissionV1,
    HostExecutionEvidenceV1,
    HostRuntimeMaterializationV1,
    HostRuntimeProfileV1,
    ProgramIRV3MaterializationV1,
    admitted_ir_v3_host_profiles_v1,
    browser_wasm_host_profile_v1,
    csharp_reference_host_profile_v1,
    javascript_reference_host_profile_v1,
    known_v1_host_profiles,
    python_reference_host_profile_v1,
    wasi_host_profile_v1,
)
from .semantic_execution_request_v0 import (
    ExecutionIntentV0,
    ExecutionRequestAdmissionReceiptV0,
    ExecutionRequestPolicyV0,
    ExecutionRequestRecordV0,
    ExecutionRequestV0,
    evaluate_execution_request,
)
from .semantic_activation_v0 import (
    ExecutionActivationCandidateV0,
    ExecutionActivationReceiptV0,
    evaluate_execution_activation,
)
from .semantic_execution_observation_v0 import (
    ExecutionObservationClaimV0,
    ExecutionObservationPolicyV0,
    ExecutionObservationReceiptV0,
    ExecutionObservationRecordV0,
    evaluate_execution_observation,
)
from .semantic_grounded_discovery_v0 import (
    ExecutionGroundedDiscoveryCycleV0,
    ExecutionGroundedDiscoveryEvaluationV0,
    evaluate_execution_grounded_discovery_cycle,
)

SYSTEM_API_SCHEMA_V0 = "TEV_SCRIPT_SYSTEM_API_V0"
SYSTEM_API_PROFILE_V0 = "POST_V1_REALIZATION_SYSTEM_V0"
SYSTEM_API_AUTHORITY_V0 = "TEV_SCRIPT_STANDALONE"

_SYSTEM_SURFACES_V0 = {
    "language": (
        "analyze_v1_sources",
        "analyze_v1_paths",
        "analyze_v1_mapping",
        "compile_v1_sources_auto",
        "compile_v1_paths_auto",
        "compile_v1_mapping_auto",
        "compile_v1_sources_to_ir_v2",
        "compile_v1_paths_to_ir_v2",
        "compile_v1_mapping_to_ir_v2",
        "compile_v1_sources_to_ir_v3",
        "compile_v1_paths_to_ir_v3",
        "compile_v1_mapping_to_ir_v3",
    ),
    "ir_v3": (
        "build_ir_v3_lowering_receipt",
        "verify_ir_v3_lowering_receipt",
        "validate_program_ir_v3",
        "run_ir_v3_conformance",
        "ScriptRuntimeV3",
        "RuntimeCheckpointV2",
    ),
    "semantic_calculus": (
        "SemanticFieldV0",
        "rule_field",
        "apply_rule",
        "commit_prepared",
    ),
    "realization": (
        "admit_realization",
        "pareto_front",
        "evaluate_realization_selection",
        "resolve_realization_selection",
        "evaluate_search_coverage",
        "evaluate_realization_planning",
    ),
    "host_realization": (
        "ProgramIRV3MaterializationV1",
        "HostRuntimeMaterializationV1",
        "HostExecutionEvidenceV1",
        "HostExecutionAdmissionV1",
        "CrossHostEquivalenceV1",
    ),
    "execution_governance": (
        "evaluate_execution_request",
        "evaluate_execution_activation",
        "evaluate_execution_observation",
        "evaluate_execution_grounded_discovery_cycle",
    ),
}


def system_api_contract_object_v0() -> dict[str, object]:
    return {
        "schema": SYSTEM_API_SCHEMA_V0,
        "profile": SYSTEM_API_PROFILE_V0,
        "authority": SYSTEM_API_AUTHORITY_V0,
        "language_version": V1_LANGUAGE_VERSION,
        "primitive_families": ["Field", "Transformation"],
        "host_execution_transformation_hash": EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
        "host_interface_hash": PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1,
        "surfaces": {key: list(_SYSTEM_SURFACES_V0[key]) for key in sorted(_SYSTEM_SURFACES_V0)},
        "consumer_requirements": [
            "bind_exact_system_api_contract_hash",
            "bind_exact_distribution_artifact_sha256",
            "treat_tev_script_as_semantic_authority_for_tev_script",
            "do_not_upgrade_proof_required_or_indeterminate_to_pass",
            "do_not_use_backend_identity_as_semantic_identity",
        ],
    }


SYSTEM_API_CONTRACT_HASH_V0 = canonical_hash(system_api_contract_object_v0())

SYSTEM_API_EXPORTS_V0 = tuple(
    sorted(
        {
            "V1_LANGUAGE_VERSION",
            "SYSTEM_API_SCHEMA_V0",
            "SYSTEM_API_PROFILE_V0",
            "SYSTEM_API_AUTHORITY_V0",
            "SYSTEM_API_CONTRACT_HASH_V0",
            "SYSTEM_API_EXPORTS_V0",
            "system_api_contract_object_v0",
            "V1AnalysisBundle",
            "V1AutoCompilationBundle",
            "V1IrV2CompilationBundle",
            "V1IrV3CompilationBundle",
            "LoweringReceiptBundleV2",
            "IrV3ConformanceReceiptBundle",
            "EmittedEventV3",
            "ScriptRuntimeV3",
            "RuntimeCheckpointV2",
            "FactV0",
            "SemanticFieldV0",
            "field_from_mapping",
            "RuleOpV0",
            "rule_field",
            "apply_rule",
            "commit_prepared",
            "ArtifactDescriptorV0",
            "ArtifactManifestV0",
            "EvidenceItemV0",
            "EvidenceRequirementV0",
            "EvidencePolicyV0",
            "evaluate_evidence",
            "ExecutableFormatV0",
            "MachineCapabilityV0",
            "MachineFieldV0",
            "evaluate_machine_compatibility",
            "RegimeContractV0",
            "RegimePreservationClaimV0",
            "TransformationRegimeBindingV0",
            "evaluate_regime_preservation",
            "ResourceBoundV0",
            "ResourceCatalogV0",
            "ResourceCeilingV0",
            "ResourceDimensionV0",
            "ResourceVectorV0",
            "ResourceEstimateClaimV0",
            "RealizationProblemV0",
            "RealizationPolicyV0",
            "RealizationCandidateV0",
            "RealizationAdmissionReceiptV0",
            "admit_realization",
            "pareto_front",
            "RealizationSelectionPolicyV0",
            "RealizationSelectionProblemV0",
            "RealizationSelectionDecisionV0",
            "RealizationSelectionReceiptV0",
            "evaluate_realization_selection",
            "RealizationSelectionResolutionV0",
            "resolve_realization_selection",
            "SearchCoverageClaimV0",
            "SearchCoverageRecordV0",
            "SearchCoveragePolicyV0",
            "SearchCoverageEvaluationV0",
            "RealizationPlanningClaimV0",
            "RealizationPlanningEvaluationV0",
            "evaluate_search_coverage",
            "evaluate_realization_planning",
            "EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1",
            "PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1",
            "ProgramIRV3MaterializationV1",
            "HostRuntimeProfileV1",
            "HostRuntimeMaterializationV1",
            "HostExecutionEvidenceV1",
            "HostExecutionAdmissionV1",
            "CrossHostEquivalenceV1",
            "python_reference_host_profile_v1",
            "javascript_reference_host_profile_v1",
            "csharp_reference_host_profile_v1",
            "browser_wasm_host_profile_v1",
            "wasi_host_profile_v1",
            "known_v1_host_profiles",
            "admitted_ir_v3_host_profiles_v1",
            "ExecutionIntentV0",
            "ExecutionRequestV0",
            "ExecutionRequestRecordV0",
            "ExecutionRequestPolicyV0",
            "ExecutionRequestAdmissionReceiptV0",
            "evaluate_execution_request",
            "ExecutionActivationCandidateV0",
            "ExecutionActivationReceiptV0",
            "evaluate_execution_activation",
            "ExecutionObservationClaimV0",
            "ExecutionObservationRecordV0",
            "ExecutionObservationPolicyV0",
            "ExecutionObservationReceiptV0",
            "evaluate_execution_observation",
            "ExecutionGroundedDiscoveryCycleV0",
            "ExecutionGroundedDiscoveryEvaluationV0",
            "evaluate_execution_grounded_discovery_cycle",
            "analyze_v1_mapping",
            "analyze_v1_paths",
            "analyze_v1_sources",
            "compile_v1_mapping_auto",
            "compile_v1_mapping_to_ir_v2",
            "compile_v1_mapping_to_ir_v3",
            "compile_v1_paths_auto",
            "compile_v1_paths_to_ir_v2",
            "compile_v1_paths_to_ir_v3",
            "compile_v1_sources_auto",
            "compile_v1_sources_to_ir_v2",
            "compile_v1_sources_to_ir_v3",
            "build_ir_v3_lowering_receipt",
            "verify_ir_v3_lowering_receipt",
            "validate_program_ir_v3",
            "run_ir_v3_conformance",
        }
    )
)

__all__ = list(SYSTEM_API_EXPORTS_V0)
