import { canonicalHash, canonicalJson } from "../javascript/src/canonical.mjs";

export const PROGRAM_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1";
export const UNIT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1";
export const INSTRUCTION_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_INSTRUCTION_V1";
export const PROOF_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1";
export const CHECKPOINT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CHECKPOINT_V1";
export const QUANTUM_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_QUANTUM_RESULT_V1";
export const FIELD_SCHEMA = "TEV_SCRIPT_MAX_V3_SEMANTIC_FIELD_V1";
export const TRANSFORM_SCHEMA = "TEV_SCRIPT_MAX_V3_FIELD_TRANSFORMATION_V1";
export const APPLY_RECEIPT_SCHEMA = "TEV_SCRIPT_MAX_V3_APPLY_RECEIPT_V1";
export const EPOCH_SCHEMA = "TEV_SCRIPT_OMEGA_EPOCH_IDENTITY_V1";
export const CONTINUATION_SCHEMA = "TEV_SCRIPT_OMEGA_CONTINUATION_RECEIPT_V1";

const ID_RE = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const SHA_RE = /^[0-9a-f]{64}$/;
const INSTRUCTION_KINDS = new Set(["apply", "branch_fact", "jump", "halt", "invoke_v4"]);

export class TevJsError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "TevJsError";
    this.code = code;
  }
}

export function fail(code, message) { throw new TevJsError(code, message); }
export function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
export function obj(value, code, message = "object required") { if (!plain(value)) fail(code, message); return value; }
export function requireFields(value, expected, code) {
  obj(value, code);
  const observed = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (observed.length !== wanted.length || observed.some((key, index) => key !== wanted[index])) fail(code, "field set mismatch");
}
export function sha(value, name, code = "TEVS_V31_JS_HASH") {
  if (typeof value !== "string" || !SHA_RE.test(value)) fail(code, `${name} must be lowercase 64-hex`);
  return value;
}
export function stable(value, name, code = "TEVS_V31_JS_ID") {
  if (typeof value !== "string" || !ID_RE.test(value)) fail(code, `${name} is not a stable id`);
  return value;
}
export function nonnegative(value, name, code = "TEVS_V31_JS_INTEGER") {
  if (!Number.isSafeInteger(value) || Object.is(value, -0) || value < 0) fail(code, `${name} must be an integer >= 0`);
  return value;
}
export function positiveBound(value, name, maximum = 1_000_000) {
  nonnegative(value, name, "TEVS_V31_BOUND");
  if (value < 1 || value > maximum) fail("TEVS_V31_BOUND", `${name} outside admitted bound`);
  return value;
}
export function sameJson(left, right) { return canonicalJson(left) === canonicalJson(right); }

export function validateFact(raw) {
  requireFields(raw, ["relation", "arguments", "fact_hash"], "TEVS_V31_FIELD_FACT");
  const relation = stable(raw.relation, "relation", "TEVS_V31_FIELD_FACT");
  if (!Array.isArray(raw.arguments)) fail("TEVS_V31_FIELD_FACT", "arguments must be an array");
  const expected = canonicalHash({ relation, arguments: raw.arguments });
  if (sha(raw.fact_hash, "fact_hash", "TEVS_V31_FIELD_FACT") !== expected) fail("TEVS_V31_FIELD_FACT", "fact hash mismatch");
  return { relation, arguments: raw.arguments, fact_hash: expected };
}

export function factValue(relation, argumentsList) {
  const rel = stable(relation, "relation", "TEVS_V31_FIELD_FACT");
  if (!Array.isArray(argumentsList)) fail("TEVS_V31_FIELD_FACT", "arguments required");
  const body = { relation: rel, arguments: argumentsList };
  return { ...body, fact_hash: canonicalHash(body) };
}

export function fieldValue(profile, factsInput) {
  const profileId = stable(profile, "profile", "TEVS_V31_FIELD");
  const facts = factsInput.map(validateFact);
  if (new Set(facts.map(item => item.fact_hash)).size !== facts.length) fail("TEVS_V31_FIELD", "duplicate fact");
  facts.sort((left, right) => left.fact_hash.localeCompare(right.fact_hash));
  const body = { schema: FIELD_SCHEMA, profile: profileId, facts };
  return { ...body, field_hash: canonicalHash(body) };
}

