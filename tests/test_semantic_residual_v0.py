from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from types import SimpleNamespace
import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_kernel_v0 import FactV0, SemanticFieldV0
from tev_script.semantic_residual_v0 import (
    RESIDUAL_PROFILE_V0,
    ResidualObstructionV0,
    SemanticResidualError,
    aggregate_residuals,
    is_residual_field,
    join_residuals,
    parse_residual,
    residual_closed,
    residual_dependency_refs,
    residual_from_obstructions,
    residual_obstructions,
    residual_progress,
    residual_strictly_refines,
    residualize_fields,
)
from tev_script.semantic_residual_adapters_v0 import (
    residual_from_application_outcome,
    residual_from_causal_hazards,
    residual_from_divergence,
    residual_from_inference_judgment,
    residual_from_liveness_obligations,
    residual_from_missing_authority,
    residual_from_missing_knowledge,
    residual_from_proof_boundary,
    residual_from_refinement_failures,
    residual_from_resource_deficits,
    residual_from_safety_violations,
)


def field(value: int, *, extra: bool = False) -> SemanticFieldV0:
    facts = [FactV0("state.x", (value,))]
    decls = [("state.x", 1)]
    if extra:
        decls.append(("irrelevant", 1))
        facts.append(FactV0("irrelevant", (99,)))
    return SemanticFieldV0.build(decls, facts)


def required_xy(x: int = 1, y: int = 2) -> SemanticFieldV0:
    return SemanticFieldV0.build(
        (("state.x", 1), ("state.y", 1)),
        (FactV0("state.x", (x,)), FactV0("state.y", (y,))),
    )


def outcome(status: str, mode: str, reason: str = "") -> SemanticFieldV0:
    h = "1" * 64
    facts = [FactV0("tev.outcome", (status, mode, h, h, h, h, h, "test.handler"))]
    decls = [("tev.outcome", 8)]
    if reason:
        decls.append(("tev.outcome.reason", 1))
        facts.append(FactV0("tev.outcome.reason", (reason,)))
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
    def policy_hash(self):
        return canonical_hash({"trusted": list(self.trusted_verifier_hashes)})

    def accepts(self, witness, expected_scope_hash):
        return (
            witness.scope_hash == expected_scope_hash
            and witness.status == "active"
            and witness.method in {"proved", "attested", "exhaustive"}
            and witness.verifier_hash in self.trusted_verifier_hashes
        )


