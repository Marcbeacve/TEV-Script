from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_kernel_v0 import FactV0, SemanticFieldV0
from tev_script.semantic_residual_v0 import (
    RESIDUAL_PROFILE_V0, ResidualObstructionV0, SemanticResidualError,
    aggregate_residuals, is_residual_field, parse_residual, residual_closed,
    residual_from_obstructions, residualize_fields,
)
from tev_script.semantic_residual_adapters_v0 import (
    residual_from_application_outcome, residual_from_causal_hazards,
    residual_from_divergence, residual_from_inference_judgment,
    residual_from_missing_authority, residual_from_missing_knowledge,
    residual_from_proof_boundary, residual_from_refinement_failures,
)

def field(value: int, *, extra: bool = False) -> SemanticFieldV0:
    facts = [FactV0("state.x", (value,))]
    decls = [("state.x", 1)]
    if extra:
        decls.append(("irrelevant", 1)); facts.append(FactV0("irrelevant", (99,)))
    return SemanticFieldV0.build(decls, facts)

def outcome(status: str, reason: str = "") -> SemanticFieldV0:
    h = "1" * 64
    facts = [FactV0("tev.outcome", (status, "commit", h, h, h, h, h, "test.handler"))]
    decls = [("tev.outcome", 8)]
    if reason:
        decls.append(("tev.outcome.reason", 1)); facts.append(FactV0("tev.outcome.reason", (reason,)))
    return SemanticFieldV0.build(decls, facts)

@dataclass(frozen=True)
class Witness:
    proof_hash: str
    verifier_hash: str
    scope_hash: str
    method: str
    status: str = "active"
@dataclass(frozen=True)
class Policy:
    trusted_verifier_hashes: tuple[str, ...]
    @property
    def policy_hash(self): return canonical_hash({"trusted": list(self.trusted_verifier_hashes)})
    def accepts(self, witness, expected_scope_hash):
        return witness.scope_hash == expected_scope_hash and witness.status == "active" and witness.method in {"proved","attested","exhaustive"} and witness.verifier_hash in self.trusted_verifier_hashes

