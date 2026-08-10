from __future__ import annotations
import unittest

from research.cuofc_correspondence_v0 import AUTHORITY_CLASS, Construct
from research.cuofc_residual_correspondence_v0 import (
    TARGET_KIND,
    translate_residual,
    translate_residual_progress,
)
from tev_script.semantic_residual_v0 import parse_residual, residual_closed


class CuofcResidualCorrespondenceV0Tests(unittest.TestCase):
    def construct(self, identifier, outstanding, *, context_hash=None):
        payload = {
            "domain": "semantic",
            "judgment_id": "door.safe_close",
            "judgment": {"kind": "finite_obligation_set", "goal": "door.safe_close"},
            "outstanding": list(outstanding),
        }
        if context_hash is not None:
            payload["context_hash"] = context_hash
        return Construct("residual", identifier, payload)

    def test_open_finite_residual_maps_to_tev_field(self):
        result, field = translate_residual(self.construct("r0", ("human.clear", "obstacle.clear")))
        view = parse_residual(field)
        self.assertEqual((result.status, result.target_kind, result.authority_class), ("DERIVED", TARGET_KIND, AUTHORITY_CLASS))
        self.assertEqual(view.status, "OPEN")
        self.assertEqual(len(view.obstructions), 2)
        self.assertEqual({x.kind for x in view.obstructions}, {"correspondence.outstanding"})

    def test_empty_finite_residual_preserves_closure(self):
        _, field = translate_residual(self.construct("closed", ()))
        self.assertTrue(residual_closed(field))

    def test_subset_progress_is_preserved(self):
        before = self.construct("r0", ("human.clear", "obstacle.clear"))
        after = self.construct("r1", ("obstacle.clear",))
        correspondence = translate_residual_progress(before, after)
        self.assertEqual(correspondence.progress.classification, "REDUCED")
        self.assertEqual(len(correspondence.progress.resolved), 1)
        self.assertEqual(len(correspondence.progress.persistent), 1)
        self.assertFalse(correspondence.progress.introduced)

    def test_boundary_change_is_not_false_progress(self):
        before = self.construct("r0", ("human.clear",), context_hash="1"*64)
        after = self.construct("r1", (), context_hash="2"*64)
        correspondence = translate_residual_progress(before, after)
        self.assertEqual(correspondence.progress.classification, "INCOMPARABLE")

    def test_correspondence_does_not_grant_authority(self):
        result, _ = translate_residual(self.construct("r0", ("human.clear",)))
        self.assertEqual(result.authority_class, "NON_NORMATIVE_RESEARCH_ONLY")
        self.assertIn("cuofc_has_no_tev_runtime_authority", result.obligations)


if __name__ == "__main__":
    unittest.main()
