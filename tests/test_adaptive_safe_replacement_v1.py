from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import unittest

from tev_script.canonical import canonical_hash
from tev_script.compiler import compile_bytes
from tev_script.conformance import run_conformance
from tev_script.semantic_residual_v0 import parse_residual
from tev_script.semantic_adaptive_replacement_v1 import (
    build_adaptive_replacement_canary_bundle_v1,
    evaluate_adaptive_replacement_canary_v1,
    initial_conformance_state_v1,
    project_adaptive_replacement_conformance_v1,
    residual_from_adaptive_replacement_v1,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


def int_value(value: int) -> dict[str, str]:
    return {"$int": str(value)}


def rat_value(numerator: int, denominator: int = 1) -> dict[str, list[str]]:
    value = Fraction(numerator, denominator)
    return {"$rat": [str(value.numerator), str(value.denominator)]}


class AdaptiveSafeReplacementV1Tests(unittest.TestCase):
    SMOKE = b'''
script Smoke version "0.2.0";
entity A {
    state x: Int = 0;
    on go { x = 1; }
}
'''

    HOT_INCREMENT = b'''
script HotIncrement version "0.2.0";
entity A {
    state x: Int = 0;
    on go { x = x + 1; }
}
'''

    CONSTANT_OBSERVATION = b'''
script Observation version "0.2.0";
entity A {
    state dt: Rat = 0;
    on go { dt = time.delta(); }
}
'''

    TRACE_EFFECT = b'''
script Effect version "0.2.0";
entity A {
    state x: Int = 0;
    on go {
        log "hello";
        x = 1;
    }
}
'''

    def compile(self, source: bytes):
        return compile_bytes("R10.tevs", source).ir

    def invocation(self) -> list[dict[str, object]]:
        return [{"entity_id": "A", "event_id": "go", "arguments": []}]

    def bundle(
        self,
        ir,
        *,
        bindings=None,
        baseline_state=None,
        interleaving="SERIALIZED",
        final_states=None,
        emitted_events=None,
        capability_trace=None,
    ):
        initial, _ = initial_conformance_state_v1(ir)
        return build_adaptive_replacement_canary_bundle_v1(
            candidate_realization_hash=h("candidate"),
            lane_id="lane.r10",
            scenario_id="r10.canary",
            program_semantic_hash=ir["semantic_hash"],
            baseline_state=initial if baseline_state is None else baseline_state,
            interleaving=interleaving,
            capability_bindings={} if bindings is None else bindings,
            invocations=self.invocation(),
            observed_final_states=[] if final_states is None else final_states,
            observed_emitted_events=[] if emitted_events is None else emitted_events,
            observed_capability_trace=[] if capability_trace is None else capability_trace,
        )

    def test_smoke_projects_to_real_conformance_runner_and_passes(self):
        ir = self.compile(self.SMOKE)
        final_states = [
            {
                "entity_id": "A",
                "state": {"x": {"type": "Int", "value": int_value(1)}},
            }
        ]
        bundle = self.bundle(ir, final_states=final_states)
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PASS")
        self.assertIsNotNone(projection.scenario)

        receipt = run_conformance(ir, projection.scenario, initial_state=bundle["baseline_state"])
        self.assertEqual(receipt["schema"], "TEV_SCRIPT_CONFORMANCE_RECEIPT_V2")
        self.assertEqual(receipt["initial_state_hash"], bundle["baseline_state_hash"])
        self.assertEqual(receipt["final_states"], final_states)
        self.assertEqual(receipt["emitted_events"], [])
        self.assertEqual(receipt["capability_trace"], [])

        evaluation = evaluate_adaptive_replacement_canary_v1(ir, bundle)
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(evaluation.runner_receipt_hash, receipt["receipt_hash"])
        self.assertTrue(parse_residual(residual_from_adaptive_replacement_v1(evaluation)).closed)

    def test_constant_observation_projects_and_passes(self):
        ir = self.compile(self.CONSTANT_OBSERVATION)
        bindings = {
            "time.delta": {
                "mode": "constant",
                "value_type": "Rat",
                "value": rat_value(1, 2),
            }
        }
        final_states = [
            {
                "entity_id": "A",
                "state": {"dt": {"type": "Rat", "value": rat_value(1, 2)}},
            }
        ]
        capability_trace = [
            {
                "capability_id": "time.delta",
                "arguments": [],
                "result": rat_value(1, 2),
            }
        ]
        bundle = self.bundle(
            ir,
            bindings=bindings,
            final_states=final_states,
            capability_trace=capability_trace,
        )
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PASS")
        receipt = run_conformance(ir, projection.scenario, initial_state=bundle["baseline_state"])
        self.assertEqual(receipt["capability_trace"], capability_trace)
        self.assertEqual(evaluate_adaptive_replacement_canary_v1(ir, bundle).status, "PASS")

    def test_variable_observation_is_proof_required(self):
        ir = self.compile(self.CONSTANT_OBSERVATION)
        bundle = self.bundle(
            ir,
            bindings={
                "time.delta": {
                    "mode": "variable",
                    "values": [
                        {"type": "Rat", "value": rat_value(1, 2)},
                        {"type": "Rat", "value": rat_value(3, 4)},
                    ],
                }
            },
        )
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PROOF_REQUIRED")
        self.assertIsNone(projection.scenario)
        self.assertIn(
            "replacement.variable_observation_projection_required",
            {item.kind for item in projection.issues},
        )

    def test_trace_effect_projects_and_passes(self):
        ir = self.compile(self.TRACE_EFFECT)
        final_states = [
            {
                "entity_id": "A",
                "state": {"x": {"type": "Int", "value": int_value(1)}},
            }
        ]
        capability_trace = [
            {
                "capability_id": "debug.log",
                "arguments": ["hello"],
                "result": None,
            }
        ]
        bundle = self.bundle(
            ir,
            bindings={"debug.log": {"mode": "trace"}},
            final_states=final_states,
            capability_trace=capability_trace,
        )
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PASS")
        receipt = run_conformance(ir, projection.scenario, initial_state=bundle["baseline_state"])
        self.assertEqual(receipt["capability_trace"], capability_trace)
        self.assertEqual(evaluate_adaptive_replacement_canary_v1(ir, bundle).status, "PASS")

    def test_irrecoverable_interleaving_is_proof_required(self):
        ir = self.compile(self.SMOKE)
        bundle = self.bundle(ir, interleaving="IRRECOVERABLE")
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PROOF_REQUIRED")
        self.assertIn(
            "replacement.interleaving_recovery_required",
            {item.kind for item in projection.issues},
        )

    def test_undeclared_capability_is_rejected(self):
        ir = self.compile(self.SMOKE)
        bundle = self.bundle(
            ir,
            bindings={
                "ghost.read": {
                    "mode": "constant",
                    "value_type": "Int",
                    "value": int_value(1),
                }
            },
        )
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "REJECT")
        self.assertIn(
            "replacement.capability_undeclared",
            {item.kind for item in projection.issues},
        )

    def test_wrong_capability_return_type_is_rejected(self):
        ir = self.compile(self.CONSTANT_OBSERVATION)
        bundle = self.bundle(
            ir,
            bindings={
                "time.delta": {
                    "mode": "constant",
                    "value_type": "Int",
                    "value": int_value(1),
                }
            },
        )
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "REJECT")
        self.assertIn(
            "replacement.capability_return_type_mismatch",
            {item.kind for item in projection.issues},
        )

    def test_hot_baseline_is_restored_explicitly_and_passes(self):
        ir = self.compile(self.HOT_INCREMENT)
        hot_state = [
            {
                "entity_id": "A",
                "state": {"x": {"type": "Int", "value": int_value(9)}},
            }
        ]
        final_states = [
            {
                "entity_id": "A",
                "state": {"x": {"type": "Int", "value": int_value(10)}},
            }
        ]
        bundle = self.bundle(ir, baseline_state=hot_state, final_states=final_states)
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PASS")
        self.assertIsNotNone(projection.scenario)

        receipt = run_conformance(ir, projection.scenario, initial_state=bundle["baseline_state"])
        self.assertEqual(receipt["schema"], "TEV_SCRIPT_CONFORMANCE_RECEIPT_V2")
        self.assertEqual(receipt["initial_state_hash"], bundle["baseline_state_hash"])
        self.assertEqual(receipt["final_states"], final_states)
        self.assertEqual(evaluate_adaptive_replacement_canary_v1(ir, bundle).status, "PASS")

    def test_malformed_hot_baseline_is_rejected_by_runner(self):
        ir = self.compile(self.HOT_INCREMENT)
        invalid_state = [
            {
                "entity_id": "A",
                "state": {"x": {"type": "Rat", "value": rat_value(9)}},
            }
        ]
        bundle = self.bundle(ir, baseline_state=invalid_state)
        evaluation = evaluate_adaptive_replacement_canary_v1(ir, bundle)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn(
            "replacement.conformance_runner_rejected",
            {item.kind for item in evaluation.issues},
        )

    def test_bundle_tamper_is_rejected_before_projection(self):
        ir = self.compile(self.SMOKE)
        bundle = self.bundle(ir)
        tampered = deepcopy(bundle)
        tampered["lane_id"] = "lane.tampered"
        projection = project_adaptive_replacement_conformance_v1(ir, tampered)
        self.assertEqual(projection.status, "REJECT")
        self.assertIsNone(projection.scenario)
        self.assertIn(
            "replacement.bundle_integrity_mismatch",
            {item.kind for item in projection.issues},
        )

    def test_observable_divergence_rejects_replacement(self):
        ir = self.compile(self.SMOKE)
        wrong_final = [
            {
                "entity_id": "A",
                "state": {"x": {"type": "Int", "value": int_value(2)}},
            }
        ]
        bundle = self.bundle(ir, final_states=wrong_final)
        evaluation = evaluate_adaptive_replacement_canary_v1(ir, bundle)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn(
            "replacement.observable_divergence",
            {item.kind for item in evaluation.issues},
        )

    def test_missing_declared_capability_remains_proof_required(self):
        ir = self.compile(self.CONSTANT_OBSERVATION)
        bundle = self.bundle(ir, bindings={})
        projection = project_adaptive_replacement_conformance_v1(ir, bundle)
        self.assertEqual(projection.status, "PROOF_REQUIRED")
        self.assertIn(
            "replacement.capability_binding_missing",
            {item.kind for item in projection.issues},
        )


if __name__ == "__main__":
    unittest.main()
