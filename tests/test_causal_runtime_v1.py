from __future__ import annotations

import unittest

from tev_script.causal_analysis_v1 import find_reaction_footprint
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    CapabilityLawV1,
    ProtocolEdgeV1,
    ProtocolViewV1,
    ReactionContractV1,
    ResourceAccessV1,
    ResourceLawV1,
)
from tev_script.causal_refinement_v1 import contract_from_footprint
from tev_script.causal_runtime_v1 import commit_prepared_reaction, prepare_reaction
from tev_script.diagnostics import TevScriptError
from tev_script.pipeline_v1 import compile_v1_mapping_to_ir_v3
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2
from tev_script.runtime_v3 import ScriptRuntimeV3


def compiled(source: bytes):
    return compile_v1_mapping_to_ir_v3({"P.tevs": source}).target.ir


class TxProvider:
    def __init__(self, *, fail_prepare=False, fail_commit=False):
        self.fail_prepare = fail_prepare
        self.fail_commit = fail_commit
        self.prepared = []
        self.committed = []
        self.aborted = []

    def prepare(self, *args):
        if self.fail_prepare:
            raise RuntimeError("PREPARE_FAIL")
        token = tuple(args)
        self.prepared.append(token)
        return token

    def commit(self, token):
        if self.fail_commit:
            raise RuntimeError("COMMIT_FAIL")
        self.committed.append(token)

    def abort(self, token):
        self.aborted.append(token)