export function validateField(raw) {
  requireFields(raw, ["schema", "profile", "facts", "field_hash"], "TEVS_V31_FIELD");
  if (raw.schema !== FIELD_SCHEMA || !Array.isArray(raw.facts)) fail("TEVS_V31_FIELD", "field schema mismatch");
  const expected = fieldValue(raw.profile, raw.facts);
  if (sha(raw.field_hash, "field_hash", "TEVS_V31_FIELD") !== expected.field_hash) fail("TEVS_V31_FIELD", "field hash mismatch");
  if (raw.facts.some((fact, index) => fact.fact_hash !== expected.facts[index].fact_hash)) fail("TEVS_V31_FIELD", "fact order mismatch");
  return expected;
}

export function transformationValue(input) {
  const transformationId = stable(input.transformation_id, "transformation_id", "TEVS_V31_TRANSFORM");
  const required = input.required_before_hash === null ? null : sha(input.required_before_hash, "required_before_hash", "TEVS_V31_TRANSFORM");
  const resultProfile = input.result_profile === null ? null : stable(input.result_profile, "result_profile", "TEVS_V31_TRANSFORM");
  if (!Array.isArray(input.remove_fact_hashes) || !Array.isArray(input.add_facts) || !Array.isArray(input.proof_requirement_hashes)) fail("TEVS_V31_TRANSFORM", "transformation arrays malformed");
  const removes = [...input.remove_fact_hashes].map(item => sha(item, "remove_fact_hash", "TEVS_V31_TRANSFORM")).sort();
  if (new Set(removes).size !== removes.length) fail("TEVS_V31_TRANSFORM", "duplicate removals");
  const adds = input.add_facts.map(validateFact).sort((left, right) => left.fact_hash.localeCompare(right.fact_hash));
  if (new Set(adds.map(item => item.fact_hash)).size !== adds.length) fail("TEVS_V31_TRANSFORM", "duplicate additions");
  if (adds.some(item => removes.includes(item.fact_hash))) fail("TEVS_V31_TRANSFORM", "remove/add collision");
  const proofs = [...input.proof_requirement_hashes].map(item => sha(item, "proof_requirement_hash", "TEVS_V31_TRANSFORM")).sort();
  if (new Set(proofs).size !== proofs.length) fail("TEVS_V31_TRANSFORM", "duplicate proof requirements");
  const body = {
    schema: TRANSFORM_SCHEMA,
    transformation_id: transformationId,
    required_before_hash: required,
    result_profile: resultProfile,
    remove_fact_hashes: removes,
    add_facts: adds,
    effect_set_hash: sha(input.effect_set_hash, "effect_set_hash", "TEVS_V31_TRANSFORM"),
    resource_vector_hash: sha(input.resource_vector_hash, "resource_vector_hash", "TEVS_V31_TRANSFORM"),
    proof_requirement_hashes: proofs,
  };
  return { ...body, transformation_hash: canonicalHash(body) };
}

export function validateTransformation(raw) {
  requireFields(raw, ["schema", "transformation_id", "required_before_hash", "result_profile", "remove_fact_hashes", "add_facts", "effect_set_hash", "resource_vector_hash", "proof_requirement_hashes", "transformation_hash"], "TEVS_V31_TRANSFORM");
  if (raw.schema !== TRANSFORM_SCHEMA) fail("TEVS_V31_TRANSFORM", "transformation schema mismatch");
  const expected = transformationValue(raw);
  if (sha(raw.transformation_hash, "transformation_hash", "TEVS_V31_TRANSFORM") !== expected.transformation_hash) fail("TEVS_V31_TRANSFORM", "transformation hash mismatch");
  if (!sameJson(raw.remove_fact_hashes, expected.remove_fact_hashes) || !sameJson(raw.add_facts, expected.add_facts) || !sameJson(raw.proof_requirement_hashes, expected.proof_requirement_hashes)) fail("TEVS_V31_TRANSFORM", "transformation order mismatch");
  return expected;
}