class SemanticResidualV0Tests(unittest.TestCase):
    def test_residual_is_field_not_third_primitive(self):
        r = residualize_fields(field(1), field(1), judgment_id="j")
        self.assertIsInstance(r, SemanticFieldV0); self.assertEqual(parse_residual(r).status, "CLOSED")
        self.assertEqual(parse_residual(r).judgment["kind"], "field_requirement")

    def test_missing_and_mismatch(self):
        required = SemanticFieldV0.build((("state.x",1),("state.y",1)),(FactV0("state.x",(2,)),FactV0("state.y",(3,))))
        r = residualize_fields(field(1), required, judgment_id="goal")
        view = parse_residual(r)
        self.assertEqual(view.status,"OPEN")
        self.assertEqual({x.kind for x in view.obstructions},{"value_mismatch","missing_fact"})

    def test_irrelevant_observed_difference_is_ignored(self):
        a = residualize_fields(field(1,extra=True), field(1), judgment_id="goal")
        b = residualize_fields(field(1), field(1), judgment_id="goal")
        self.assertTrue(residual_closed(a)); self.assertTrue(residual_closed(b))
        self.assertNotEqual(a.field_hash,b.field_hash)  # provenance differs while judgment closure agrees

    def test_deterministic_obstruction_order_and_dedup(self):
        obs = [ResidualObstructionV0("missing_fact","b",2,None),ResidualObstructionV0("missing_fact","a",1,None),ResidualObstructionV0("missing_fact","b",2,None)]
        r1 = residual_from_obstructions(domain="semantic",judgment_id="j",judgment={"x":1},source={"s":1},obstructions=obs)
        r2 = residual_from_obstructions(domain="semantic",judgment_id="j",judgment={"x":1},source={"s":1},obstructions=reversed(obs))
        self.assertEqual(r1.field_hash,r2.field_hash); self.assertEqual(len(parse_residual(r1).obstructions),2)

    def test_parse_rejects_tampered_status(self):
        r = residualize_fields(field(1), field(1), judgment_id="j")
        root = r.facts_for("tev.residual")[0]
        tampered = r.without("tev.residual").with_fact(FactV0("tev.residual",(root.arguments[0],"OPEN",*root.arguments[2:])))
        with self.assertRaises(SemanticResidualError): parse_residual(tampered)

    def test_application_adapter(self):
        self.assertTrue(residual_closed(residual_from_application_outcome(outcome("COMMITTED"))))
        r = residual_from_application_outcome(outcome("UNKNOWN_COMMIT","network_lost")); v=parse_residual(r)
        self.assertEqual(v.obstructions[0].kind,"unknown_commit"); self.assertEqual(v.obstructions[0].detail["reasons"],["network_lost"])

    def test_inference_adapter(self):
        p = residual_from_inference_judgment(SimpleNamespace(status="PASS",reason="ok",countermodel=()))
        self.assertTrue(residual_closed(p))
        q = residual_from_inference_judgment(SimpleNamespace(status="PROOF_REQUIRED",reason="bound",countermodel=()))
        self.assertEqual(parse_residual(q).obstructions[0].kind,"proof_required")
        c = residual_from_inference_judgment(SimpleNamespace(status="REJECT",reason="countermodel",countermodel=(("p","NEITHER"),)))
        self.assertEqual(parse_residual(c).obstructions[0].kind,"countermodel")

    def test_proof_adapter(self):
        good=Witness("1"*64,"2"*64,"3"*64,"proved"); policy=Policy(("2"*64,))
        self.assertTrue(residual_closed(residual_from_proof_boundary(good,policy,"3"*64)))
        bad=Witness("1"*64,"9"*64,"4"*64,"sampled","revoked")
        kinds={o.kind for o in parse_residual(residual_from_proof_boundary(bad,policy,"3"*64)).obstructions}
        self.assertEqual(kinds,{"scope_mismatch","proof_inactive","proof_method_weak","untrusted_verifier"})

    def test_divergence_adapter_exact_and_scoped(self):
        expected=field(2); observed=field(1)
        r=residual_from_divergence(observed,expected,domain="composition",judgment_id="diamond")
        self.assertEqual({o.kind for o in parse_residual(r).obstructions},{"missing_fact","unexpected_fact"})
        scoped=residual_from_divergence(observed,expected,domain="abstraction",judgment_id="square",relation_scope=("other",))
        self.assertTrue(residual_closed(scoped))

    def test_thin_domain_adapters(self):
        adapters=(
            residual_from_missing_authority(("door.close",)),
            residual_from_missing_knowledge(("human.in_path",)),
            residual_from_causal_hazards(("effect_observation_staging_hazard",)),
            residual_from_refinement_failures(("effect:door.open",)),
        )
        self.assertEqual([parse_residual(x).domain for x in adapters],["authority","epistemic","causal","refinement"])
        self.assertTrue(all(not residual_closed(x) for x in adapters))

    def test_aggregate_preserves_child_hashes(self):
        closed=residualize_fields(field(1),field(1),judgment_id="a")
        open_=residualize_fields(field(1),field(2),judgment_id="b")
        agg=aggregate_residuals((closed,open_),judgment_id="all")
        v=parse_residual(agg); self.assertFalse(v.closed); self.assertEqual(len(v.obstructions),1)
        self.assertEqual(v.obstructions[0].detail["child_residual_hash"],open_.field_hash)

    def test_aggregate_accepts_one_shot_generator(self):
        closed=residualize_fields(field(1),field(1),judgment_id="a")
        open_=residualize_fields(field(1),field(2),judgment_id="b")
        agg=aggregate_residuals((x for x in (closed,open_)),judgment_id="all")
        self.assertEqual(len(parse_residual(agg).obstructions),1)

    def test_parser_rejects_hidden_semantic_surface(self):
        r=residualize_fields(field(1),field(2),judgment_id="j")
        polluted=SemanticFieldV0.build(tuple(r.declarations)+(("hidden.payload",1),),tuple(f for f in r.facts if f.relation!="tev.meta.relation")+(FactV0("hidden.payload",("x",)),))
        with self.assertRaises(SemanticResidualError): parse_residual(polluted)

    def test_profile_and_no_cuofc_dependency(self):
        r=residualize_fields(field(1),field(2),judgment_id="j")
        self.assertEqual(parse_residual(r).status,"OPEN"); self.assertTrue(is_residual_field(r))
        self.assertEqual(r.facts_for("tev.residual")[0].arguments[0],RESIDUAL_PROFILE_V0)
        import pathlib
        root=pathlib.Path(__file__).resolve().parents[1]
        for name in ("semantic_residual_v0.py","semantic_residual_adapters_v0.py"):
            text=(root/"tev_script"/name).read_text(encoding="utf-8")
            self.assertNotIn("cuofc",text.lower()); self.assertNotIn("research",text.lower())

if __name__ == "__main__": unittest.main()
