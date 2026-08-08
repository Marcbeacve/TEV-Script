from .compiler import (
    IR_SCHEMA,
    LANGUAGE_VERSION,
    CompilationBundle,
    compile_bytes,
    compile_declaration,
    compile_path,
)
from .diagnostics import Diagnostic, SourceSpan, TevScriptError
from .runtime import EmittedEvent, ScriptRuntime
from .conformance import run_conformance
from .values import decode_typed_value, encode_typed_value
from .capability_catalog import load_capability_catalog, parse_capability_catalog

# V1 is intentionally exported through versioned names. The historical V0.2
# public names above remain unchanged until a separately certified stable
# admission decides whether any unversioned aliases should move.
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
from .lowering_receipt_v1 import (
    LoweringReceiptBundleV1,
    build_ir_v2_lowering_receipt,
    verify_ir_v2_lowering_receipt,
)
from .lowering_receipt_v2 import (
    LoweringReceiptBundleV2,
    build_ir_v3_lowering_receipt,
    verify_ir_v3_lowering_receipt,
)
from .ir_v3_values import (
    RecordValueV3,
    TypeDescriptorV3,
    TypeTableV3,
    VariantValueV3,
    build_type_table_v3,
    decode_v3_value,
    encode_v3_value,
)
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_conformance import (
    IrV3ConformanceReceiptBundle,
    run_ir_v3_conformance,
)
from .runtime_v3 import EmittedEventV3, ScriptRuntimeV3
from .runtime_checkpoint_v2 import RuntimeCheckpointV2

__all__ = [
    # Certified V0.2 surface.
    "CompilationBundle",
    "Diagnostic",
    "EmittedEvent",
    "IR_SCHEMA",
    "LANGUAGE_VERSION",
    "ScriptRuntime",
    "SourceSpan",
    "TevScriptError",
    "compile_bytes",
    "compile_declaration",
    "compile_path",
    "decode_typed_value",
    "encode_typed_value",
    "run_conformance",
    "load_capability_catalog",
    "parse_capability_catalog",
    # Additive V1 compiler surface.
    "V1AnalysisBundle",
    "V1AutoCompilationBundle",
    "V1IrV2CompilationBundle",
    "V1IrV3CompilationBundle",
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
    # Lowering evidence.
    "LoweringReceiptBundleV1",
    "LoweringReceiptBundleV2",
    "build_ir_v2_lowering_receipt",
    "build_ir_v3_lowering_receipt",
    "verify_ir_v2_lowering_receipt",
    "verify_ir_v3_lowering_receipt",
    # IR V3 value/validator/runtime surface.
    "RecordValueV3",
    "TypeDescriptorV3",
    "TypeTableV3",
    "VariantValueV3",
    "build_type_table_v3",
    "decode_v3_value",
    "encode_v3_value",
    "validate_program_ir_v3",
    "IrV3ConformanceReceiptBundle",
    "run_ir_v3_conformance",
    "EmittedEventV3",
    "RuntimeCheckpointV2",
    "ScriptRuntimeV3",
]