export function applyTransformation(before, tx) {
  if (tx.required_before_hash !== null && tx.required_before_hash !== before.field_hash) fail("TEVS_V31_APPLY", "before-field pin mismatch");
  const remaining = new Map(before.facts.map(item => [item.fact_hash, item]));
  for (const hash of tx.remove_fact_hashes) {
    if (!remaining.has(hash)) fail("TEVS_V31_APPLY", "remove target absent");
    remaining.delete(hash);
  }
  for (const fact of tx.add_facts) {
    if (remaining.has(fact.fact_hash)) fail("TEVS_V31_APPLY", "add duplicates fact");
    remaining.set(fact.fact_hash, fact);
  }
  const after = fieldValue(tx.result_profile === null ? before.profile : tx.result_profile, [...remaining.values()]);
  const status = tx.proof_requirement_hashes.length ? "PROOF_REQUIRED" : "PASS";
  const receiptBody = {
    schema: APPLY_RECEIPT_SCHEMA,
    before_field_hash: before.field_hash,
    transformation_hash: tx.transformation_hash,
    after_field_hash: after.field_hash,
    effect_set_hash: tx.effect_set_hash,
    resource_vector_hash: tx.resource_vector_hash,
    proof_requirement_hashes: tx.proof_requirement_hashes,
    status,
  };
  return { after, receipt: { ...receiptBody, receipt_hash: canonicalHash(receiptBody) } };
}

function validateProof(raw, authority) {
  requireFields(raw, ["schema", "requirement_hash", "verification_receipt_hash", "verifier_identity_hash", "authority_hash", "status", "admission_hash"], "TEVS_V31_PROOF");
  if (raw.schema !== PROOF_SCHEMA || raw.status !== "VERIFIED") fail("TEVS_V31_PROOF", "proof admission shape mismatch");
  const body = {
    schema: PROOF_SCHEMA,
    requirement_hash: sha(raw.requirement_hash, "requirement_hash", "TEVS_V31_PROOF"),
    verification_receipt_hash: sha(raw.verification_receipt_hash, "verification_receipt_hash", "TEVS_V31_PROOF"),
    verifier_identity_hash: sha(raw.verifier_identity_hash, "verifier_identity_hash", "TEVS_V31_PROOF"),
    authority_hash: sha(raw.authority_hash, "authority_hash", "TEVS_V31_PROOF"),
    status: "VERIFIED",
  };
  const expected = canonicalHash(body);
  if (sha(raw.admission_hash, "admission_hash", "TEVS_V31_PROOF") !== expected) fail("TEVS_V31_PROOF_HASH", "proof admission hash mismatch");
  if (body.authority_hash !== authority) fail("TEVS_V31_PROOF_AUTHORITY", "proof authority mismatch");
  return { ...body, admission_hash: expected };
}

function validateInstruction(raw) {
  requireFields(raw, ["schema", "kind", "transformation_hash", "next_pc", "fact_hash", "present_pc", "absent_pc", "target_pc", "unit_hash", "result_relation", "instruction_hash"], "TEVS_V31_INSTRUCTION");
  if (raw.schema !== INSTRUCTION_SCHEMA || !INSTRUCTION_KINDS.has(raw.kind)) fail("TEVS_V31_INSTRUCTION", "instruction schema/kind mismatch");
  const body = { schema: INSTRUCTION_SCHEMA, kind: raw.kind, transformation_hash: null, next_pc: null, fact_hash: null, present_pc: null, absent_pc: null, target_pc: null, unit_hash: null, result_relation: null };
  if (raw.kind === "apply") { body.transformation_hash = sha(raw.transformation_hash, "transformation_hash", "TEVS_V31_INSTRUCTION"); body.next_pc = nonnegative(raw.next_pc, "next_pc", "TEVS_V31_INSTRUCTION"); }
  else if (raw.kind === "branch_fact") { body.fact_hash = sha(raw.fact_hash, "fact_hash", "TEVS_V31_INSTRUCTION"); body.present_pc = nonnegative(raw.present_pc, "present_pc", "TEVS_V31_INSTRUCTION"); body.absent_pc = nonnegative(raw.absent_pc, "absent_pc", "TEVS_V31_INSTRUCTION"); }
  else if (raw.kind === "jump") body.target_pc = nonnegative(raw.target_pc, "target_pc", "TEVS_V31_INSTRUCTION");
  else if (raw.kind === "invoke_v4") { body.unit_hash = sha(raw.unit_hash, "unit_hash", "TEVS_V31_INSTRUCTION"); body.result_relation = stable(raw.result_relation, "result_relation", "TEVS_V31_INSTRUCTION"); body.next_pc = nonnegative(raw.next_pc, "next_pc", "TEVS_V31_INSTRUCTION"); }
  const expected = canonicalHash(body);
  if (sha(raw.instruction_hash, "instruction_hash", "TEVS_V31_INSTRUCTION") !== expected) fail("TEVS_V31_INSTRUCTION_HASH", "instruction hash mismatch");
  return { ...body, instruction_hash: expected };
}

