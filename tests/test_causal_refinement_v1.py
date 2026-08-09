from __future__ import annotations

import unittest

from tev_script.causal_analysis_v1 import find_reaction_footprint
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    CapabilityLawV1,
    ProofObligationRefV1,
    ReactionContractV1,
    ResourceAccessV1,
    ResourceLawV1,
)
from tev_script.causal_refinement_v1 import contract_from_footprint, verify_structural_refinement
from tev_script.pipeline_v1 import compile_v1_mapping_to_ir_v3


class CausalRefinementTests(unittest.TestCase):
    SOURCE = b'''script P version "1.0.0";
capability sensor.read() -> Int observation;
capability door.open() -> Unit effect;
entity E {
 state seen: Int = 0;
 on sense { seen = sensor.read(); }
 on bad { seen = sensor.read(); call door.open(); }
}
'''

    def setUp(self) -> None:
        self.ir = compile_v1_mapping_to_ir_v3({"P.tevs": self.SOURCE}).target.ir
        self.catalog = CapabilityLawCatalogV1(
            "deployment", True,
            resources=(ResourceLawV1("sensor"), ResourceLawV1("door")),
            capabilities=(
                CapabilityLawV1("sensor.read", "observation", (ResourceAccessV1("sensor", "read"),), observation_semantics="stable"),
                CapabilityLawV1("door.open", "effect", (ResourceAccessV1("door", "write"),), effect_protocol="immediate"),
            ),
        )

    def test_contract_can_precede_implementation_and_accept_narrow_candidate(self) -> None:
        footprint = find_reaction_footprint(self.ir, "E", "sense")
        contract = ReactionContractV1(
            "SenseContract", "E", "sense",
            allowed_state_reads=(),
            allowed_state_writes=("seen",),
            allowed_observations=("sensor.read",),
            allowed_resources=("sensor",),
            maximum_reachable_events=1,
            maximum_instruction_ceiling=1048576,
        )
        receipt = verify_structural_refinement(contract, footprint, self.catalog)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.to_object()["receipt_hash"], receipt.receipt_hash)

    def test_refinement_rejects_effect_authority_escalation(self) -> None:
        footprint = find_reaction_footprint(self.ir, "E", "bad")
        contract = ReactionContractV1(
            "NoDoor", "E", "bad",
            allowed_state_writes=("seen",),
            allowed_observations=("sensor.read",),
            allowed_effects=(),
            allowed_resources=("sensor",),
            maximum_instruction_ceiling=1048576,
        )
        receipt = verify_structural_refinement(contract, footprint, self.catalog)
        self.assertEqual(receipt.status, "REJECT")
        self.assertTrue(any(item["kind"] == "effects" for item in receipt.failures))

    def test_refinement_rejects_resource_ceiling_escalation(self) -> None:
        footprint = find_reaction_footprint(self.ir, "E", "bad")
        contract = ReactionContractV1(
            "NoDoorResource", "E", "bad",
            allowed_state_writes=("seen",),
            allowed_observations=("sensor.read",),
            allowed_effects=("door.open",),
            allowed_resources=("sensor",),
            maximum_instruction_ceiling=1048576,
        )
        receipt = verify_structural_refinement(contract, footprint, self.catalog)
        self.assertEqual(receipt.status, "REJECT")
        self.assertTrue(any(item["kind"] == "resources" for item in receipt.failures))

    def test_proof_obligation_fails_closed_as_proof_required(self) -> None:
        footprint = find_reaction_footprint(self.ir, "E", "sense")
        base = contract_from_footprint("Proofed", footprint, self.catalog)
        contract = ReactionContractV1(
            base.contract_id, base.entity_id, base.trigger_event,
            base.allowed_state_reads, base.allowed_state_writes,
            base.allowed_observations, base.allowed_effects, base.allowed_emitted_events,
            base.allowed_resources, base.maximum_reachable_events,
            base.maximum_instruction_ceiling, base.required_atomicity,
            proof_obligations=(ProofObligationRefV1("Safety", "smt", "1" * 64),),
        )
        receipt = verify_structural_refinement(contract, footprint, self.catalog)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertEqual(receipt.pending_obligations, ("Safety",))


    def test_model_serialization_roots_match_closed_schema_surfaces(self) -> None:
        import json
        from pathlib import Path
        footprint = find_reaction_footprint(self.ir, "E", "sense")
        contract = contract_from_footprint("Schema", footprint, self.catalog)
        receipt = verify_structural_refinement(contract, footprint, self.catalog)
        pairs = (
            (self.catalog.to_object(), "schemas/tev_script_capability_law_catalog_v1.schema.json"),
            (contract.to_object(), "schemas/tev_script_reaction_contract_v1.schema.json"),
            (receipt.to_object(), "schemas/tev_script_refinement_receipt_v1.schema.json"),
        )
        for value, path in pairs:
            schema = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(set(value), set(schema["required"]), path)

    def test_contract_hash_is_order_canonical(self) -> None:
        a = ReactionContractV1(
            "C", "E", "sense",
            allowed_state_writes=("z", "a"),
            allowed_observations=("sensor.read",),
            maximum_instruction_ceiling=999999,
        )
        b = ReactionContractV1(
            "C", "E", "sense",
            allowed_state_writes=("a", "z"),
            allowed_observations=("sensor.read",),
            maximum_instruction_ceiling=999999,
        )
        self.assertEqual(a.contract_hash, b.contract_hash)


if __name__ == "__main__":
    unittest.main()
