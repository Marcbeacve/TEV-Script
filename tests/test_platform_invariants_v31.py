from __future__ import annotations

from dataclasses import asdict
import copy

import pytest

from tev_script.canonical import canonical_json
from tev_script.descriptor_v31 import v31_descriptor
from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v5_total import (
    total_core_program_to_mapping,
    validate_total_core_program,
)
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
from tev_script.source_total_core_v31 import compile_total_core_v31

AUTHORITY = "a" * 64

CYCLE_SOURCE = f'''
process PlatformInvariantCycle version "3.1.0";
authority {AUTHORITY};
quantum_steps 3;
field actual = [];
label Loop = jump Loop;
entry Loop;
'''

EFFECT_SOURCE = '''
script Effects version "2.0.0";
state count:Int=0;
capability observation sensor.read(Int)->Int;
action tick() {
    observe sample=sensor.read(count);
    set count=sample;
}
entry main=tick();
'''

EFFECT_PROCESS = f'''
process PlatformInvariantEffects version "3.1.0";
authority {AUTHORITY};
quantum_steps 4;
unit Effects profile effects;
field actual = [];
label Start = invoke_v4 Effects result tev.total.result End;
label End = halt;
entry Start;
'''


def _cycle_program():
    return compile_total_core_v31(CYCLE_SOURCE, unit_sources={})


def test_total_core_determinism_same_input_same_canonical_result() -> None:
    program = _cycle_program()
    checkpoint = initial_total_core_checkpoint(program)
    left = run_total_core_quantum(program, checkpoint)
    right = run_total_core_quantum(program, checkpoint)
    assert canonical_json(asdict(left)) == canonical_json(asdict(right))


def test_total_core_capability_non_escalation_requires_external_effect_input() -> None:
    assert v31_descriptor()["physical_effect_commit_inside_runtime"] is False
    with pytest.raises(TevScriptError) as captured:
        compile_total_core_v31(
            EFFECT_PROCESS,
            unit_sources={"Effects": EFFECT_SOURCE},
        )
    assert captured.value.diagnostic.code == "TEVS_V31_SOURCE_EFFECT_INPUT_SET"


def test_total_core_bounded_execution_suspends_exactly_at_quantum_limit() -> None:
    program = _cycle_program()
    result = run_total_core_quantum(program, initial_total_core_checkpoint(program))
    assert result.status == "SUSPENDED"
    assert result.steps_used == 3
    assert result.pc == 0


def test_total_core_canonical_identity_rejects_program_hash_tamper() -> None:
    program = _cycle_program()
    raw = copy.deepcopy(total_core_program_to_mapping(program))
    raw["program_hash"] = "0" * 64
    with pytest.raises(TevScriptError):
        validate_total_core_program(raw)


def test_total_core_checkpoint_replay_is_canonically_equivalent() -> None:
    program = _cycle_program()
    first = run_total_core_quantum(program, initial_total_core_checkpoint(program))
    replay_a = run_total_core_quantum(program, first.next_checkpoint)
    replay_b = run_total_core_quantum(program, first.next_checkpoint)
    assert canonical_json(asdict(replay_a)) == canonical_json(asdict(replay_b))
    assert (
        replay_a.continuation.previous_continuation_hash
        == first.continuation.continuation_hash
    )
