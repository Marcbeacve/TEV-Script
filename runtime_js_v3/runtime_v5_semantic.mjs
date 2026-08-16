#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const PROGRAM_SCHEMA = 'TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1';
const INSTRUCTION_SCHEMA = 'TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_INSTRUCTION_V1';
const CHECKPOINT_SCHEMA = 'TEV_SCRIPT_PROGRAM_IR_V5_PROCESS_CHECKPOINT_V1';
const FACT_SCHEMA = 'TEV_SCRIPT_MAX_V3_FIELD_FACT_V1';
const FIELD_SCHEMA = 'TEV_SCRIPT_MAX_V3_SEMANTIC_FIELD_V1';
const TRANSFORM_SCHEMA = 'TEV_SCRIPT_MAX_V3_FIELD_TRANSFORMATION_V1';
const APPLY_RECEIPT_SCHEMA = 'TEV_SCRIPT_MAX_V3_APPLY_RECEIPT_V1';
const EPOCH_SCHEMA = 'TEV_SCRIPT_OMEGA_EPOCH_IDENTITY_V1';
const CONTINUATION_SCHEMA = 'TEV_SCRIPT_OMEGA_CONTINUATION_RECEIPT_V1';
const QUANTUM_SCHEMA = 'TEV_SCRIPT_MAX_V3_QUANTUM_RESULT_V1';
const LANGUAGE_VERSION = '3.0.0';
const PROFILE = 'semantic_process';
const MAX_QUANTUM_STEPS = 1_000_000;
const MAX_INSTRUCTIONS = 65_536;
const ID_RE = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const SHA_RE = /^[0-9a-f]{64}$/;

class TevJsError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'TevJsError';
    this.code = code;
  }
}

function fail(code, message) { throw new TevJsError(code, message); }
function isPlainObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function requireObject(value, code, message) { if (!isPlainObject(value)) fail(code, message); return value; }
function requireFields(value, fields, code) {
  requireObject(value, code, 'object required');
  const keys = Object.keys(value).sort();
  const expected = [...fields].sort();
  if (keys.length !== expected.length || keys.some((k, i) => k !== expected[i])) fail(code, 'field set mismatch');
}
function sha(value, name, code='TEVS_JS_V3_HASH') { if (typeof value !== 'string' || !SHA_RE.test(value)) fail(code, `${name} must be lowercase 64-hex`); return value; }
function stableId(value, name, code='TEVS_JS_V3_ID') { if (typeof value !== 'string' || !ID_RE.test(value)) fail(code, `${name} is not a stable id`); return value; }
function nonnegativeInt(value, name, code='TEVS_JS_V3_INTEGER') { if (!Number.isSafeInteger(value) || Object.is(value, -0) || value < 0) fail(code, `${name} must be integer >= 0`); return value; }

