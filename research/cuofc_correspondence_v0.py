from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Mapping
from tev_script.canonical import canonical_hash,canonical_json
from tev_script.semantic_apply_v0 import RuleOpV0,rule_field
from tev_script.semantic_effects_v0 import DomainLawV0,EffectAtomV0,derived_roles
from tev_script.semantic_epistemic_v0 import evidence_field
from tev_script.semantic_governance_v0 import CenterContextV0
from tev_script.semantic_kernel_v0 import FactV0,SemanticFieldV0
AUTHORITY_CLASS="NON_NORMATIVE_RESEARCH_ONLY"
STATUSES={"EXACT","DERIVED","PARTIAL","OUT_OF_SCOPE","REJECT"}
@dataclass(frozen=True,slots=True)
class Construct:
 kind:str; identifier:str; payload:Mapping[str,Any]; assumptions:tuple[str,...]=()
 def __post_init__(self): canonical_json(dict(self.payload)); canonical_json(list(self.assumptions))
 @property
 def source_hash(self): return canonical_hash({"schema":"CUOFC_CONSTRUCT_V0","kind":self.kind,"id":self.identifier,"payload":dict(self.payload),"assumptions":list(self.assumptions)})
@dataclass(frozen=True,slots=True)
class Result:
 source_hash:str; source_kind:str; status:str; target_kind:str=""; target_hash:str=""; obligations:tuple[str,...]=(); reason:str=""; authority_class:str=AUTHORITY_CLASS
 def __post_init__(self):
  if self.status not in STATUSES or self.authority_class!=AUTHORITY_CLASS: raise ValueError("correspondence authority/status")
def R(c,s,t="",h="",o=(),reason=""): return Result(c.source_hash,c.kind,s,t,h,tuple(o),reason)
def field(c):
 p=dict(c.payload); f=SemanticFieldV0.build(tuple((str(x[0]),int(x[1])) for x in p.get("declarations",())),tuple(FactV0(str(x["relation"]),tuple(x.get("arguments",()))) for x in p.get("facts",()))); return R(c,"EXACT","TEV.SemanticFieldV0",f.field_hash),f
def transformation(c):
 p=dict(c.payload); ops=tuple(RuleOpV0(str(x["opcode"]),dict(x.get("payload",{}))) for x in p.get("operations",())); effects=tuple(EffectAtomV0(str(x["domain"]),str(x["resource"]),str(x["mode"]),payload=tuple(x.get("payload",())),temporal=str(x.get("temporal","unknown")),recoverability=str(x.get("recoverability","unknown")),exposure=str(x.get("exposure","none"))) for x in p.get("effects",())); r=rule_field(c.identifier,ops,effects); return R(c,"EXACT","TEV.RuleField",r.field_hash),r
def center(c):
 p=dict(c.payload); ks=("center_id","view_hash","knowledge_hash","authority_hash","frame_hash","policy_hash");
 if any(k not in p for k in ks): raise ValueError("center fields")
 v=CenterContextV0(*(str(p[k]) for k in ks)); h=canonical_hash({"schema":"TEV_SCRIPT_SEMANTIC_CONTEXT_V0",**{k:str(p[k]) for k in ks}}); return R(c,"DERIVED","TEV.CenterContextV0",h,("center_components_are_evidence_bound",)),v,h
def evidence(c):
 p=dict(c.payload); f=evidence_field(tuple(tuple(x) for x in p.get("rows",())),tuple(tuple(x) for x in p.get("dependencies",())),tuple(tuple(x) for x in p.get("unknowns",())),tuple(tuple(x) for x in p.get("invalidated",()))); return R(c,"EXACT","TEV.EvidenceField",f.field_hash),f
def observation(c):
 p=dict(c.payload); cap=str(p["capability"]); args=tuple(p.get("arguments",())); m=str(p.get("external_mode","read")); tm=str(p.get("temporal","unknown")); eff=(EffectAtomV0("knowledge",cap,"read",payload=args,temporal=tm,exposure="acquired"),EffectAtomV0("external",cap,m,payload=args,temporal=tm,recoverability="irreversible" if m=="consume" else "unknown")); op={"capability":cap,"arguments":list(args)};
 if "target_relation" in p: op.update(target_relation=str(p["target_relation"]),target_prefix=list(p.get("target_prefix",())))
 r=rule_field(c.identifier,(RuleOpV0("observe",op),),eff); return R(c,"DERIVED","TEV.ObservationRule",r.field_hash,("provider_or_model_required",)),r
def laws(c):
 out={}; rows=[]
 for x in dict(c.payload).get("domains",()):
  l=DomainLawV0(str(x["domain"]),bool(x.get("complete",False)),bool(x.get("snapshot_reads_commute",False)),bool(x.get("stable_reads_commute",False)),tuple(tuple(y) for y in x.get("explicit_commuting_modes",()))); out[l.domain]=l; rows.append({"domain":l.domain,"complete":l.complete,"snapshot_reads_commute":l.snapshot_reads_commute,"stable_reads_commute":l.stable_reads_commute,"explicit_commuting_modes":[list(y) for y in l.explicit_commuting_modes]})
 h=canonical_hash({"schema":"TEV_SCRIPT_SEMANTIC_LAW_CONTEXT_V0","laws":sorted(rows,key=lambda x:x["domain"])}); return R(c,"DERIVED","TEV.DomainLawContext",h,("law_truth_requires_independent_justification",)),out,h
def translate(c):
 if c.kind=="field": return field(c)[0]
 if c.kind=="transformation": return transformation(c)[0]
 if c.kind=="center": return center(c)[0]
 if c.kind=="evidence": return evidence(c)[0]
 if c.kind=="observation": return observation(c)[0]
 if c.kind=="environment_laws": return laws(c)[0]
 if c.kind in {"evaluate","project","prepare","replay","commit"}: return R(c,"DERIVED","TEV.ApplicationMode."+c.kind,canonical_hash({"schema":"TEV_APPLICATION_MODE_CORRESPONDENCE_V0","mode":c.kind}),("commit_requires_prepared_outcome",) if c.kind=="commit" else ())
 if c.kind=="actual_world": return R(c,"OUT_OF_SCOPE",o=("represent_via_observation_or_model",),reason="external_reality_is_not_a_semantic_field")
 if c.kind=="truth_authority": return R(c,"REJECT",o=("verifier_and_trust_policy_required",),reason="data_cannot_self_authenticate_truth")
 if c.kind=="continuum": return R(c,"PARTIAL","TEV.AbstractOrApproximateField",o=("computable_abstraction_required","judgment_preservation_required"),reason="continuum_not_finitely_materialized")
 if c.kind=="unstratified_self_reference": return R(c,"REJECT",o=("higher_stratum_verifier_required",),reason="same_stratum_self_certification_forbidden")
 if c.kind=="omniscient_center": return R(c,"PARTIAL","TEV.CenterContextV0",o=("knowledge_and_authority_must_be_explicit","omniscience_not_assumed"),reason="center_is_bounded")
 return R(c,"OUT_OF_SCOPE",reason="no_correspondence_defined")
def observation_roles(c):
 from tev_script.semantic_apply_v0 import parse_rule
 _,r=observation(c); _,_,_,e=parse_rule(r); return derived_roles(e)
