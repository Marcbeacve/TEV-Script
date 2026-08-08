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
    # Additive V1 candidate surface.
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
    "EmittedEventV3",
    "RuntimeCheckpointV2",
    "ScriptRuntimeV3",
]
