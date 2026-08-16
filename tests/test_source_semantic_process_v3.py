from __future__ import annotations
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.runtime_v5_semantic import run_semantic_quantum
from tev_script.source_semantic_process_v3 import (
    compile_semantic_process_v3,
    parse_semantic_process_v3,
)
from tev_script.program_ir_v5_semantic import initial_process_checkpoint

SOURCE_A = r'''
# native MAX source
process Door version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["closed"];
fact opened = door.state ["open"];
field actual = [closed];
transform open effects 1111111111111111111111111111111111111111111111111111111111111111 resources 2222222222222222222222222222222222222222222222222222222222222222 remove [closed] add [opened];
label start = branch_fact closed do_open done;
label do_open = apply open done;
label done = halt;
entry start;
'''

SOURCE_B = r'''
process   Door   version "3.0.0";
quantum_steps 4;
authority 3333333333333333333333333333333333333333333333333333333333333333;
# declaration order intentionally changed
fact opened = door.state ["open"];
fact closed = door.state ["closed"];
field actual=[closed];
transform open effects 1111111111111111111111111111111111111111111111111111111111111111 resources 2222222222222222222222222222222222222222222222222222222222222222 remove [closed] add [opened];
label done = halt;
label do_open = apply open done;
label start = branch_fact closed do_open done;
entry start;
'''


class SemanticProcessV3SourceTests(unittest.TestCase):
    def test_semantic_hash_erases_whitespace_comments_and_decl_order(self) -> None:
        left = parse_semantic_process_v3(SOURCE_A)
        right = parse_semantic_process_v3(SOURCE_B)
        self.assertEqual(left.source_semantic_hash, right.source_semantic_hash)
        self.assertEqual(left.program_id, "Door")

    def test_compile_and_run_to_halt(self) -> None:
        program = compile_semantic_process_v3(SOURCE_A)
        result = run_semantic_quantum(program, initial_process_checkpoint(program))
        self.assertEqual(result.status, "HALTED")
        self.assertEqual({f.arguments[0] for f in result.field.facts}, {"open"})

    def test_cyclic_source_is_admitted_but_quantum_is_bounded(self) -> None:
        source = r'''
process Cycle version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 3;
fact alive = proc.state ["alive"];
field process = [alive];
label loop = jump loop;
entry loop;
'''
        program = compile_semantic_process_v3(source)
        result = run_semantic_quantum(program, initial_process_checkpoint(program))
        self.assertEqual(result.status, "SUSPENDED")
        self.assertEqual(result.steps_used, 3)

    def test_unknown_reference_and_duplicate_name_fail_closed(self) -> None:
        with self.assertRaises(TevScriptError):
            compile_semantic_process_v3(SOURCE_A.replace("apply open done", "apply missing done"))
        with self.assertRaises(TevScriptError):
            compile_semantic_process_v3(SOURCE_A.replace('fact opened = door.state ["open"];', 'fact closed = door.state ["open"];'))

    def test_version_quantum_and_json_fail_closed(self) -> None:
        with self.assertRaises(TevScriptError):
            compile_semantic_process_v3(SOURCE_A.replace('version "3.0.0"', 'version "2.0.0"'))
        with self.assertRaises(TevScriptError):
            compile_semantic_process_v3(SOURCE_A.replace("quantum_steps 4", "quantum_steps 0"))
        with self.assertRaises(TevScriptError):
            compile_semantic_process_v3(SOURCE_A.replace('["closed"]', '[broken]'))


if __name__ == "__main__":
    unittest.main()