function embeddedProgramHash(raw) {
  obj(raw, "TEVS_V31_UNIT");
  const declared = sha(raw.program_ir_hash, "program_ir_hash", "TEVS_V31_UNIT");
  const body = { ...raw };
  delete body.program_ir_hash;
  const computed = canonicalHash(body);
  if (declared !== computed) fail("TEVS_V31_V4_UNIT_HASH", "embedded V4 program hash mismatch");
  return computed;
}

function validateUnit(raw) {
  requireFields(raw, ["schema", "unit_id", "profile", "program_ir_v4", "program_ir_hash", "unit_hash"], "TEVS_V31_UNIT");
  if (raw.schema !== UNIT_SCHEMA || !["pure", "recursive", "effects"].includes(raw.profile)) fail("TEVS_V31_UNIT", "unit shape/profile mismatch");
  const irHash = embeddedProgramHash(raw.program_ir_v4);
  if (sha(raw.program_ir_hash, "program_ir_hash", "TEVS_V31_UNIT") !== irHash) fail("TEVS_V31_UNIT_HASH", "unit program hash mismatch");
  const body = { schema: UNIT_SCHEMA, unit_id: stable(raw.unit_id, "unit_id", "TEVS_V31_UNIT"), profile: raw.profile, program_ir_hash: irHash };
  const expected = canonicalHash(body);
  if (sha(raw.unit_hash, "unit_hash", "TEVS_V31_UNIT") !== expected) fail("TEVS_V31_UNIT_HASH", "unit hash mismatch");
  return { ...raw, program_ir_hash: irHash, unit_hash: expected };
}

export function validateProgram(raw) {
  requireFields(raw, ["schema", "language_version", "profile", "program_id", "source_semantic_hash", "initial_field", "transformations", "v4_units", "proof_admissions", "instructions", "entry_pc", "quantum_step_limit", "authority_hash", "program_hash"], "TEVS_V31_PROGRAM");
  if (raw.schema !== PROGRAM_SCHEMA || raw.language_version !== "3.1.0" || raw.profile !== "total_core") fail("TEVS_V31_PROGRAM", "program schema/version/profile mismatch");
  const authority = sha(raw.authority_hash, "authority_hash", "TEVS_V31_PROGRAM");
  const initialField = validateField(raw.initial_field);
  if (!Array.isArray(raw.transformations) || !Array.isArray(raw.v4_units) || !Array.isArray(raw.proof_admissions) || !Array.isArray(raw.instructions)) fail("TEVS_V31_PROGRAM", "program tables must be arrays");
  const transformations = raw.transformations.map(validateTransformation);
  const units = raw.v4_units.map(validateUnit);
  const proofs = raw.proof_admissions.map(item => validateProof(item, authority));
  const instructions = raw.instructions.map(validateInstruction);
  const entryPc = nonnegative(raw.entry_pc, "entry_pc", "TEVS_V31_PROGRAM");
  const quantumStepLimit = positiveBound(raw.quantum_step_limit, "quantum_step_limit");
  if (entryPc >= instructions.length) fail("TEVS_V31_PROGRAM", "entry pc outside program");
  const txByHash = Object.fromEntries(transformations.map(item => [item.transformation_hash, item]));
  const unitByHash = Object.fromEntries(units.map(item => [item.unit_hash, item]));
  const admitted = new Set(proofs.map(item => item.requirement_hash));
  for (const instruction of instructions) {
    for (const target of [instruction.next_pc, instruction.present_pc, instruction.absent_pc, instruction.target_pc]) if (target !== null && target >= instructions.length) fail("TEVS_V31_PROGRAM", "target pc outside program");
    if (instruction.kind === "apply") {
      const tx = txByHash[instruction.transformation_hash];
      if (!tx) fail("TEVS_V31_PROGRAM", "unknown transformation");
      if (tx.proof_requirement_hashes.some(item => !admitted.has(item))) fail("TEVS_V31_PROOF_REQUIRED", "missing exact proof admission");
    }
    if (instruction.kind === "invoke_v4" && !unitByHash[instruction.unit_hash]) fail("TEVS_V31_UNIT", "unknown unit");
  }
  const body = { ...raw };
  delete body.program_hash;
  const expected = canonicalHash(body);
  if (sha(raw.program_hash, "program_hash", "TEVS_V31_PROGRAM") !== expected) fail("TEVS_V31_PROGRAM_HASH", "program hash mismatch");
  return { ...raw, initial_field: initialField, transformations, v4_units: units, proof_admissions: proofs, instructions, program_hash: expected, txByHash, unitByHash };
}

