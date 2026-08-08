from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.python_host_v1 import (
    PythonCapabilityContractV1,
    PythonProgramArtifactV1,
    PythonRuntimeHostV1,
    build_python_program_v1,
)


COUNTER = b'''script Counter version "1.0.0";
entity E {
    state count: Int = 0;
    on inc { count = count + 1; }
}
'''

SENSOR = b'''script Sensor version "1.0.0";
capability world.read() -> Int observation;
entity E {
    state value: Int = 0;
    on update { value = world.read(); }
}
'''


class V1PythonProductionHostTests(unittest.TestCase):
    def test_build_for_python_host_is_explicit_ir_v3(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        ir = artifact.ir()
        self.assertEqual(ir["schema"], "TEV_SCRIPT_PROGRAM_IR_V3")
        self.assertEqual(ir["boundary"]["runtime_source_compilation"], False)
        self.assertEqual(ir["boundary"]["automatic_authority_escalation"], False)
        self.assertEqual(artifact.program_id, "Counter")
        self.assertEqual(artifact.required_capabilities, ())

    def test_runtime_invocation_and_exact_checkpoint_restore(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        host = PythonRuntimeHostV1(artifact)

        host.invoke("E", "inc")
        self.assertEqual(host.state("E")["count"], 1)
        checkpoint = host.capture_checkpoint()
        checkpoint_json = host.capture_checkpoint_json()
        self.assertEqual(checkpoint.to_canonical_json(), checkpoint_json)

        host.invoke("E", "inc")
        self.assertEqual(host.state("E")["count"], 2)
        host.restore_checkpoint(checkpoint_json)
        self.assertEqual(host.state("E")["count"], 1)

        host.invoke("E", "inc")
        self.assertEqual(host.state("E")["count"], 2)

    def test_capability_contract_is_explicit_and_preflight_is_least_authority(self) -> None:
        artifact = build_python_program_v1({"sensor.tevs": SENSOR})
        self.assertEqual(
            artifact.required_capabilities,
            (
                PythonCapabilityContractV1(
                    capability_id="world.read",
                    parameters=(),
                    return_type="Int",
                    kind="observation",
                ),
            ),
        )

        with self.assertRaises(TevScriptError) as missing:
            PythonRuntimeHostV1(artifact)
        self.assertEqual(missing.exception.diagnostic.code, "TEVS_PYTHON_V1_CAPABILITY_MISSING")

        host = PythonRuntimeHostV1(artifact, {"world.read": lambda: 7})
        host.invoke("E", "update")
        self.assertEqual(host.state("E")["value"], 7)

    def test_unused_and_non_callable_bindings_fail_closed(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        with self.assertRaises(TevScriptError) as unused:
            PythonRuntimeHostV1(artifact, {"world.read": lambda: 1})
        self.assertEqual(unused.exception.diagnostic.code, "TEVS_PYTHON_V1_CAPABILITY_UNUSED")

        sensor = build_python_program_v1({"sensor.tevs": SENSOR})
        with self.assertRaises(TevScriptError) as non_callable:
            PythonRuntimeHostV1(sensor, {"world.read": 7})  # type: ignore[dict-item]
        self.assertEqual(
            non_callable.exception.diagnostic.code,
            "TEVS_PYTHON_V1_CAPABILITY_BINDING_CALLABLE",
        )

    def test_capability_cannot_reenter_same_runtime_host(self) -> None:
        artifact = build_python_program_v1({"sensor.tevs": SENSOR})
        holder: dict[str, PythonRuntimeHostV1] = {}

        def reentrant_read() -> int:
            holder["host"].state("E")
            return 7

        host = PythonRuntimeHostV1(artifact, {"world.read": reentrant_read})
        holder["host"] = host

        with self.assertRaises(TevScriptError) as busy:
            host.invoke("E", "update")
        self.assertEqual(busy.exception.diagnostic.code, "TEVS_PYTHON_V1_HOST_BUSY")
        self.assertEqual(host.state("E")["value"], 0)

    def test_artifact_parser_accepts_only_canonical_document_or_artifact_lf(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        bare = PythonProgramArtifactV1.parse(artifact.canonical_ir_json)
        stored = PythonProgramArtifactV1.parse(artifact.canonical_ir_json + "\n")
        self.assertEqual(bare.ir_semantic_hash, artifact.ir_semantic_hash)
        self.assertEqual(stored.ir_semantic_hash, artifact.ir_semantic_hash)

        with self.assertRaises(TevScriptError) as leading_space:
            PythonProgramArtifactV1.parse(" " + artifact.canonical_ir_json)
        self.assertEqual(
            leading_space.exception.diagnostic.code,
            "TEVS_PYTHON_V1_ARTIFACT_CANONICAL",
        )

        with self.assertRaises(TevScriptError) as extra_lf:
            PythonProgramArtifactV1.parse(artifact.canonical_ir_json + "\n\n")
        self.assertEqual(
            extra_lf.exception.diagnostic.code,
            "TEVS_PYTHON_V1_ARTIFACT_CANONICAL",
        )


if __name__ == "__main__":
    unittest.main()