class SemanticResidualCoreV0Tests(unittest.TestCase):
    def test_residual_is_field_not_third_primitive(self):
        r = residualize_fields(field(1), field(1), judgment_id="j")
        self.assertIsInstance(r, SemanticFieldV0)
        self.assertEqual(parse_residual(r).status, "CLOSED")
        self.assertEqual(r.facts_for("tev.residual")[0].arguments[0], RESIDUAL_PROFILE_V0)

    def test_closed_is_judgment_relative_not_world_equality(self):
        r = residualize_fields(field(1, extra=True), field(1), judgment_id="j")
        self.assertTrue(residual_closed(r))
        self.assertEqual(parse_residual(r).judgment["kind"], "field_requirement")

    def test_missing_and_mismatch_are_structural(self):
        r = residualize_fields(field(9), required_xy(1, 2), judgment_id="goal")
        kinds = {x.kind for x in parse_residual(r).obstructions}
        self.assertEqual(kinds, {"semantic.value_mismatch", "semantic.missing_fact"})

    def test_source_is_self_describing_and_hash_bound(self):
        r = residualize_fields(field(1), field(2), judgment_id="goal")
        v = parse_residual(r)
        self.assertEqual(v.source["kind"], "semantic_field")
        self.assertEqual(v.source["field_hash"], field(1).field_hash)

    def test_deterministic_obstruction_order_and_dedup(self):
        obs = (
            ResidualObstructionV0("semantic.missing_fact", "b", 2, None),
            ResidualObstructionV0("semantic.missing_fact", "a", 1, None),
            ResidualObstructionV0("semantic.missing_fact", "b", 2, None),
        )
        hashes = set()
        for perm in permutations(obs):
            hashes.add(
                residual_from_obstructions(
                    domain="semantic", judgment_id="j", judgment={"x": 1},
                    source={"s": 1}, obstructions=perm,
                ).field_hash
            )
        self.assertEqual(len(hashes), 1)
        one = residual_from_obstructions(
            domain="semantic", judgment_id="j", judgment={"x": 1}, source={"s": 1}, obstructions=obs
        )
        self.assertEqual(len(parse_residual(one).obstructions), 2)

    def test_dependency_refs_are_canonical_and_queryable(self):
        a = ResidualObstructionV0(
            "proof.required", "lemma", dependency_refs=("z", "a", "z")
        )
        r = residual_from_obstructions(
            domain="proof", judgment_id="j", judgment={}, source={}, obstructions=(a,)
        )
        self.assertEqual(parse_residual(r).obstructions[0].dependency_refs, ("a", "z"))
        self.assertEqual(residual_dependency_refs(r), ("a", "z"))
        self.assertEqual(len(residual_obstructions(r, dependency_refs=("a",))), 1)
        self.assertEqual(len(residual_obstructions(r, dependency_refs=("missing",))), 0)

    def test_parser_rejects_tampered_status(self):
        r = residualize_fields(field(1), field(1), judgment_id="j")
        root = r.facts_for("tev.residual")[0]
        tampered = r.without("tev.residual").with_fact(
            FactV0("tev.residual", (root.arguments[0], "OPEN", *root.arguments[2:]))
        )
        with self.assertRaises(SemanticResidualError):
            parse_residual(tampered)

    def test_parser_rejects_tampered_source_hash(self):
        r = residualize_fields(field(1), field(2), judgment_id="j")
        root = r.facts_for("tev.residual")[0]
        args = list(root.arguments)
        args[6] = "0" * 64
        tampered = r.without("tev.residual").with_fact(FactV0("tev.residual", tuple(args)))
        with self.assertRaises(SemanticResidualError):
            parse_residual(tampered)

    def test_parser_rejects_tampered_obstruction_hash(self):
        r = residualize_fields(field(1), field(2), judgment_id="j")
        row = r.facts_for("tev.residual.obstruction")[0]
        args = list(row.arguments)
        args[1] = "0" * 64
        tampered = r.without("tev.residual.obstruction", row.arguments).with_fact(
            FactV0("tev.residual.obstruction", tuple(args))
        )
        with self.assertRaises(SemanticResidualError):
            parse_residual(tampered)

    def test_parser_rejects_hidden_semantic_surface(self):
        r = residualize_fields(field(1), field(2), judgment_id="j")
        polluted = SemanticFieldV0.build(
            tuple(r.declarations) + (("hidden.payload", 1),),
            tuple(f for f in r.facts if f.relation != "tev.meta.relation") + (FactV0("hidden.payload", ("x",)),),
        )
        with self.assertRaises(SemanticResidualError):
            parse_residual(polluted)

    def test_join_same_boundary_flattens_obstructions(self):
        subject = field(1)
        required = required_xy(2, 3)
        full = residualize_fields(subject, required, judgment_id="goal")
        v = parse_residual(full)
        r1 = residual_from_obstructions(
            domain=v.domain, judgment_id=v.judgment_id, judgment=v.judgment,
            source={"part": 1}, obstructions=(v.obstructions[0],),
            context_hash=v.context_hash, law_hash=v.law_hash,
        )
        r2 = residual_from_obstructions(
            domain=v.domain, judgment_id=v.judgment_id, judgment=v.judgment,
            source={"part": 2}, obstructions=(v.obstructions[1],),
            context_hash=v.context_hash, law_hash=v.law_hash,
        )
        joined = join_residuals((r1, r2))
        self.assertEqual(
            set(parse_residual(joined).obstruction_hashes),
            set(v.obstruction_hashes),
        )

    def test_join_rejects_different_judgment_boundaries(self):
        a = residualize_fields(field(1), field(2), judgment_id="a")
        b = residualize_fields(field(1), field(2), judgment_id="b")
        with self.assertRaises(SemanticResidualError):
            join_residuals((a, b))

    def test_aggregate_preserves_open_child_hashes(self):
        closed = residualize_fields(field(1), field(1), judgment_id="a")
        open_ = residualize_fields(field(1), field(2), judgment_id="b")
        agg = aggregate_residuals((closed, open_), judgment_id="all")
        v = parse_residual(agg)
        self.assertFalse(v.closed)
        self.assertEqual(len(v.obstructions), 1)
        self.assertEqual(v.obstructions[0].detail["child_residual_hash"], open_.field_hash)
        self.assertIn(open_.field_hash, v.obstructions[0].dependency_refs)

    def test_progress_closed(self):
        before = residualize_fields(field(1), field(2), judgment_id="j")
        after = residualize_fields(field(2), field(2), judgment_id="j")
        p = residual_progress(before, after)
        self.assertEqual(p.classification, "CLOSED")
        self.assertTrue(p.resolved)
        self.assertFalse(p.introduced)
        self.assertTrue(residual_strictly_refines(after, before))

    def test_progress_reduced_without_scalar_metric(self):
        req = required_xy(2, 3)
        before = residualize_fields(field(1), req, judgment_id="j")
        partial = SemanticFieldV0.build(
            (("state.x", 1),), (FactV0("state.x", (2,)),)
        )
        after = residualize_fields(partial, req, judgment_id="j")
        p = residual_progress(before, after)
        self.assertEqual(p.classification, "REDUCED")
        self.assertEqual(len(p.resolved), 1)
        self.assertEqual(len(p.persistent), 1)

    def test_progress_regressed(self):
        before = residualize_fields(field(2), field(2), judgment_id="j")
        after = residualize_fields(field(1), field(2), judgment_id="j")
        self.assertEqual(residual_progress(before, after).classification, "REGRESSED")

    def test_progress_changed_when_old_resolves_and_new_appears(self):
        j = {"kind": "manual"}
        before = residual_from_obstructions(
            domain="semantic", judgment_id="j", judgment=j, source={"t": 0},
            obstructions=(ResidualObstructionV0("demo.a", "x"),),
        )
        after = residual_from_obstructions(
            domain="semantic", judgment_id="j", judgment=j, source={"t": 1},
            obstructions=(ResidualObstructionV0("demo.b", "y"),),
        )
        p = residual_progress(before, after)
        self.assertEqual(p.classification, "CHANGED")
        self.assertEqual(len(p.resolved), 1)
        self.assertEqual(len(p.introduced), 1)

    def test_progress_incomparable_when_context_changes(self):
        a = residual_from_obstructions(
            domain="semantic", judgment_id="j", judgment={}, source={}, obstructions=(), context_hash="1"*64
        )
        b = residual_from_obstructions(
            domain="semantic", judgment_id="j", judgment={}, source={}, obstructions=(), context_hash="2"*64
        )
        self.assertEqual(residual_progress(a, b).classification, "INCOMPARABLE")


