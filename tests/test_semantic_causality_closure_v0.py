from __future__ import annotations

import unittest

from tev_script.semantic_causality_v0 import (
    BooleanEquationV0,
    FiniteBooleanSCMV0,
    but_for_actual_cause,
    causal_judgment,
    causal_scope_hash,
)
from tev_script.semantic_proof_boundary_v0 import (
    ProofBoundaryWitnessV0,
    VerifierTrustPolicyV0,
)


def unary(variable, parent, function):
    return BooleanEquationV0(
        variable,
        (parent,),
        (
            ((False,), bool(function(False))),
            ((True,), bool(function(True))),
        ),
    )


class CausalityClosureV0Tests(unittest.TestCase):
    @staticmethod
    def model():
        return FiniteBooleanSCMV0(
            ("U",),
            (
                unary("X", "U", lambda value: value),
                unary("Y", "X", lambda value: value),
            ),
        )

    def test_direct_but_for_cause(self):
        result = but_for_actual_cause(
            self.model(),
            {"U": True},
            {"X": True},
            "Y",
            True,
        )
        self.assertEqual(result.status, "PASS")

    def test_self_and_exogenous_causes_reject(self):
        model = self.model()
        self.assertEqual(
            but_for_actual_cause(
                model,
                {"U": True},
                {"Y": True},
                "Y",
                True,
            ).reason,
            "self_causation_disallowed",
        )
        self.assertEqual(
            but_for_actual_cause(
                model,
                {"U": True},
                {"U": True},
                "Y",
                True,
            ).reason,
            "cause_not_endogenous",
        )

    def test_redundant_or_branch_is_not_but_for_cause(self):
        x = unary("X", "U1", lambda value: value)
        z = unary("Z", "U2", lambda value: value)
        y = BooleanEquationV0(
            "Y",
            ("X", "Z"),
            tuple(
                ((left, right), left or right)
                for left in (False, True)
                for right in (False, True)
            ),
        )
        model = FiniteBooleanSCMV0(
            ("U1", "U2"),
            (x, z, y),
        )
        self.assertEqual(
            but_for_actual_cause(
                model,
                {
                    "U1": True,
                    "U2": True,
                },
                {"X": True},
                "Y",
                True,
            ).status,
            "REJECT",
        )

    def test_general_criterion_requires_trusted_scope(self):
        model = self.model()
        context = {"U": True}
        cause = {"X": True}
        scope_hash = causal_scope_hash(
            model,
            context,
            cause,
            "Y",
            True,
            "HP_GENERAL",
        )
        witness = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            scope_hash,
            "attested",
        )
        self.assertEqual(
            causal_judgment(
                criterion="HP_GENERAL",
                model=model,
                context=context,
                cause=cause,
                outcome_variable="Y",
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("c" * 64,)
                ),
            ).status,
            "PROOF_REQUIRED",
        )
        self.assertEqual(
            causal_judgment(
                criterion="HP_GENERAL",
                model=model,
                context=context,
                cause=cause,
                outcome_variable="Y",
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("b" * 64,)
                ),
            ).status,
            "PASS",
        )


if __name__ == "__main__":
    unittest.main()
