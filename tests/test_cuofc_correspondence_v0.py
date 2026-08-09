from __future__ import annotations
import unittest
from pathlib import Path
from research.cuofc_correspondence_v0 import Construct,AUTHORITY_CLASS,field,transformation,center,evidence,observation,observation_roles,laws,translate
from tev_script.semantic_apply_v0 import apply_rule,outcome_after_field
from tev_script.semantic_epistemic_v0 import proposition_status
from tev_script.semantic_kernel_v0 import FactV0,SemanticFieldV0
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_field_exact(self):
  c=Construct("field","door",{"declarations":[["door.phase",2]],"facts":[{"relation":"door.phase","arguments":["d","closed"]}]}); r,f=field(c); d=SemanticFieldV0.build((("door.phase",2),),(FactV0("door.phase",("d","closed")),)); self.assertEqual((r.status,r.authority_class,f.field_hash),("EXACT",AUTHORITY_CLASS,d.field_hash))
 def test_transformation_apply(self):
  fc=Construct("field","f",{"declarations":[["x",1]],"facts":[{"relation":"x","arguments":[0]}]}); tc=Construct("transformation","set1",{"operations":[{"opcode":"remove","payload":{"relation":"x"}},{"opcode":"put","payload":{"relation":"x","arguments":[1]}}]}); _,f=field(fc); _,r=transformation(tc); self.assertTrue(outcome_after_field(apply_rule(f,r)).has("x",(1,)))
 def test_center_identity(self):
  def C(i,a): return Construct("center",i,{"center_id":i,"view_hash":"1"*64,"knowledge_hash":"2"*64,"authority_hash":a,"frame_hash":"4"*64,"policy_hash":"5"*64})
  self.assertNotEqual(center(C("a","a"*64))[2],center(C("b","b"*64))[2])
 def test_evidence_both(self):
  c=Construct("evidence","e",{"rows":[["e1","p","support","a",1,2,"s1","active"],["e2","p","refute","b",1,3,"s2","active"]]}); self.assertEqual(proposition_status(evidence(c)[1],"p"),"BOTH")
 def test_destructive_observation(self): self.assertEqual(observation_roles(Construct("observation","pop",{"capability":"queue.pop","arguments":["q"],"external_mode":"consume","temporal":"sequence_sensitive"})),("action","observation"))
 def test_project_noncommit(self):
  _,f=field(Construct("field","f",{"declarations":[["seen",1]],"facts":[]})); _,r=observation(Construct("observation","read",{"capability":"sensor.read","target_relation":"seen","temporal":"snapshot"})); calls=[]
  def model(cap,args): calls.append(cap); return 7
  out=apply_rule(f,r,mode="project",observation_provider=model); root=out.facts_for("tev.outcome")[0]; self.assertEqual((root.arguments[0],root.arguments[1],calls),("COMPLETED","project",["sensor.read"])); self.assertTrue(outcome_after_field(out).has("seen",(7,)))
 def test_law_not_truth(self):
  r,ls,h=laws(Construct("environment_laws","l",{"domains":[{"domain":"state","complete":True,"snapshot_reads_commute":True}]})); self.assertEqual(r.target_hash,h); self.assertIn("law_truth_requires_independent_justification",r.obligations); self.assertIn("state",ls)
 def test_negative_boundaries(self):
  for k,s in {"actual_world":"OUT_OF_SCOPE","truth_authority":"REJECT","continuum":"PARTIAL","unstratified_self_reference":"REJECT","omniscient_center":"PARTIAL"}.items(): self.assertEqual(translate(Construct(k,k,{})).status,s)
 def test_authority_noninterference(self):
  bad=[]
  for p in ROOT.rglob("*"):
   if not p.is_file() or ".git" in p.parts: continue
   rel=p.relative_to(ROOT).as_posix()
   if rel.startswith(("research/","tests/test_cuofc_","tests/run_cuofc_")): continue
   if not (rel.startswith(("tev_script/","runtimes/","javascript/","conformance/","schemas/","spec/","tools/","RUN_TEV_SCRIPT")) or rel in {"REPOSITORY_CHANNEL.json","CANONICAL_INDEX.json","DESIGN_DECISION.json","descriptor.json","pyproject.toml"}): continue
   try: txt=p.read_text(encoding="utf-8")
   except: continue
   if "research.cuofc_correspondence" in txt or "from research" in txt or "import research" in txt: bad.append(rel)
  self.assertEqual(bad,[])
if __name__=="__main__": unittest.main()
