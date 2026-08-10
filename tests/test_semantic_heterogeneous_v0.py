from __future__ import annotations
import unittest

from tev_script.semantic_kernel_v0 import FactV0, SemanticFieldV0
from tev_script.semantic_effects_v0 import EffectAtomV0, derived_roles

class SemanticHeterogeneousV0Tests(unittest.TestCase):
    def test_eight_domains_share_same_kernel(self):
        cases = (
            ("door", ("clear", True), EffectAtomV0("external","door:motor","write")),
            ("filesystem", ("exists", True), EffectAtomV0("external","file:A","write")),
            ("robot", ("grasping", False), EffectAtomV0("external","arm:1","write")),
            ("bank", ("balance", 10), EffectAtomV0("external","account:1","reserve")),
            ("hidden_agent", ("visible", False), EffectAtomV0("knowledge","agent:1","read",exposure="acquired")),
            ("algebra", ("carrier_size", 4), EffectAtomV0("state","carrier","read",temporal="snapshot")),
            ("code_update", ("version", 2), EffectAtomV0("authority","program:update","consume")),
            ("knowledge", ("known", False), EffectAtomV0("knowledge","claim:x","write",exposure="acquired")),
        )
        hashes = []
        for domain, (name, value), effect in cases:
            field = SemanticFieldV0.build((("domain",1),("fact",3)),(
                FactV0("domain",(domain,)),
                FactV0("fact",(domain,name,value)),
            ))
            hashes.append(field.field_hash)
            self.assertTrue(effect.domain)
        self.assertEqual(len(set(hashes)), 8)

if __name__ == "__main__":
    unittest.main()