// Strict JSON parser: duplicate keys, floats, negative zero and unsafe integers fail closed.
class StrictJsonParser {
  constructor(text) { this.text = text; this.i = 0; }
  parse() { this.ws(); const value = this.value(); this.ws(); if (this.i !== this.text.length) fail('TEVS_JS_JSON_TRAILING', 'trailing JSON data'); return value; }
  ws() { while (this.i < this.text.length && /[\x20\x09\x0a\x0d]/.test(this.text[this.i])) this.i++; }
  value() {
    this.ws();
    const ch = this.text[this.i];
    if (ch === '{') return this.object();
    if (ch === '[') return this.array();
    if (ch === '"') return this.string();
    if (ch === '-' || (ch >= '0' && ch <= '9')) return this.integer();
    for (const [token, value] of [['true', true], ['false', false], ['null', null]]) {
      if (this.text.startsWith(token, this.i)) { this.i += token.length; return value; }
    }
    fail('TEVS_JS_JSON_SYNTAX', `unexpected token at ${this.i}`);
  }
  object() {
    this.i++; this.ws(); const out = Object.create(null);
    if (this.text[this.i] === '}') { this.i++; return out; }
    while (true) {
      this.ws(); if (this.text[this.i] !== '"') fail('TEVS_JS_JSON_SYNTAX', 'object key must be string');
      const key = this.string();
      if (Object.prototype.hasOwnProperty.call(out, key)) fail('TEVS_JS_JSON_DUPLICATE_KEY', `duplicate key ${key}`);
      this.ws(); if (this.text[this.i++] !== ':') fail('TEVS_JS_JSON_SYNTAX', 'missing colon');
      out[key] = this.value(); this.ws();
      const ch = this.text[this.i++];
      if (ch === '}') break;
      if (ch !== ',') fail('TEVS_JS_JSON_SYNTAX', 'missing comma');
    }
    return out;
  }
  array() {
    this.i++; this.ws(); const out = [];
    if (this.text[this.i] === ']') { this.i++; return out; }
    while (true) {
      out.push(this.value()); this.ws();
      const ch = this.text[this.i++];
      if (ch === ']') break;
      if (ch !== ',') fail('TEVS_JS_JSON_SYNTAX', 'missing comma');
    }
    return out;
  }
  string() {
    const start = this.i; this.i++;
    let escape = false;
    while (this.i < this.text.length) {
      const code = this.text.charCodeAt(this.i);
      const ch = this.text[this.i++];
      if (!escape && ch === '"') {
        const token = this.text.slice(start, this.i);
        try { return JSON.parse(token); } catch { fail('TEVS_JS_JSON_STRING', 'invalid JSON string'); }
      }
      if (!escape && code < 0x20) fail('TEVS_JS_JSON_STRING', 'unescaped control character');
      if (!escape && ch === '\\') escape = true; else escape = false;
    }
    fail('TEVS_JS_JSON_STRING', 'unterminated string');
  }
  integer() {
    const start = this.i;
    if (this.text[this.i] === '-') this.i++;
    if (this.text[this.i] === '0') {
      this.i++;
      if (/[0-9]/.test(this.text[this.i] ?? '')) fail('TEVS_JS_JSON_NUMBER', 'leading zero');
    } else {
      if (!/[1-9]/.test(this.text[this.i] ?? '')) fail('TEVS_JS_JSON_NUMBER', 'invalid integer');
      while (/[0-9]/.test(this.text[this.i] ?? '')) this.i++;
    }
    if (/[.eE]/.test(this.text[this.i] ?? '')) fail('TEVS_JS_JSON_FLOAT_FORBIDDEN', 'floating JSON numbers are forbidden');
    const token = this.text.slice(start, this.i);
    if (token === '-0') fail('TEVS_JS_JSON_NEGATIVE_ZERO', 'negative zero forbidden');
    const value = Number(token);
    if (!Number.isSafeInteger(value)) fail('TEVS_JS_JSON_NUMBER_RANGE', 'integer exceeds portable safe range');
    return value;
  }
}
function parseStrictJson(text) { return new StrictJsonParser(text).parse(); }

