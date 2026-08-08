from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .linked_program_v1 import LinkedProgramBundleV1, emit_linked_program_v1
from .linker_v1 import LinkPlanV1, SourceInputV1, link_v1_sources
from .lowering_boundary_v1 import LoweringBoundaryV1, analyze_ir_v2_lowering_boundary
from .lowering_ir_v2_linked_v1 import (
    LinkedV1IrV2Bundle,
    lower_linked_program_v1_to_ir_v2,
)
from .lowering_ir_v3_linked_v1 import (
    LinkedV1IrV3Bundle,
    lower_linked_program_v1_to_ir_v3,
)
from .static_semantics_v1 import StaticSemanticsV1, analyze_v1_static_semantics


@dataclass(frozen=True, slots=True)
class V1AnalysisBundle:
    plan: LinkPlanV1
    semantics: StaticSemanticsV1
    linked_program: LinkedProgramBundleV1
    ir_v2_boundary: LoweringBoundaryV1


@dataclass(frozen=True, slots=True)
class V1IrV2CompilationBundle:
    analysis: V1AnalysisBundle
    target: LinkedV1IrV2Bundle


@dataclass(frozen=True, slots=True)
class V1IrV3CompilationBundle:
    analysis: V1AnalysisBundle
    target: LinkedV1IrV3Bundle


@dataclass(frozen=True, slots=True)
class V1AutoCompilationBundle:
    analysis: V1AnalysisBundle
    target_ir: str
    target: LinkedV1IrV2Bundle | LinkedV1IrV3Bundle


def analyze_v1_sources(
    sources: Iterable[SourceInputV1],
) -> V1AnalysisBundle:
    plan = link_v1_sources(tuple(sources))
    semantics = analyze_v1_static_semantics(plan)
    linked_program = emit_linked_program_v1(semantics)
    boundary = analyze_ir_v2_lowering_boundary(semantics)
    return V1AnalysisBundle(
        plan=plan,
        semantics=semantics,
        linked_program=linked_program,
        ir_v2_boundary=boundary,
    )


def analyze_v1_mapping(
    sources: Mapping[str, bytes],
) -> V1AnalysisBundle:
    return analyze_v1_sources(
        SourceInputV1(path, data)
        for path, data in sources.items()
    )


def analyze_v1_paths(
    paths: Iterable[str | Path],
) -> V1AnalysisBundle:
    inputs = []
    for path in paths:
        selected = Path(path)
        inputs.append(
            SourceInputV1(
                selected.as_posix(),
                selected.read_bytes(),
            )
        )
    return analyze_v1_sources(inputs)


def compile_v1_sources_to_ir_v2(
    sources: Iterable[SourceInputV1],
) -> V1IrV2CompilationBundle:
    analysis = analyze_v1_sources(sources)
    target = lower_linked_program_v1_to_ir_v2(
        analysis.linked_program
    )
    return V1IrV2CompilationBundle(
        analysis=analysis,
        target=target,
    )


def compile_v1_mapping_to_ir_v2(
    sources: Mapping[str, bytes],
) -> V1IrV2CompilationBundle:
    return compile_v1_sources_to_ir_v2(
        SourceInputV1(path, data)
        for path, data in sources.items()
    )


def compile_v1_paths_to_ir_v2(
    paths: Iterable[str | Path],
) -> V1IrV2CompilationBundle:
    inputs = []
    for path in paths:
        selected = Path(path)
        inputs.append(
            SourceInputV1(
                selected.as_posix(),
                selected.read_bytes(),
            )
        )
    return compile_v1_sources_to_ir_v2(inputs)


def compile_v1_sources_to_ir_v3(
    sources: Iterable[SourceInputV1],
) -> V1IrV3CompilationBundle:
    analysis = analyze_v1_sources(sources)
    target = lower_linked_program_v1_to_ir_v3(
        analysis.linked_program
    )
    return V1IrV3CompilationBundle(
        analysis=analysis,
        target=target,
    )


def compile_v1_mapping_to_ir_v3(
    sources: Mapping[str, bytes],
) -> V1IrV3CompilationBundle:
    return compile_v1_sources_to_ir_v3(
        SourceInputV1(path, data)
        for path, data in sources.items()
    )


def compile_v1_paths_to_ir_v3(
    paths: Iterable[str | Path],
) -> V1IrV3CompilationBundle:
    inputs = []
    for path in paths:
        selected = Path(path)
        inputs.append(
            SourceInputV1(
                selected.as_posix(),
                selected.read_bytes(),
            )
        )
    return compile_v1_sources_to_ir_v3(inputs)


def compile_v1_sources_auto(
    sources: Iterable[SourceInputV1],
) -> V1AutoCompilationBundle:
    analysis = analyze_v1_sources(sources)
    if analysis.ir_v2_boundary.lowerable:
        target_ir = "TEV_SCRIPT_PROGRAM_IR_V2"
        target: LinkedV1IrV2Bundle | LinkedV1IrV3Bundle = (
            lower_linked_program_v1_to_ir_v2(analysis.linked_program)
        )
    else:
        target_ir = "TEV_SCRIPT_PROGRAM_IR_V3"
        target = lower_linked_program_v1_to_ir_v3(analysis.linked_program)
    return V1AutoCompilationBundle(
        analysis=analysis,
        target_ir=target_ir,
        target=target,
    )


def compile_v1_mapping_auto(
    sources: Mapping[str, bytes],
) -> V1AutoCompilationBundle:
    return compile_v1_sources_auto(
        SourceInputV1(path, data)
        for path, data in sources.items()
    )


def compile_v1_paths_auto(
    paths: Iterable[str | Path],
) -> V1AutoCompilationBundle:
    inputs = []
    for path in paths:
        selected = Path(path)
        inputs.append(
            SourceInputV1(
                selected.as_posix(),
                selected.read_bytes(),
            )
        )
    return compile_v1_sources_auto(inputs)
