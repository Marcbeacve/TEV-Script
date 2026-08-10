from __future__ import annotations
import unittest

from tev_script.semantic_governance_v0 import LawJustificationV0, DecisionDimensionsV0, law_claim_status
from tev_script.semantic_kernel_v0 import FactV0, SemanticFieldV0
from tev_script.semantic_apply_v0 import RuleOpV0, rule_field, apply_rule, commit_prepared
from tev_script.semantic_effects_v0 import EffectAtomV0
from tev_script.semantic_composition_v0 import compose_rules, composition_barrier, reconcile_unknown, outcome_after_field

class SemanticGovernanceV0Tests(unittest.TestCase):
    def test_law_hash_is_not_truth(self):
        sampled = LawJustificationV0("a"*64,"observed","device","campaign")
        proved = LawJustificationV0("a"*64,"proved","device","proof")
        falsified = LawJustificationV0("a"*64,"observed","device","counterexample","falsified")
        self.assertEqual(law_claim_status((sampled,)),"PROOF_REQUIRED")
        self.assertEqual(law_claim_status((proved,)),"PASS")
        self.assertEqual(law_claim_status((proved,falsified)),"REJECT")

    def test_desirability_not_part_of_admissibility(self):
        good_bad_goal = DecisionDimensionsV0(True,True,True,True,-999)
        self.assertEqual(good_bad_goal.admissibility(),"ADMISSIBLE")
        unknown = DecisionDimensionsV0(True,None,True,True,999)
        self.assertEqual(unknown.admissibility(),"UNKNOWN")

    def test_rule_composition_is_associative_focal(self):
        base = SemanticFieldV0.build((("x",1),), (FactV0("x",(0,)),))
        a = rule_field("a",(RuleOpV0("remove",{"relation":"x"}),RuleOpV0("put",{"relation":"x","arguments":[1]})))
        b = rule_field("b",(RuleOpV0("remove",{"relation":"x"}),RuleOpV0("put",{"relation":"x","arguments":[2]})))
        c = rule_field("c",(RuleOpV0("remove",{"relation":"x"}),RuleOpV0("put",{"relation":"x","arguments":[3]})))
        left = compose_rules("left",(compose_rules("ab",(a,b)),c))
        right = compose_rules("right",(a,compose_rules("bc",(b,c))))
        lo = apply_rule(base,left,mode="evaluate",observation_provider=lambda *_:None)
        ro = apply_rule(base,right,mode="evaluate",observation_provider=lambda *_:None)
        self.assertEqual(outcome_after_field(lo).field_hash,outcome_after_field(ro).field_hash)

    def test_unknown_commit_is_barrier_and_reconcile(self):
        base = SemanticFieldV0.build((("x",1),), (FactV0("x",(0,)),))
        effect = EffectAtomV0("external","remote:x","write")
        r = rule_field("r",(
            RuleOpV0("remove",{"relation":"x"}),
            RuleOpV0("put",{"relation":"x","arguments":[1]}),
            RuleOpV0("effect",{"effect_index":0}),
        ),(effect,))
        p = apply_rule(base,r,mode="prepare",observation_provider=lambda *_:None)
        unknown = commit_prepared(p,current=base,effect_provider=lambda _: "UNKNOWN_COMMIT")
        self.assertTrue(composition_barrier(unknown))
        expected = outcome_after_field(p)
        self.assertEqual(reconcile_unknown(unknown,expected)[0],"COMMITTED")
        self.assertEqual(reconcile_unknown(unknown,base)[0],"DIVERGED")

if __name__ == "__main__":
    unittest.main()