class SemanticResidualAdapterV0Tests(unittest.TestCase):
    def test_application_adapter_is_mode_sensitive(self):
        self.assertTrue(residual_closed(residual_from_application_outcome(outcome("COMPLETED", "evaluate"))))
        self.assertTrue(residual_closed(residual_from_application_outcome(outcome("PREPARED", "prepare"))))
        self.assertTrue(residual_closed(residual_from_application_outcome(outcome("COMMITTED", "commit"))))
        wrong = residual_from_application_outcome(outcome("PREPARED", "commit"))
        self.assertFalse(residual_closed(wrong))
        self.assertEqual(parse_residual(wrong).obstructions[0].kind, "operational.status_unaccepted")

    def test_unknown_commit_preserves_reconciliation_obstruction(self):
        r = residual_from_application_outcome(outcome("UNKNOWN_COMMIT", "commit", "network_lost"))
        v = parse_residual(r)
        self.assertEqual(v.obstructions[0].kind, "operational.unknown_commit")
        self.assertEqual(v.obstructions[0].detail["reasons"], ["network_lost"])
        self.assertEqual(v.context_hash, "1" * 64)
        self.assertEqual(v.law_hash, "1" * 64)

    def test_inference_adapter(self):
        p = residual_from_inference_judgment(SimpleNamespace(status="PASS", reason="ok", countermodel=()))
        self.assertTrue(residual_closed(p))
        q = residual_from_inference_judgment(SimpleNamespace(status="PROOF_REQUIRED", reason="bound", countermodel=()))
        self.assertEqual(parse_residual(q).obstructions[0].kind, "proof.required")
        c = residual_from_inference_judgment(SimpleNamespace(status="REJECT", reason="countermodel", countermodel=(("p", "NEITHER"),)))
        self.assertEqual(parse_residual(c).obstructions[0].kind, "epistemic.countermodel")

    def test_proof_adapter_exposes_all_independent_obstructions(self):
        good = Witness("1"*64, "2"*64, "3"*64, "proved")
        policy = Policy(("2"*64,))
        self.assertTrue(residual_closed(residual_from_proof_boundary(good, policy, "3"*64)))
        bad = Witness("1"*64, "9"*64, "4"*64, "sampled", "revoked")
        kinds = {o.kind for o in parse_residual(residual_from_proof_boundary(bad, policy, "3"*64)).obstructions}
        self.assertEqual(kinds, {"proof.scope_mismatch", "proof.inactive", "proof.method_weak", "proof.untrusted_verifier"})

    def test_divergence_exact_and_scoped(self):
        expected = field(2)
        observed = field(1)
        r = residual_from_divergence(observed, expected, domain="composition", judgment_id="diamond")
        self.assertEqual(
            {o.kind for o in parse_residual(r).obstructions},
            {"composition.missing_fact", "composition.unexpected_fact"},
        )
        scoped = residual_from_divergence(
            observed, expected, domain="abstraction", judgment_id="square", relation_scope=("other",)
        )
        self.assertTrue(residual_closed(scoped))

    def test_cross_layer_thin_adapters_share_one_profile(self):
        residuals = (
            residual_from_missing_authority(("door.close",)),
            residual_from_missing_knowledge(("human.in_path",)),
            residual_from_causal_hazards(("effect_observation_staging_hazard",)),
            residual_from_refinement_failures(("effect:door.open",)),
            residual_from_resource_deficits(("energy",)),
            residual_from_safety_violations(("human.in_path",)),
            residual_from_liveness_obligations(("eventually.closed",)),
        )
        self.assertEqual(
            [parse_residual(x).domain for x in residuals],
            ["authority", "epistemic", "causal", "refinement", "resource", "safety", "liveness"],
        )
        self.assertTrue(all(not residual_closed(x) for x in residuals))
        self.assertTrue(all(x.facts_for("tev.residual")[0].arguments[0] == RESIDUAL_PROFILE_V0 for x in residuals))

    def test_no_cuofc_or_agent_runtime_dependency(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("semantic_residual_v0.py", "semantic_residual_adapters_v0.py"):
            text = (root / "tev_script" / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("cuofc", text)
            self.assertNotIn("ia_tev", text)
            self.assertNotIn("planner", text)
            self.assertNotIn("agent", text)


if __name__ == "__main__":
    unittest.main()
