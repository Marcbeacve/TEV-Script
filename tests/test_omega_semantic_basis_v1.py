from __future__ import annotations
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import (
    field_fact, semantic_field, validate_semantic_field,
    field_transformation, validate_field_transformation,
    apply_field_transformation, validate_apply_receipt, apply_sequence,
)

class OmegaFieldTests(unittest.TestCase):
    def test_field_order_is_nonsemantic_and_hash_stable(self) -> None:
        a = field_fact("world.door", ("closed",))
        b = field_fact("world.count", (2,))
        left = semantic_field((a, b), profile="actual")
        right = semantic_field((b, a), profile="actual")
        self.assertEqual(left, right)
        self.assertEqual(tuple(f.fact_hash for f in left.facts), tuple(sorted((a.fact_hash, b.fact_hash))))

    def test_duplicate_fact_rejected(self) -> None:
        a = field_fact("world.door", ("closed",))
        with self.assertRaises(TevScriptError):
            semantic_field((a, a))

    def test_unstable_relation_rejected(self) -> None:
        with self.assertRaises(TevScriptError):
            field_fact("bad relation", (1,))

    def test_tampered_field_hash_rejected(self) -> None:
        a = field_fact("world.door", ("closed",))
        field = semantic_field((a,))
        wire = {
            "schema": field.schema,
            "profile": field.profile,
            "facts": [{"relation": a.relation, "arguments": list(a.arguments), "fact_hash": a.fact_hash}],
            "field_hash": "0" * 64,
        }
        with self.assertRaises(TevScriptError):
            validate_semantic_field(wire)


class OmegaTransformationTests(unittest.TestCase):
    def _hashes(self):
        return "1" * 64, "2" * 64

    def test_transformation_order_is_canonical(self) -> None:
        a = field_fact("world.a", (1,)); b = field_fact("world.b", (2,))
        effects, resources = self._hashes()
        left = field_transformation(
            transformation_id="door.change", remove_fact_hashes=("f" * 64, "e" * 64),
            add_facts=(a, b), effect_set_hash=effects, resource_vector_hash=resources,
            proof_requirement_hashes=("d" * 64, "c" * 64),
        )
        right = field_transformation(
            transformation_id="door.change", remove_fact_hashes=("e" * 64, "f" * 64),
            add_facts=(b, a), effect_set_hash=effects, resource_vector_hash=resources,
            proof_requirement_hashes=("c" * 64, "d" * 64),
        )
        self.assertEqual(left, right)

    def test_duplicate_remove_rejected(self) -> None:
        effects, resources = self._hashes()
        with self.assertRaises(TevScriptError):
            field_transformation(
                transformation_id="bad", remove_fact_hashes=("a"*64, "a"*64),
                effect_set_hash=effects, resource_vector_hash=resources,
            )

    def test_add_remove_collision_rejected(self) -> None:
        fact = field_fact("world.a", (1,)); effects, resources = self._hashes()
        with self.assertRaises(TevScriptError):
            field_transformation(
                transformation_id="bad", remove_fact_hashes=(fact.fact_hash,), add_facts=(fact,),
                effect_set_hash=effects, resource_vector_hash=resources,
            )

    def test_tampered_transformation_hash_rejected(self) -> None:
        effects, resources = self._hashes()
        tx = field_transformation(transformation_id="ok", effect_set_hash=effects, resource_vector_hash=resources)
        wire = {
            "schema": tx.schema, "transformation_id": tx.transformation_id,
            "required_before_hash": tx.required_before_hash, "result_profile": tx.result_profile,
            "remove_fact_hashes": list(tx.remove_fact_hashes), "add_facts": [],
            "effect_set_hash": tx.effect_set_hash, "resource_vector_hash": tx.resource_vector_hash,
            "proof_requirement_hashes": list(tx.proof_requirement_hashes), "transformation_hash": "0"*64,
        }
        with self.assertRaises(TevScriptError):
            validate_field_transformation(wire)