class CausalRuntimeTests(unittest.TestCase):
    def test_prepared_reaction_is_repeatable_and_observation_sensitive(self) -> None:
        ir = compiled(b'''script P version "1.0.0";
capability sensor.read() -> Int observation;
capability motor.set(Int) -> Unit effect;
entity E { state x: Int = 0; on go { x = sensor.read(); call motor.set(x); } }
''')
        laws = CapabilityLawCatalogV1(
            "robot", True,
            resources=(ResourceLawV1("sensor"), ResourceLawV1("drive")),
            capabilities=(
                CapabilityLawV1("sensor.read", "observation", (ResourceAccessV1("sensor", "read"),), observation_semantics="stable"),
                CapabilityLawV1("motor.set", "effect", (ResourceAccessV1("drive", "write"),), effect_protocol="immediate"),
            ),
        )
        def prepare_with(value):
            runtime = ScriptRuntimeV3(ir, {"sensor.read": lambda: value, "motor.set": lambda x: None})
            fp = find_reaction_footprint(ir, "E", "go")
            contract = contract_from_footprint("C", fp, laws)
            return prepare_reaction(runtime, "E", "go", contract=contract, laws=laws).prepared
        one = prepare_with(7)
        two = prepare_with(7)
        changed = prepare_with(8)
        self.assertEqual(one.prepared_reaction_hash, two.prepared_reaction_hash)
        self.assertNotEqual(one.prepared_reaction_hash, changed.prepared_reaction_hash)
        self.assertEqual(one.effect_intents[0]["capability_id"], "motor.set")

    def test_nontransactional_effect_failure_never_publishes_state(self) -> None:
        ir = compiled(b'''script P version "1.0.0";
capability sink.write(Int) -> Unit effect;
entity E { state x: Int = 0; on go { x = 1; call sink.write(x); } }
''')
        laws = CapabilityLawCatalogV1(
            "host", True,
            resources=(ResourceLawV1("sink"),),
            capabilities=(CapabilityLawV1("sink.write", "effect", (ResourceAccessV1("sink", "write"),), effect_protocol="immediate"),),
        )
        runtime = ScriptRuntimeV3(ir, {"sink.write": lambda value: None})
        contract = contract_from_footprint("C", find_reaction_footprint(ir, "E", "go"), laws)
        bundle = prepare_reaction(runtime, "E", "go", contract=contract, laws=laws)
        def fail(value):
            raise RuntimeError("HOST_FAIL")
        result = commit_prepared_reaction(runtime, bundle, contract=contract, laws=laws, effect_bindings={"sink.write": fail})
        self.assertEqual(result.status, "EXTERNAL_PARTIAL")
        self.assertFalse(result.state_committed)
        self.assertEqual(runtime.state("E")["x"], 0)

    def test_transaction_prepare_failure_aborts_and_preserves_state(self) -> None:
        ir = compiled(b'''script P version "1.0.0";
capability debit(Int) -> Unit effect;
capability credit(Int) -> Unit effect;
entity E { state balance: Int = 10; on transfer { balance = balance - 3; call debit(3); call credit(3); } }
''')
        laws = CapabilityLawCatalogV1(
            "ledger", True,
            resources=(ResourceLawV1("ledger"),),
            capabilities=(
                CapabilityLawV1("debit", "effect", (ResourceAccessV1("ledger", "write"),), effect_protocol="prepare_commit_abort", commit_total_after_prepare=True),
                CapabilityLawV1("credit", "effect", (ResourceAccessV1("ledger", "write"),), effect_protocol="prepare_commit_abort", commit_total_after_prepare=True),
            ),
        )
        runtime = ScriptRuntimeV3(ir)
        contract = contract_from_footprint("Transfer", find_reaction_footprint(ir, "E", "transfer"), laws, required_atomicity="transactional")
        bundle = prepare_reaction(runtime, "E", "transfer", contract=contract, laws=laws)
        debit = TxProvider()
        credit = TxProvider(fail_prepare=True)
        result = commit_prepared_reaction(runtime, bundle, contract=contract, laws=laws, effect_bindings={"debit": debit, "credit": credit})
        self.assertEqual(result.status, "ABORTED")
        self.assertEqual(runtime.state("E")["balance"], 10)
        self.assertEqual(len(debit.aborted), 1)
        self.assertEqual(debit.committed, [])

    def test_transaction_success_commits_effects_then_state(self) -> None:
        ir = compiled(b'''script P version "1.0.0";
capability debit(Int) -> Unit effect;
capability credit(Int) -> Unit effect;
entity E { state balance: Int = 10; on transfer { balance = balance - 3; call debit(3); call credit(3); } }
''')
        laws = CapabilityLawCatalogV1(
            "ledger", True,
            resources=(ResourceLawV1("ledger"),),
            capabilities=(
                CapabilityLawV1("debit", "effect", (ResourceAccessV1("ledger", "write"),), effect_protocol="prepare_commit_abort", commit_total_after_prepare=True),
                CapabilityLawV1("credit", "effect", (ResourceAccessV1("ledger", "write"),), effect_protocol="prepare_commit_abort", commit_total_after_prepare=True),
            ),
        )
        runtime = ScriptRuntimeV3(ir)
        contract = contract_from_footprint("Transfer", find_reaction_footprint(ir, "E", "transfer"), laws, required_atomicity="transactional")
        bundle = prepare_reaction(runtime, "E", "transfer", contract=contract, laws=laws)
        debit, credit = TxProvider(), TxProvider()
        result = commit_prepared_reaction(runtime, bundle, contract=contract, laws=laws, effect_bindings={"debit": debit, "credit": credit})
        self.assertEqual(result.status, "COMMITTED")
        self.assertEqual(runtime.state("E")["balance"], 7)
        self.assertEqual(len(debit.committed), 1)
        self.assertEqual(len(credit.committed), 1)

    def test_event_budget_failure_in_shadow_does_not_mutate_original(self) -> None:
        ir = compiled(b'''script P version "1.0.0"; entity E { state x: Int = 0; on tick { x = x + 1; emit tick(); } }''')
        runtime = ScriptRuntimeV3(ir)
        laws = CapabilityLawCatalogV1("none", True)
        contract = contract_from_footprint("Cycle", find_reaction_footprint(ir, "E", "tick"), laws)
        with self.assertRaises(TevScriptError) as caught:
            prepare_reaction(runtime, "E", "tick", contract=contract, laws=laws)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_IR_V3_EVENT_BUDGET")
        self.assertEqual(runtime.state("E")["x"], 0)

    def test_protocol_typestate_is_contract_view_and_uses_canonical_checkpoint(self) -> None:
        ir = compiled(b'''script DoorProtocol version "1.0.0";
enum Mode { Closed; Open; }
entity Door {
 state mode: Mode = Mode::Closed;
 on open { mode = Mode::Open; }
 on close { mode = Mode::Closed; }
}
''')
        runtime = ScriptRuntimeV3(ir)
        laws = CapabilityLawCatalogV1("none", True)
        fp = find_reaction_footprint(ir, "Door", "open")
        before = RuntimeCheckpointV2.capture(runtime).to_object()["entities"][0]["state"]["mode"]
        probe = ScriptRuntimeV3(ir)
        probe.invoke("Door", "open")
        after = RuntimeCheckpointV2.capture(probe).to_object()["entities"][0]["state"]["mode"]
        contract = ReactionContractV1(
            "DoorOpen", "Door", "open",
            allowed_state_writes=("mode",),
            maximum_reachable_events=fp.reachable_handler_count,
            maximum_instruction_ceiling=fp.instruction_ceiling,
            protocol=ProtocolViewV1("mode", (ProtocolEdgeV1("open", before, after),)),
        )
        bundle = prepare_reaction(runtime, "Door", "open", contract=contract, laws=laws)
        result = commit_prepared_reaction(runtime, bundle, contract=contract, laws=laws)
        self.assertEqual(result.status, "COMMITTED")
        self.assertEqual(RuntimeCheckpointV2.capture(runtime).to_object()["entities"][0]["state"]["mode"], after)

    def test_invalid_protocol_edge_is_rejected_before_commit(self) -> None:
        ir = compiled(b'''script DoorProtocol version "1.0.0";
enum Mode { Closed; Open; }
entity Door { state mode: Mode = Mode::Closed; on close { mode = Mode::Closed; } }
''')
        runtime = ScriptRuntimeV3(ir)
        laws = CapabilityLawCatalogV1("none", True)
        fp = find_reaction_footprint(ir, "Door", "close")
        current = RuntimeCheckpointV2.capture(runtime).to_object()["entities"][0]["state"]["mode"]
        impossible = {"type": current["type"], "value": {"$enum": {"type": current["type"], "variant": "Open"}}}
        contract = ReactionContractV1(
            "CloseOnlyFromOpen", "Door", "close",
            allowed_state_writes=("mode",),
            maximum_reachable_events=1,
            maximum_instruction_ceiling=fp.instruction_ceiling,
            protocol=ProtocolViewV1("mode", (ProtocolEdgeV1("close", impossible, current),)),
        )
        with self.assertRaises(TevScriptError) as caught:
            prepare_reaction(runtime, "Door", "close", contract=contract, laws=laws)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_CAUSAL_REFINEMENT_REJECT")
        self.assertEqual(RuntimeCheckpointV2.capture(runtime).to_object()["entities"][0]["state"]["mode"], current)

    def test_effect_observation_hazard_rejected_before_observation_execution(self) -> None:
        ir = compiled(b'''script P version "1.0.0";
capability world.set(Int) -> Unit effect;
capability world.read() -> Int observation;
entity E { state seen: Int = 0; on go { call world.set(1); seen = world.read(); } }
''')
        laws = CapabilityLawCatalogV1(
            "world", True,
            resources=(ResourceLawV1("world"),),
            capabilities=(
                CapabilityLawV1("world.set", "effect", (ResourceAccessV1("world", "write"),), effect_protocol="immediate"),
                CapabilityLawV1("world.read", "observation", (ResourceAccessV1("world", "read"),), observation_semantics="stable"),
            ),
        )
        calls = []
        runtime = ScriptRuntimeV3(ir, {"world.set": lambda value: None, "world.read": lambda: calls.append("read") or 1})
        contract = contract_from_footprint("World", find_reaction_footprint(ir, "E", "go"), laws)
        with self.assertRaises(TevScriptError) as caught:
            prepare_reaction(runtime, "E", "go", contract=contract, laws=laws)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_CAUSAL_NOT_PREPARABLE")
        self.assertEqual(calls, [])


    def test_durable_transactional_classification_and_commit_law_violation(self) -> None:
        ir = compiled(b'''script P version "1.0.0";
capability ledger.write(Int) -> Unit effect;
entity E { state x: Int = 0; on go { x = 1; call ledger.write(x); } }
''')
        laws = CapabilityLawCatalogV1(
            "durable", True,
            resources=(ResourceLawV1("ledger"),),
            capabilities=(
                CapabilityLawV1(
                    "ledger.write", "effect",
                    (ResourceAccessV1("ledger", "write"),),
                    effect_protocol="prepare_commit_abort",
                    commit_total_after_prepare=True,
                    durable_recovery=True,
                ),
            ),
        )
        runtime = ScriptRuntimeV3(ir)
        contract = contract_from_footprint(
            "Durable", find_reaction_footprint(ir, "E", "go"), laws,
            required_atomicity="durable_transactional",
        )
        bundle = prepare_reaction(runtime, "E", "go", contract=contract, laws=laws)
        self.assertEqual(bundle.prepared.atomicity, "durable_transactional")
        provider = TxProvider(fail_commit=True)
        result = commit_prepared_reaction(
            runtime, bundle, contract=contract, laws=laws,
            effect_bindings={"ledger.write": provider},
        )
        self.assertEqual(result.status, "LAW_VIOLATION")
        self.assertFalse(result.state_committed)
        self.assertTrue(result.external_partial)
        self.assertEqual(runtime.state("E")["x"], 0)

    def test_prepared_mapping_mutation_is_detected_before_commit(self) -> None:
        ir = compiled(b'''script P version "1.0.0"; entity E { state x: Int = 0; on go { x = 1; } }''')
        runtime = ScriptRuntimeV3(ir)
        laws = CapabilityLawCatalogV1("none", True)
        contract = contract_from_footprint("C", find_reaction_footprint(ir, "E", "go"), laws)
        bundle = prepare_reaction(runtime, "E", "go", contract=contract, laws=laws)
        bundle.prepared.before_checkpoint["program_id"] = "Tampered"
        with self.assertRaises(TevScriptError) as caught:
            commit_prepared_reaction(runtime, bundle, contract=contract, laws=laws)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_CAUSAL_PREPARED_TAMPER")
        self.assertEqual(runtime.state("E")["x"], 0)

    def test_prepared_serialization_root_matches_closed_schema_surface(self) -> None:
        import json
        from pathlib import Path
        ir = compiled(b'''script P version "1.0.0"; entity E { state x: Int = 0; on go { x = 1; } }''')
        runtime = ScriptRuntimeV3(ir)
        laws = CapabilityLawCatalogV1("none", True)
        contract = contract_from_footprint("C", find_reaction_footprint(ir, "E", "go"), laws)
        prepared = prepare_reaction(runtime, "E", "go", contract=contract, laws=laws).prepared.to_object()
        schema = json.loads(Path("schemas/tev_script_prepared_reaction_v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(prepared), set(schema["required"]))

    def test_stale_prepared_reaction_cannot_commit_after_state_change(self) -> None:
        ir = compiled(b'''script P version "1.0.0"; entity E { state x: Int = 0; on go { x = x + 1; } }''')
        runtime = ScriptRuntimeV3(ir)
        laws = CapabilityLawCatalogV1("none", True)
        contract = contract_from_footprint("C", find_reaction_footprint(ir, "E", "go"), laws)
        bundle = prepare_reaction(runtime, "E", "go", contract=contract, laws=laws)
        runtime.invoke("E", "go")
        with self.assertRaises(TevScriptError) as caught:
            commit_prepared_reaction(runtime, bundle, contract=contract, laws=laws)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_CAUSAL_STALE_STATE")


if __name__ == "__main__":
    unittest.main()