export function validateContinuation(raw) {
  requireFields(raw, ["schema", "epoch_hash", "epoch_index", "previous_continuation_hash", "result_hash", "state_hash", "observations_hash", "effects_hash", "resources_hash", "continuation_hash"], "TEVS_V31_CONTINUATION");
  if (raw.schema !== CONTINUATION_SCHEMA) fail("TEVS_V31_CONTINUATION", "continuation schema mismatch");
  const index = nonnegative(raw.epoch_index, "epoch_index", "TEVS_V31_CONTINUATION");
  const previous = raw.previous_continuation_hash === null ? null : sha(raw.previous_continuation_hash, "previous_continuation_hash", "TEVS_V31_CONTINUATION");
  if ((index === 0 && previous !== null) || (index > 0 && previous === null)) fail("TEVS_V31_CONTINUATION", "previous continuation contract mismatch");
  const body = { schema: CONTINUATION_SCHEMA, epoch_hash: sha(raw.epoch_hash, "epoch_hash", "TEVS_V31_CONTINUATION"), epoch_index: index, previous_continuation_hash: previous, result_hash: sha(raw.result_hash, "result_hash", "TEVS_V31_CONTINUATION"), state_hash: sha(raw.state_hash, "state_hash", "TEVS_V31_CONTINUATION"), observations_hash: sha(raw.observations_hash, "observations_hash", "TEVS_V31_CONTINUATION"), effects_hash: sha(raw.effects_hash, "effects_hash", "TEVS_V31_CONTINUATION"), resources_hash: sha(raw.resources_hash, "resources_hash", "TEVS_V31_CONTINUATION") };
  const expected = canonicalHash(body);
  if (sha(raw.continuation_hash, "continuation_hash", "TEVS_V31_CONTINUATION") !== expected) fail("TEVS_V31_CONTINUATION_HASH", "continuation hash mismatch");
  return { ...body, continuation_hash: expected };
}

export function stateHash(programHash, fieldHash, pc) { return canonicalHash({ program_hash: programHash, field_hash: fieldHash, pc }); }

export function checkpointValue(program, field, pc, nextEpoch, previous, halted) {
  if (!Number.isSafeInteger(pc) || pc < 0 || pc >= program.instructions.length) fail("TEVS_V31_RUNTIME_CHECKPOINT_PC", "CHECKPOINT pc outside program");
  if (!Number.isSafeInteger(nextEpoch) || nextEpoch < 0) fail("TEVS_V31_RUNTIME_CHECKPOINT_EPOCH", "CHECKPOINT epoch invalid");
  if (halted && program.instructions[pc].kind !== "halt") fail("TEVS_V31_RUNTIME_CHECKPOINT_HALTED", "CHECKPOINT halted pc must be halt");
  if (nextEpoch === 0 && previous !== null) fail("TEVS_V31_RUNTIME_CHECKPOINT_PREVIOUS", "CHECKPOINT epoch zero has previous");
  if (nextEpoch > 0) {
    if (previous === null) fail("TEVS_V31_RUNTIME_CHECKPOINT_PREVIOUS", "CHECKPOINT resume requires continuation");
    if (previous.epoch_index !== nextEpoch - 1) fail("TEVS_V31_RUNTIME_CHECKPOINT_EPOCH", "CHECKPOINT continuation epoch mismatch");
    if (previous.state_hash !== stateHash(program.program_hash, field.field_hash, pc)) fail("TEVS_V31_RUNTIME_CHECKPOINT_STATE", "CHECKPOINT continuation state mismatch");
  }
  const body = { schema: CHECKPOINT_SCHEMA, program_hash: program.program_hash, field, pc, next_epoch_index: nextEpoch, previous_continuation: previous, halted };
  return { ...body, checkpoint_hash: canonicalHash(body) };
}

