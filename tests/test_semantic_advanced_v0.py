from __future__ import annotations
import unittest

from tev_script.semantic_kernel_v0 import FactV0, SemanticFieldV0
from tev_script.semantic_trace_v0 import trace_field, concurrent, bounded_response, finite_ranking_witness
from tev_script.semantic_abstraction_v0 import coarsest_decision_sufficient_relation_sets, project_relations, verify_commuting_square
from tev_script.semantic_computation_v0 import run_to_completion_by_quanta, strictly_decreasing_measure, bounded_capacity_append
from tev_script.semantic_security_v0 import AuthorityGrantV0, can_observe, can_disclose, attenuate
from tev_script.semantic_reflection_v0 import SemanticArtifactV0, ChangeProposalV0, verify_stratified_change
from tev_script.semantic_projection_v0 import model_projection_metadata, necessary_cause_focal

class SemanticAdvancedV0Tests(unittest.TestCase):
    def test_partial_order_has_true_concurrency(self):
        t = trace_field(
            (("a","A","sense"),("b","B","sense"),("c","C","decide")),
            (("a","c"),("b","c")),
        )
        self.assertTrue(concurrent(t,"a","b"))

    def test_bounded_response(self):
        t = trace_field(
            (("r","A","request"),("x","A","tick"),("s","A","response")),
            (("r","x"),("x","s")),
        )
        self.assertTrue(bounded_response(t,"request","response",2))
        self.assertFalse(bounded_response(t,"request","response",1))

    def test_finite_ranking_progress(self):
        self.assertTrue(finite_ranking_witness((3,2,1,0), lambda x: x == 0))
        self.assertFalse(finite_ranking_witness((3,3,2,0), lambda x: x == 0))

    def test_decision_sufficient_coarse_graining(self):
        decl = (("clearance",1),("color",1),("temperature",1),("owner",1))
        vals = (
            SemanticFieldV0.build(decl,(FactV0("clearance",(True,)),FactV0("color",("red",)),FactV0("temperature",(20,)),FactV0("owner",("a",)))),
            SemanticFieldV0.build(decl,(FactV0("clearance",(True,)),FactV0("color",("blue",)),FactV0("temperature",(99,)),FactV0("owner",("b",)))),
            SemanticFieldV0.build(decl,(FactV0("clearance",(False,)),FactV0("color",("red",)),FactV0("temperature",(20,)),FactV0("owner",("a",)))),
        )
        decision = lambda f: "OPEN" if bool(f.facts_for("clearance")[0].arguments[0]) else "REJECT"
        winners = coarsest_decision_sufficient_relation_sets(vals, ("clearance","color","temperature","owner"), decision)
        self.assertEqual(winners, (("clearance",),))

    def test_commuting_square(self):
        fine0 = SemanticFieldV0.build((("x",1),("noise",1)),(FactV0("x",(0,)),FactV0("noise",(9,))))
        fine1 = SemanticFieldV0.build((("x",1),("noise",1)),(FactV0("x",(1,)),FactV0("noise",(8,))))
        alpha = lambda f: project_relations(f,("x",))
        coarse0, coarse1 = alpha(fine0), alpha(fine1)
        judgment = lambda f: "POS" if f.facts_for("x")[0].arguments[0] > 0 else "ZERO"
        self.assertTrue(verify_commuting_square(fine0,fine1,coarse0,coarse1,alpha,judgment))

    def test_resumable_quantum_is_chunk_invariant(self):
        step = lambda x: x + 1
        done = lambda x: x >= 31
        results = [
            run_to_completion_by_quanta(0, step=step, done=done, quantum=q, max_quanta=100).value
            for q in (1,3,7,100)
        ]
        self.assertEqual(results, [31,31,31,31])

    def test_structural_measure_and_capacity(self):
        self.assertTrue(strictly_decreasing_measure((4,3,1,0)))
        self.assertEqual(bounded_capacity_append((1,2),3,2)[0], "CAPACITY_EXCEEDED")

    def test_observe_and_disclose_authority_are_distinct(self):
        grants = (
            AuthorityGrantV0("agent","observe","db","/patients","Secret"),
            AuthorityGrantV0("agent","disclose","db","/patients","Secret"),
        )
        self.assertTrue(can_observe(grants,"agent","db","Secret"))
        self.assertFalse(can_disclose(grants,"agent","db","Secret","Public"))

    def test_explicit_declassification(self):
        grants = (
            AuthorityGrantV0("agent","disclose","db","/patients","Secret"),
            AuthorityGrantV0("agent","declassify","db","/patients","Secret"),
        )
        self.assertTrue(can_disclose(grants,"agent","db","Secret","Public"))

    def test_attenuation_cannot_amplify(self):
        root = AuthorityGrantV0("root","write","filesystem","/project","Secret",delegatable=True)
        child = attenuate(root,subject="agent",scope="/project/assets",max_label="Internal")
        self.assertEqual(child.scope,"/project/assets")
        with self.assertRaises(ValueError):
            attenuate(root,subject="agent",scope="/",max_label="Internal")

    def test_stratified_self_change(self):
        app = SemanticArtifactV0("app","a"*64,3)
        compiler = SemanticArtifactV0("compiler","b"*64,4)
        p = ChangeProposalV0(app,"c"*64,compiler,())
        self.assertEqual(verify_stratified_change(p,("proved",))[0],"PASS")

    def test_same_stratum_self_certification_rejected(self):
        kernel = SemanticArtifactV0("kernel","a"*64,5)
        p = ChangeProposalV0(kernel,"b"*64,kernel,("kernel",))
        self.assertEqual(verify_stratified_change(p,("proved",))[0],"REJECT")

    def test_project_metadata_binds_model_and_assumptions(self):
        a = model_projection_metadata("a"*64,("floor_stable",),"b"*64)
        b = model_projection_metadata("c"*64,("floor_stable",),"b"*64)
        self.assertNotEqual(a.field_hash,b.field_hash)

    def test_temporal_precedence_not_sufficient_cause(self):
        self.assertTrue(necessary_cause_focal(True,False))
        self.assertFalse(necessary_cause_focal(True,True))

if __name__ == "__main__":
    unittest.main()