function comparePythonStrings(a, b) {
  const aa = Array.from(a, ch => ch.codePointAt(0));
  const bb = Array.from(b, ch => ch.codePointAt(0));
  const n = Math.min(aa.length, bb.length);
  for (let i = 0; i < n; i++) if (aa[i] !== bb[i]) return aa[i] - bb[i];
  return aa.length - bb.length;
}
function escapeString(value) {
  let out = '"';
  for (let i = 0; i < value.length; i++) {
    const code = value.charCodeAt(i);
    if (code === 0x22) out += '\\"';
    else if (code === 0x5c) out += '\\\\';
    else if (code === 0x08) out += '\\b';
    else if (code === 0x0c) out += '\\f';
    else if (code === 0x0a) out += '\\n';
    else if (code === 0x0d) out += '\\r';
    else if (code === 0x09) out += '\\t';
    else if (code < 0x20 || code >= 0x80) out += `\\u${code.toString(16).padStart(4, '0')}`;
    else out += value[i];
  }
  return out + '"';
}
function canonicalJson(value) {
  if (value === null) return 'null';
  if (value === true) return 'true';
  if (value === false) return 'false';
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) fail('TEVS_JS_CANONICAL_INTEGER', 'canonical integers must be safe and not -0');
    return String(value);
  }
  if (typeof value === 'string') return escapeString(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (isPlainObject(value)) {
    const keys = Object.keys(value).sort(comparePythonStrings);
    return `{${keys.map(key => `${escapeString(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  fail('TEVS_JS_CANONICAL_VALUE', `unsupported canonical value ${typeof value}`);
}
function canonicalHash(value) { return createHash('sha256').update(canonicalJson(value), 'utf8').digest('hex'); }

function validateFact(raw) {
  requireFields(raw, ['relation', 'arguments', 'fact_hash'], 'TEVS_JS_V3_FACT_FIELDS');
  const relation = stableId(raw.relation, 'relation', 'TEVS_JS_V3_FACT_ID');
  if (!Array.isArray(raw.arguments)) fail('TEVS_JS_V3_FACT_ARGUMENTS', 'arguments must be array');
  const body = { relation, arguments: raw.arguments };
  const expected = canonicalHash(body);
  if (sha(raw.fact_hash, 'fact_hash') !== expected) fail('TEVS_JS_V3_FACT_HASH', 'fact hash mismatch');
  return { relation, arguments: raw.arguments, fact_hash: expected };
}
function validateField(raw) {
  requireFields(raw, ['schema', 'profile', 'facts', 'field_hash'], 'TEVS_JS_V3_FIELD_FIELDS');
  if (raw.schema !== FIELD_SCHEMA) fail('TEVS_JS_V3_FIELD_SCHEMA', 'field schema mismatch');
  const profile = stableId(raw.profile, 'profile', 'TEVS_JS_V3_FIELD_PROFILE');
  if (!Array.isArray(raw.facts)) fail('TEVS_JS_V3_FIELD_FACTS', 'facts must be array');
  const facts = raw.facts.map(validateFact);
  if (new Set(facts.map(f => f.fact_hash)).size !== facts.length) fail('TEVS_JS_V3_FIELD_DUPLICATE', 'duplicate fact');
  const ordered = [...facts].sort((a, b) => a.fact_hash.localeCompare(b.fact_hash));
  if (facts.some((f, i) => f.fact_hash !== ordered[i].fact_hash)) fail('TEVS_JS_V3_FIELD_ORDER', 'facts not canonical order');
  const body = { schema: FIELD_SCHEMA, profile, facts: ordered };
  const expected = canonicalHash(body);
  if (sha(raw.field_hash, 'field_hash') !== expected) fail('TEVS_JS_V3_FIELD_HASH', 'field hash mismatch');
  return { ...body, field_hash: expected };
}
function validateTransformation(raw) {
  requireFields(raw, ['schema','transformation_id','required_before_hash','result_profile','remove_fact_hashes','add_facts','effect_set_hash','resource_vector_hash','proof_requirement_hashes','transformation_hash'], 'TEVS_JS_V3_TRANSFORM_FIELDS');
  if (raw.schema !== TRANSFORM_SCHEMA) fail('TEVS_JS_V3_TRANSFORM_SCHEMA', 'transformation schema mismatch');
  const transformation_id = stableId(raw.transformation_id, 'transformation_id', 'TEVS_JS_V3_TRANSFORM_ID');
  const required_before_hash = raw.required_before_hash === null ? null : sha(raw.required_before_hash, 'required_before_hash');
  const result_profile = raw.result_profile === null ? null : stableId(raw.result_profile, 'result_profile', 'TEVS_JS_V3_TRANSFORM_PROFILE');
  if (!Array.isArray(raw.remove_fact_hashes) || !Array.isArray(raw.add_facts) || !Array.isArray(raw.proof_requirement_hashes)) fail('TEVS_JS_V3_TRANSFORM_ARRAY', 'malformed transformation arrays');
  const removes = raw.remove_fact_hashes.map(x => sha(x, 'remove_fact_hash'));
  if (new Set(removes).size !== removes.length || removes.some((x, i) => i && removes[i-1] > x)) fail('TEVS_JS_V3_TRANSFORM_ORDER', 'remove hashes not sorted unique');
  const adds = raw.add_facts.map(validateFact);
  if (new Set(adds.map(x => x.fact_hash)).size !== adds.length || adds.some((x, i) => i && adds[i-1].fact_hash > x.fact_hash)) fail('TEVS_JS_V3_TRANSFORM_ORDER', 'add facts not sorted unique');
  if (adds.some(x => removes.includes(x.fact_hash))) fail('TEVS_JS_V3_TRANSFORM_COLLISION', 'remove/add collision');
  const proofs = raw.proof_requirement_hashes.map(x => sha(x, 'proof_requirement_hash'));
  if (new Set(proofs).size !== proofs.length || proofs.some((x, i) => i && proofs[i-1] > x)) fail('TEVS_JS_V3_TRANSFORM_ORDER', 'proof hashes not sorted unique');
  const effect_set_hash = sha(raw.effect_set_hash, 'effect_set_hash');
  const resource_vector_hash = sha(raw.resource_vector_hash, 'resource_vector_hash');
  const body = { schema: TRANSFORM_SCHEMA, transformation_id, required_before_hash, result_profile, remove_fact_hashes: removes, add_facts: adds, effect_set_hash, resource_vector_hash, proof_requirement_hashes: proofs };
  const expected = canonicalHash(body);
  if (sha(raw.transformation_hash, 'transformation_hash') !== expected) fail('TEVS_JS_V3_TRANSFORM_HASH', 'transformation hash mismatch');
  return { ...body, transformation_hash: expected };
}
function validateInstruction(raw) {
  requireFields(raw, ['schema','kind','transformation_hash','next_pc','fact_hash','present_pc','absent_pc','target_pc','instruction_hash'], 'TEVS_JS_V3_INSTRUCTION_FIELDS');
  if (raw.schema !== INSTRUCTION_SCHEMA) fail('TEVS_JS_V3_INSTRUCTION_SCHEMA', 'instruction schema mismatch');
  const kind = raw.kind;
  if (!['apply','branch_fact','jump','halt'].includes(kind)) fail('TEVS_JS_V3_INSTRUCTION_KIND', 'unknown instruction');
  let transformation_hash=null,next_pc=null,fact_hash=null,present_pc=null,absent_pc=null,target_pc=null;
  if (kind === 'apply') { transformation_hash=sha(raw.transformation_hash,'transformation_hash'); next_pc=nonnegativeInt(raw.next_pc,'next_pc'); }
  else if (kind === 'branch_fact') { fact_hash=sha(raw.fact_hash,'fact_hash'); present_pc=nonnegativeInt(raw.present_pc,'present_pc'); absent_pc=nonnegativeInt(raw.absent_pc,'absent_pc'); }
  else if (kind === 'jump') target_pc=nonnegativeInt(raw.target_pc,'target_pc');
  const body={schema:INSTRUCTION_SCHEMA,kind,transformation_hash,next_pc,fact_hash,present_pc,absent_pc,target_pc};
  const expected=canonicalHash(body);
  if (sha(raw.instruction_hash,'instruction_hash')!==expected) fail('TEVS_JS_V3_INSTRUCTION_HASH','instruction hash mismatch');
  return {...body,instruction_hash:expected};
}
function validateProgram(raw) {
  requireFields(raw, ['schema','language_version','profile','program_id','source_semantic_hash','initial_field','transformations','instructions','entry_pc','quantum_step_limit','authority_hash','program_hash'], 'TEVS_JS_V3_PROGRAM_FIELDS');
  if (raw.schema!==PROGRAM_SCHEMA || raw.language_version!==LANGUAGE_VERSION || raw.profile!==PROFILE) fail('TEVS_JS_V3_PROGRAM_PROFILE','unsupported Program IR V5 profile');
  const program_id=stableId(raw.program_id,'program_id','TEVS_JS_V3_PROGRAM_ID');
  const source_semantic_hash=sha(raw.source_semantic_hash,'source_semantic_hash');
  const authority_hash=sha(raw.authority_hash,'authority_hash');
  const initial_field=validateField(raw.initial_field);
  if (!Array.isArray(raw.transformations)||!Array.isArray(raw.instructions)) fail('TEVS_JS_V3_PROGRAM_ARRAY','program tables must be arrays');
  const transformations=raw.transformations.map(validateTransformation);
  if (transformations.some(t=>t.proof_requirement_hashes.length)) fail('TEVS_JS_V3_PROGRAM_PROOF_OPEN','proof-open transformation is not executable');
  if (new Set(transformations.map(t=>t.transformation_hash)).size!==transformations.length) fail('TEVS_JS_V3_PROGRAM_TRANSFORM_DUP','duplicate transformation');
  const ordered=[...transformations].sort((a,b)=>a.transformation_hash.localeCompare(b.transformation_hash));
  if (transformations.some((t,i)=>t.transformation_hash!==ordered[i].transformation_hash)) fail('TEVS_JS_V3_PROGRAM_TRANSFORM_ORDER','transformation table not canonical');
  const instructions=raw.instructions.map(validateInstruction);
  if (!instructions.length||instructions.length>MAX_INSTRUCTIONS) fail('TEVS_JS_V3_PROGRAM_INSTRUCTIONS','instruction count outside bound');
  const entry_pc=nonnegativeInt(raw.entry_pc,'entry_pc'); if(entry_pc>=instructions.length) fail('TEVS_JS_V3_PROGRAM_ENTRY','entry outside table');
  const quantum_step_limit=nonnegativeInt(raw.quantum_step_limit,'quantum_step_limit'); if(quantum_step_limit<1||quantum_step_limit>MAX_QUANTUM_STEPS) fail('TEVS_JS_V3_PROGRAM_QUANTUM','quantum bound outside range');
  const known=new Set(transformations.map(t=>t.transformation_hash));
  for(const ins of instructions){
    for(const pc of [ins.next_pc,ins.present_pc,ins.absent_pc,ins.target_pc]) if(pc!==null&&pc>=instructions.length) fail('TEVS_JS_V3_PROGRAM_TARGET','target outside table');
    if(ins.kind==='apply'&&!known.has(ins.transformation_hash)) fail('TEVS_JS_V3_PROGRAM_TRANSFORM_UNKNOWN','unknown transformation');
  }
  const body={schema:PROGRAM_SCHEMA,language_version:LANGUAGE_VERSION,profile:PROFILE,program_id,source_semantic_hash,initial_field,transformations,instructions,entry_pc,quantum_step_limit,authority_hash};
  const expected=canonicalHash(body);
  if(sha(raw.program_hash,'program_hash','TEVS_JS_V3_PROGRAM_HASH')!==expected) fail('TEVS_JS_V3_PROGRAM_HASH','program hash mismatch');
  return {...body,program_hash:expected};
}
function processStateHash(program_hash,field_hash,pc){ return canonicalHash({program_hash:sha(program_hash,'program_hash'),field_hash:sha(field_hash,'field_hash'),pc:nonnegativeInt(pc,'pc')}); }
function validateContinuation(raw){
  requireFields(raw,['schema','epoch_hash','epoch_index','previous_continuation_hash','result_hash','state_hash','observations_hash','effects_hash','resources_hash','continuation_hash'],'TEVS_JS_V3_CONTINUATION_FIELDS');
  if(raw.schema!==CONTINUATION_SCHEMA) fail('TEVS_JS_V3_CONTINUATION_SCHEMA','continuation schema mismatch');
  const epoch_index=nonnegativeInt(raw.epoch_index,'epoch_index');
  const previous_continuation_hash=raw.previous_continuation_hash===null?null:sha(raw.previous_continuation_hash,'previous_continuation_hash');
  if(epoch_index===0&&previous_continuation_hash!==null) fail('TEVS_JS_V3_CONTINUATION_PREVIOUS','epoch zero has previous');
  if(epoch_index>0&&previous_continuation_hash===null) fail('TEVS_JS_V3_CONTINUATION_PREVIOUS','resumed epoch lacks previous');
  const body={schema:CONTINUATION_SCHEMA,epoch_hash:sha(raw.epoch_hash,'epoch_hash'),epoch_index,previous_continuation_hash,result_hash:sha(raw.result_hash,'result_hash'),state_hash:sha(raw.state_hash,'state_hash'),observations_hash:sha(raw.observations_hash,'observations_hash'),effects_hash:sha(raw.effects_hash,'effects_hash'),resources_hash:sha(raw.resources_hash,'resources_hash')};
  const expected=canonicalHash(body); if(sha(raw.continuation_hash,'continuation_hash')!==expected) fail('TEVS_JS_V3_CONTINUATION_HASH','continuation hash mismatch');
  return {...body,continuation_hash:expected};
}
function checkpointBody(program_hash,field,pc,next_epoch_index,previous_continuation,halted){ return {schema:CHECKPOINT_SCHEMA,program_hash,field,pc,next_epoch_index,previous_continuation,halted}; }
function buildCheckpoint(program,{field,pc,next_epoch_index,previous_continuation,halted}){
  field=validateField(field); pc=nonnegativeInt(pc,'pc'); next_epoch_index=nonnegativeInt(next_epoch_index,'next_epoch_index');
  if(pc>=program.instructions.length) fail('TEVS_JS_V3_CHECKPOINT_PC','checkpoint pc outside program');
  if(typeof halted!=='boolean') fail('TEVS_JS_V3_CHECKPOINT_HALTED','halted must be boolean');
  let previous=null;
  if(next_epoch_index===0){ if(previous_continuation!==null) fail('TEVS_JS_V3_CHECKPOINT_PREVIOUS','epoch zero checkpoint cannot have continuation'); }
  else { if(previous_continuation===null) fail('TEVS_JS_V3_CHECKPOINT_PREVIOUS','resumed checkpoint requires continuation'); previous=validateContinuation(previous_continuation); if(previous.epoch_index!==next_epoch_index-1) fail('TEVS_JS_V3_CHECKPOINT_EPOCH','continuation epoch mismatch'); if(previous.state_hash!==processStateHash(program.program_hash,field.field_hash,pc)) fail('TEVS_JS_V3_CHECKPOINT_STATE','continuation state mismatch'); }
  if(halted&&program.instructions[pc].kind!=='halt') fail('TEVS_JS_V3_CHECKPOINT_HALTED','halted checkpoint must point at halt');
  const body=checkpointBody(program.program_hash,field,pc,next_epoch_index,previous,halted);
  return {...body,checkpoint_hash:canonicalHash(body)};
}
function validateCheckpoint(program,raw){
  requireFields(raw,['schema','program_hash','field','pc','next_epoch_index','previous_continuation','halted','checkpoint_hash'],'TEVS_JS_V3_CHECKPOINT_FIELDS');
  if(raw.schema!==CHECKPOINT_SCHEMA) fail('TEVS_JS_V3_CHECKPOINT_SCHEMA','checkpoint schema mismatch');
  if(sha(raw.program_hash,'program_hash')!==program.program_hash) fail('TEVS_JS_V3_CHECKPOINT_PROGRAM','checkpoint program mismatch');
  const expected=buildCheckpoint(program,{field:raw.field,pc:raw.pc,next_epoch_index:raw.next_epoch_index,previous_continuation:raw.previous_continuation,halted:raw.halted});
  if(sha(raw.checkpoint_hash,'checkpoint_hash')!==expected.checkpoint_hash) fail('TEVS_JS_V3_CHECKPOINT_HASH','checkpoint hash mismatch');
  return expected;
}
function buildField(facts,profile){
  profile=stableId(profile,'profile'); const checked=facts.map(validateFact); if(new Set(checked.map(f=>f.fact_hash)).size!==checked.length) fail('TEVS_JS_V3_FIELD_DUPLICATE','duplicate fact'); const ordered=[...checked].sort((a,b)=>a.fact_hash.localeCompare(b.fact_hash)); const body={schema:FIELD_SCHEMA,profile,facts:ordered}; return {...body,field_hash:canonicalHash(body)};
}
function applyTransformation(before,tx){
  before=validateField(before); tx=validateTransformation(tx); if(tx.required_before_hash!==null&&tx.required_before_hash!==before.field_hash) fail('TEVS_JS_V3_APPLY_BEFORE','before pin mismatch');
  const remaining=new Map(before.facts.map(f=>[f.fact_hash,f]));
  for(const hash of tx.remove_fact_hashes){ if(!remaining.has(hash)) fail('TEVS_JS_V3_APPLY_REMOVE','remove target absent'); remaining.delete(hash); }
  for(const fact of tx.add_facts){ if(remaining.has(fact.fact_hash)) fail('TEVS_JS_V3_APPLY_ADD','addition duplicates remaining fact'); remaining.set(fact.fact_hash,fact); }
  const after=buildField([...remaining.values()],tx.result_profile===null?before.profile:tx.result_profile);
  const status=tx.proof_requirement_hashes.length?'PROOF_REQUIRED':'PASS';
  const body={schema:APPLY_RECEIPT_SCHEMA,before_field_hash:before.field_hash,transformation_hash:tx.transformation_hash,after_field_hash:after.field_hash,effect_set_hash:tx.effect_set_hash,resource_vector_hash:tx.resource_vector_hash,proof_requirement_hashes:tx.proof_requirement_hashes,status};
  const receipt={...body,receipt_hash:canonicalHash(body)}; return {after,receipt};
}
function epochIdentity({epoch_index,computation_hash,input_state_hash,authority_hash,previous_continuation_hash}){
  epoch_index=nonnegativeInt(epoch_index,'epoch_index'); computation_hash=sha(computation_hash,'computation_hash'); input_state_hash=sha(input_state_hash,'input_state_hash'); authority_hash=sha(authority_hash,'authority_hash');
  if(epoch_index===0){if(previous_continuation_hash!==null)fail('TEVS_JS_V3_EPOCH_PREVIOUS','epoch zero has previous');} else previous_continuation_hash=sha(previous_continuation_hash,'previous_continuation_hash');
  const body={schema:EPOCH_SCHEMA,epoch_index,computation_hash,input_state_hash,authority_hash,previous_continuation_hash}; return {...body,epoch_hash:canonicalHash(body)};
}
function continuationReceipt({epoch,result_hash,state_hash,observations_hash,effects_hash,resources_hash}){
  const body={schema:CONTINUATION_SCHEMA,epoch_hash:epoch.epoch_hash,epoch_index:epoch.epoch_index,previous_continuation_hash:epoch.previous_continuation_hash,result_hash:sha(result_hash,'result_hash'),state_hash:sha(state_hash,'state_hash'),observations_hash:sha(observations_hash,'observations_hash'),effects_hash:sha(effects_hash,'effects_hash'),resources_hash:sha(resources_hash,'resources_hash')}; return {...body,continuation_hash:canonicalHash(body)};
}
function resultSemanticHash(status,field_hash,pc){return canonicalHash({status,field_hash,pc});}
function runQuantum(programRaw,checkpointRaw){
  const program=validateProgram(programRaw); const checkpoint=validateCheckpoint(program,checkpointRaw); if(checkpoint.halted) fail('TEVS_JS_V3_RUNTIME_HALTED','halted checkpoint cannot resume');
  const input_state_hash=processStateHash(program.program_hash,checkpoint.field.field_hash,checkpoint.pc); const previous_hash=checkpoint.previous_continuation===null?null:checkpoint.previous_continuation.continuation_hash;
  const epoch=epochIdentity({epoch_index:checkpoint.next_epoch_index,computation_hash:program.program_hash,input_state_hash,authority_hash:program.authority_hash,previous_continuation_hash:previous_hash});
  let field=checkpoint.field; let pc=checkpoint.pc; let steps_used=0; const applied=[]; const effect_hashes=[]; let status='SUSPENDED'; const txs=new Map(program.transformations.map(t=>[t.transformation_hash,t]));
  while(steps_used<program.quantum_step_limit){ const ins=program.instructions[pc]; steps_used++;
    if(ins.kind==='apply'){const {after,receipt}=applyTransformation(field,txs.get(ins.transformation_hash)); if(receipt.status!=='PASS')fail('TEVS_JS_V3_RUNTIME_APPLY_OPEN','proof-open Apply'); field=after; applied.push(receipt.receipt_hash); effect_hashes.push(receipt.effect_set_hash); pc=ins.next_pc;}
    else if(ins.kind==='branch_fact'){const present=field.facts.some(f=>f.fact_hash===ins.fact_hash); pc=present?ins.present_pc:ins.absent_pc;}
    else if(ins.kind==='jump'){pc=ins.target_pc;}
    else {status='HALTED';break;}
  }
  const result_hash=resultSemanticHash(status,field.field_hash,pc); const state_hash=processStateHash(program.program_hash,field.field_hash,pc);
  const continuation=continuationReceipt({epoch,result_hash,state_hash,observations_hash:canonicalHash([]),effects_hash:canonicalHash(effect_hashes),resources_hash:canonicalHash({steps_used})});
  const next_checkpoint=buildCheckpoint(program,{field,pc,next_epoch_index:checkpoint.next_epoch_index+1,previous_continuation:continuation,halted:status==='HALTED'});
  const body={schema:QUANTUM_SCHEMA,program_hash:program.program_hash,epoch,status,steps_used,field,pc,apply_receipt_hashes:applied,result_hash,continuation,next_checkpoint};
  return {...body,quantum_hash:canonicalHash(body)};
}

function main(){
  try{
    const text=readFileSync(0,'utf8'); const request=parseStrictJson(text); requireFields(request,['program','checkpoint'],'TEVS_JS_V3_REQUEST_FIELDS'); const result=runQuantum(request.program,request.checkpoint); process.stdout.write(canonicalJson(result)+'\n');
  }catch(error){
    const code=error instanceof TevJsError?error.code:'TEVS_JS_V3_INTERNAL'; const message=error instanceof Error?error.message:String(error); process.stderr.write(`TEVS_JS_V3_ERROR:${code}:${message}\n`); process.exitCode=1;
  }
}

if(import.meta.url===new URL(`file://${process.argv[1]}`).href) main();

export { canonicalJson, canonicalHash, parseStrictJson, runQuantum, validateProgram, validateCheckpoint };