export function validateCheckpoint(program, raw) {
  requireFields(raw, ["schema", "program_hash", "field", "pc", "next_epoch_index", "previous_continuation", "halted", "checkpoint_hash"], "TEVS_V31_RUNTIME_CHECKPOINT");
  if (raw.schema !== CHECKPOINT_SCHEMA || raw.program_hash !== program.program_hash || typeof raw.halted !== "boolean") fail("TEVS_V31_RUNTIME_CHECKPOINT", "CHECKPOINT shape/program mismatch");
  const pc = nonnegative(raw.pc, "pc", "TEVS_V31_RUNTIME_CHECKPOINT");
  const nextEpoch = nonnegative(raw.next_epoch_index, "next_epoch_index", "TEVS_V31_RUNTIME_CHECKPOINT");
  const field = validateField(raw.field);
  const previous = raw.previous_continuation === null ? null : validateContinuation(raw.previous_continuation);
  const expected = checkpointValue(program, field, pc, nextEpoch, previous, raw.halted);
  if (sha(raw.checkpoint_hash, "checkpoint_hash", "TEVS_V31_RUNTIME_CHECKPOINT") !== expected.checkpoint_hash) fail("TEVS_V31_RUNTIME_CHECKPOINT_HASH", "CHECKPOINT identity mismatch");
  return expected;
}

export function epochValue(index, computationHash, inputStateHash, authorityHash, previousHash) {
  if ((index === 0 && previousHash !== null) || (index > 0 && previousHash === null)) fail("TEVS_V31_EPOCH", "previous continuation mismatch");
  const body = { schema: EPOCH_SCHEMA, epoch_index: index, computation_hash: computationHash, input_state_hash: inputStateHash, authority_hash: authorityHash, previous_continuation_hash: previousHash };
  return { ...body, epoch_hash: canonicalHash(body) };
}

export function continuationValue(epoch, resultHash, currentStateHash, observationsHash, effectsHash, resourcesHash) {
  const body = { schema: CONTINUATION_SCHEMA, epoch_hash: epoch.epoch_hash, epoch_index: epoch.epoch_index, previous_continuation_hash: epoch.previous_continuation_hash, result_hash: resultHash, state_hash: currentStateHash, observations_hash: observationsHash, effects_hash: effectsHash, resources_hash: resourcesHash };
  return { ...body, continuation_hash: canonicalHash(body) };
}

export function resultSemanticHash(status, fieldHash, pc) { return canonicalHash({ status, field_hash: fieldHash, pc }); }

export function proofAdmittedApply(program, field, tx) {
  if (tx.proof_requirement_hashes.length === 0) {
    const direct = applyTransformation(field, tx);
    return { ...direct, proofUseHash: null };
  }
  const byRequirement = Object.fromEntries(program.proof_admissions.map(item => [item.requirement_hash, item]));
  const selected = tx.proof_requirement_hashes.map(requirement => {
    const admission = byRequirement[requirement];
    if (!admission || admission.status !== "VERIFIED" || admission.authority_hash !== program.authority_hash) fail("TEVS_V31_RUNTIME_PROOF_REQUIRED", "PROOF admission unavailable");
    return admission;
  });
  const proofUseHash = canonicalHash({ schema: "TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_USE_V1", program_hash: program.program_hash, authority_hash: program.authority_hash, transformation_hash: tx.transformation_hash, requirement_hashes: tx.proof_requirement_hashes, admission_hashes: selected.map(item => item.admission_hash) });
  const localTx = transformationValue({ transformation_id: `tev.total.proof_admitted.${proofUseHash.slice(0, 32)}`, required_before_hash: tx.required_before_hash, result_profile: tx.result_profile, remove_fact_hashes: tx.remove_fact_hashes, add_facts: tx.add_facts, effect_set_hash: tx.effect_set_hash, resource_vector_hash: tx.resource_vector_hash, proof_requirement_hashes: [] });
  const applied = applyTransformation(field, localTx);
  if (applied.receipt.status !== "PASS") fail("TEVS_V31_RUNTIME_PROOF_APPLY", "PROOF admitted Apply did not pass");
  return { ...applied, proofUseHash };
}

export { canonicalHash, canonicalJson };
