from __future__ import annotations
import unittest

from tev_script.canonical import canonical_hash

from tev_script.semantic_kernel_v0 import FactV0, SemanticFieldV0
from tev_script.semantic_effects_v0 import EffectAtomV0, DomainLawV0, effects_commute, derived_roles
from tev_script.semantic_apply_v0 import RuleOpV0, rule_field, apply_rule, commit_prepared, outcome_after_field
from tev_script.semantic_epistemic_v0 import evidence_field, proposition_status, invalidate_transitively

class SemanticCalculusV0Tests(unittest.TestCase):
    @staticmethod
    def state(value=0):
        return SemanticFieldV0.build((("x", 1), ("seen", 1)), (FactV0("x", (value,)),))

    def test_identity_not_state(self):
        f0 = SemanticFieldV0.build((("entity",1),("angle",2)), (FactV0("entity",("door:1",)), FactV0("angle",("door:1",0))))
        f1 = SemanticFieldV0.build((("entity",1),("angle",2)), (FactV0("entity",("door:1",)), FactV0("angle",("door:1",10))))
        self.assertNotEqual(f0.field_hash, f1.field_hash)
        self.assertEqual(f0.facts_for("entity")[0].arguments, f1.facts_for("entity")[0].arguments)

    def test_field_canonical_dedupe(self):
        a = SemanticFieldV0.build((("r",1),), (FactV0("r",({"b":2,"a":1},)), FactV0("r",({"a":1,"b":2},))))
        self.assertEqual(len(a.facts_for("r")), 1)

    def test_project_is_non_committing(self):
        before = self.state(0)
        rule = rule_field("set", (RuleOpV0("remove", {"relation":"x"}), RuleOpV0("put", {"relation":"x","arguments":[1]})))
        out = apply_rule(before, rule, mode="project", observation_provider=lambda *_: None)
        self.assertEqual(before.facts_for("x")[0].arguments[0], 0)
        self.assertEqual(outcome_after_field(out).facts_for("x")[0].arguments[0], 1)

    def test_prepare_then_commit(self):
        before = self.state(0)
        effect = EffectAtomV0("external","motor:door","write", recoverability="irreversible")
        rule = rule_field(
            "open",
            (RuleOpV0("remove", {"relation":"x"}), RuleOpV0("put", {"relation":"x","arguments":[1]}), RuleOpV0("effect", {"effect_index":0})),
            (effect,),
        )
        prepared = apply_rule(before, rule, mode="prepare", observation_provider=lambda *_: None)
        committed = commit_prepared(prepared, current=before, effect_provider=lambda _: "COMMITTED")
        self.assertEqual(committed.facts_for("tev.outcome")[0].arguments[0], "COMMITTED")
        self.assertEqual(outcome_after_field(committed).facts_for("x")[0].arguments[0], 1)

    def test_unknown_commit_does_not_publish_state(self):
        before = self.state(0)
        effect = EffectAtomV0("external","remote:write","write", recoverability="unknown")
        rule = rule_field(
            "remote",
            (RuleOpV0("remove", {"relation":"x"}), RuleOpV0("put", {"relation":"x","arguments":[1]}), RuleOpV0("effect", {"effect_index":0})),
            (effect,),
        )
        prepared = apply_rule(before, rule, mode="prepare", observation_provider=lambda *_: None)
        result = commit_prepared(prepared, current=before, effect_provider=lambda _: "UNKNOWN_COMMIT")
        self.assertEqual(result.facts_for("tev.outcome")[0].arguments[0], "UNKNOWN_COMMIT")
        self.assertEqual(outcome_after_field(result).field_hash, before.field_hash)

    def test_outcome_binds_center_laws_handler_and_parent(self):
        before = self.state(0)
        rule = rule_field("noop", ())
        c1 = canonical_hash({"center": "a"})
        c2 = canonical_hash({"center": "b"})
        laws = canonical_hash({"laws": ["L1"]})
        a = apply_rule(before, rule, mode="prepare", observation_provider=lambda *_: None, context_hash=c1, law_hash=laws, handler_id="test.prepare")
        b = apply_rule(before, rule, mode="prepare", observation_provider=lambda *_: None, context_hash=c2, law_hash=laws, handler_id="test.prepare")
        self.assertNotEqual(a.field_hash, b.field_hash)
        root = a.facts_for("tev.outcome")[0].arguments
        self.assertEqual(root[5], c1)
        self.assertEqual(root[6], laws)
        self.assertEqual(root[7], "test.prepare")
        committed = commit_prepared(a, current=before, effect_provider=lambda _: "COMMITTED")
        self.assertEqual(committed.facts_for("tev.outcome.parent")[0].arguments[0], a.field_hash)
        croot = committed.facts_for("tev.outcome")[0].arguments
        self.assertEqual(croot[5], c1)
        self.assertEqual(croot[6], laws)
        self.assertEqual(croot[7], "reference.commit")

    def test_apply_rejects_noncanonical_context_hash(self):
        with self.assertRaises(ValueError):
            apply_rule(self.state(0), rule_field("noop", ()), mode="evaluate", observation_provider=lambda *_: None, context_hash="not-a-hash")

    def test_destructive_observation_is_explicit(self):
        q = [7, 8]
        before = self.state(0)
        effects = (
            EffectAtomV0("knowledge","queue.pop","read", exposure="acquired"),
            EffectAtomV0("external","queue:q","consume", recoverability="irreversible"),
        )
        rule = rule_field(
            "pop",
            (RuleOpV0("observe", {"capability":"queue.pop","target_relation":"seen"}),),
            effects,
        )
        prepared = apply_rule(before, rule, mode="prepare", observation_provider=lambda *_: q.pop(0))
        self.assertEqual(q, [8])
        self.assertEqual(outcome_after_field(prepared).facts_for("seen")[0].arguments, (7,))
        self.assertEqual(set(derived_roles(effects)), {"action","observation"})

    def test_sequence_sensitive_read_read_does_not_commute(self):
        a = EffectAtomV0("external","sensor:s","read", temporal="sequence_sensitive")
        law = DomainLawV0("external", complete=True, snapshot_reads_commute=True, stable_reads_commute=True)
        self.assertFalse(effects_commute((a,), (a,), {"external":law})[0])

    def test_snapshot_reads_commute(self):
        a = EffectAtomV0("external","sensor:s","read", temporal="snapshot")
        law = DomainLawV0("external", complete=True, snapshot_reads_commute=True)
        self.assertTrue(effects_commute((a,), (a,), {"external":law})[0])

    def test_argument_indexed_resources_are_distinct(self):
        a = EffectAtomV0("external","file","write", payload=("A.txt",))
        b = EffectAtomV0("external","file","write", payload=("B.txt",))
        law = DomainLawV0("external", complete=True)
        self.assertTrue(effects_commute((a,), (b,), {"external":law})[0])

    def test_evidence_conflict_is_first_class(self):
        ev = evidence_field((
            ("e1","door.open","support","cameraA",1000,1001,"","active"),
            ("e2","door.open","refute","cameraB",1000,1002,"","active"),
        ))
        self.assertEqual(proposition_status(ev,"door.open"), "BOTH")

    def test_provenance_invalidation_is_transitive(self):
        ev = evidence_field(
            (
                ("e0","camera.detect","support","camera",1,1,"","active"),
                ("e1","object.exists","support","detector",1,2,"e0","active"),
                ("e2","door.unsafe","support","physics",1,3,"e1","active"),
            ),
            dependencies=(("e1","e0"),("e2","e1")),
        )
        out = invalidate_transitively(ev,"e0","source_invalid")
        invalid = {f.arguments[0] for f in out.facts_for("tev.evidence.invalidated")}
        self.assertEqual(invalid, {"e0","e1","e2"})

if __name__ == "__main__":
    unittest.main()