class OmegaApplyTests(unittest.TestCase):
    EFFECTS = "1" * 64
    RESOURCES = "2" * 64

    def _before(self):
        closed = field_fact("door.state", ("closed",))
        return closed, semantic_field((closed,), profile="actual")

    def test_apply_passes_exact_delta_without_proof_obligations(self) -> None:
        closed, before = self._before(); opened = field_fact("door.state", ("open",))
        tx = field_transformation(
            transformation_id="door.open", required_before_hash=before.field_hash,
            remove_fact_hashes=(closed.fact_hash,), add_facts=(opened,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        after, receipt = apply_field_transformation(before, tx)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(after.facts, (opened,))
        self.assertEqual(receipt.after_field_hash, after.field_hash)
        self.assertEqual(validate_apply_receipt(receipt), receipt)

    def test_transformation_can_change_field_profile_explicitly(self) -> None:
        fact = field_fact("state.value", (1,))
        before = semantic_field((fact,), profile="theory")
        tx = field_transformation(
            transformation_id="realize.profile", result_profile="actual",
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        after, receipt = apply_field_transformation(before, tx)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(after.profile, "actual")
        self.assertEqual(after.facts, before.facts)
        self.assertNotEqual(after.field_hash, before.field_hash)

    def test_unresolved_proof_requirements_are_not_pass(self) -> None:
        closed, before = self._before(); opened = field_fact("door.state", ("open",))
        tx = field_transformation(
            transformation_id="door.open.proved", remove_fact_hashes=(closed.fact_hash,),
            add_facts=(opened,), effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
            proof_requirement_hashes=("a"*64,),
        )
        after, receipt = apply_field_transformation(before, tx)
        self.assertEqual(after.facts, (opened,))
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertNotEqual(receipt.status, "PASS")
        self.assertEqual(receipt.proof_requirement_hashes, ("a"*64,))

    def test_before_pin_mismatch_fails_closed(self) -> None:
        _closed, before = self._before()
        tx = field_transformation(
            transformation_id="door.badpin", required_before_hash="f"*64,
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        with self.assertRaises(TevScriptError):
            apply_field_transformation(before, tx)

    def test_missing_remove_target_fails_closed(self) -> None:
        _closed, before = self._before()
        tx = field_transformation(
            transformation_id="door.missing", remove_fact_hashes=("e"*64,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        with self.assertRaises(TevScriptError):
            apply_field_transformation(before, tx)

    def test_apply_receipt_tamper_is_rejected(self) -> None:
        _closed, before = self._before()
        tx = field_transformation(transformation_id="door.noop", effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES)
        _after, receipt = apply_field_transformation(before, tx)
        wire = {
            "schema": receipt.schema, "before_field_hash": receipt.before_field_hash,
            "transformation_hash": receipt.transformation_hash, "after_field_hash": receipt.after_field_hash,
            "effect_set_hash": receipt.effect_set_hash, "resource_vector_hash": receipt.resource_vector_hash,
            "proof_requirement_hashes": list(receipt.proof_requirement_hashes), "status": receipt.status,
            "receipt_hash": "0"*64,
        }
        with self.assertRaises(TevScriptError):
            validate_apply_receipt(wire)


class OmegaSequenceTests(unittest.TestCase):
    EFFECTS = "1" * 64
    RESOURCES = "2" * 64

    def test_sequence_preserves_literal_order_and_exact_pins(self) -> None:
        closed = field_fact("door.state", ("closed",)); opened = field_fact("door.state", ("open",)); locked = field_fact("door.lock", (True,))
        before = semantic_field((closed,), profile="actual")
        first = field_transformation(
            transformation_id="door.open", required_before_hash=before.field_hash,
            remove_fact_hashes=(closed.fact_hash,), add_facts=(opened,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        middle, _ = apply_field_transformation(before, first)
        second = field_transformation(
            transformation_id="door.lock", required_before_hash=middle.field_hash, add_facts=(locked,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        after, receipts = apply_sequence(before, (first, second))
        self.assertEqual(after, semantic_field((opened, locked), profile="actual"))
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[0].after_field_hash, receipts[1].before_field_hash)
        self.assertEqual(receipts[0].transformation_hash, first.transformation_hash)
        self.assertEqual(receipts[1].transformation_hash, second.transformation_hash)

    def test_reversing_semantic_order_fails_closed(self) -> None:
        closed = field_fact("door.state", ("closed",)); opened = field_fact("door.state", ("open",))
        before = semantic_field((closed,), profile="actual")
        first = field_transformation(
            transformation_id="door.open", required_before_hash=before.field_hash,
            remove_fact_hashes=(closed.fact_hash,), add_facts=(opened,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        middle, _ = apply_field_transformation(before, first)
        second = field_transformation(
            transformation_id="door.close", required_before_hash=middle.field_hash,
            remove_fact_hashes=(opened.fact_hash,), add_facts=(closed,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        with self.assertRaises(TevScriptError):
            apply_sequence(before, (second, first))


if __name__ == "__main__":
    unittest.main()
