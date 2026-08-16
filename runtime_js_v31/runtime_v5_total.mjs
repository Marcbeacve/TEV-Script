#!/usr/bin/env node
import { parseStrictJson } from "../javascript/src/strict-json.mjs";
import {
  QUANTUM_SCHEMA,
  TevJsError,
  applyTransformation,
  canonicalHash,
  canonicalJson,
  checkpointValue,
  continuationValue,
  epochValue,
  factValue,
  fail,
  proofAdmittedApply,
  requireFields,
  resultSemanticHash,
  stateHash,
  transformationValue,
  validateCheckpoint,
  validateProgram,
} from "./core.mjs";
import { runV4Unit } from "./v4_governed.mjs";

function bridgePayload(unit, receipt) {
  const common = {
    unit_id: unit.unit_id,
    unit_hash: unit.unit_hash,
    program_ir_hash: unit.program_ir_hash,
    run_receipt_hash: receipt.receipt_hash,
  };
  if (unit.profile === "pure" || unit.profile === "recursive") {
    return {
      payload: {
        ...common,
        result_type: receipt.result_type,
        result_encoded: receipt.result_encoded,
        result_hash: receipt.result_hash,
        evaluation_steps: receipt.evaluation_steps,
      },
      steps: receipt.evaluation_steps,
      observationHash: null,
      effectHash: null,
    };
  }
  return {
    payload: {
      ...common,
      final_state: receipt.final_state,
      final_state_hash: receipt.final_state_hash,
      capability_transcript_hash: receipt.capability_transcript_hash,
      evaluation_steps: receipt.evaluation_steps,
      observation_calls: receipt.observation_calls,
      transition_receipt_hash: receipt.transition_receipt_hash,
    },
    steps: receipt.evaluation_steps,
    observationHash: receipt.capability_transcript_hash,
    effectHash: receipt.transition_receipt_hash,
  };
}

function appendBridge(field, unit, relation, payload, runReceiptHash, evaluationSteps) {
  const fact = factValue(relation, [payload]);
  const bridge = transformationValue({
    transformation_id: `tev.total.bridge.${unit.unit_id}.${runReceiptHash.slice(0, 16)}`,
    required_before_hash: field.field_hash,
    result_profile: null,
    remove_fact_hashes: [],
    add_facts: [fact],
    effect_set_hash: canonicalHash([]),
    resource_vector_hash: canonicalHash({ v4_evaluation_steps: evaluationSteps }),
    proof_requirement_hashes: [],
  });
  const applied = applyTransformation(field, bridge);
  if (applied.receipt.status !== "PASS") fail("TEVS_V31_RUNTIME_BRIDGE_APPLY", "bridge Apply did not close");
  return applied;
}

function runQuantum(program, checkpoint) {
  if (checkpoint.halted) fail("TEVS_V31_RUNTIME_HALTED", "halted checkpoint cannot resume");

  const inputStateHash = stateHash(program.program_hash, checkpoint.field.field_hash, checkpoint.pc);
  const previousHash = checkpoint.previous_continuation === null
    ? null
    : checkpoint.previous_continuation.continuation_hash;
  const epoch = epochValue(
    checkpoint.next_epoch_index,
    program.program_hash,
    inputStateHash,
    program.authority_hash,
    previousHash,
  );

  let field = checkpoint.field;
  let pc = checkpoint.pc;
  let stepsUsed = 0;
  let v4Steps = 0;
  const applyHashes = [];
  const childHashes = [];
  const observationHashes = [];
  const effectHashes = [];
  let status = "SUSPENDED";

  while (stepsUsed < program.quantum_step_limit) {
    const instruction = program.instructions[pc];
    stepsUsed += 1;

    if (instruction.kind === "apply") {
      const tx = program.txByHash[instruction.transformation_hash];
      const applied = proofAdmittedApply(program, field, tx);
      field = applied.after;
      if (applied.receipt.status !== "PASS") fail("TEVS_V31_RUNTIME_APPLY_OPEN", "Apply did not close");
      applyHashes.push(applied.receipt.receipt_hash);
      if (applied.proofUseHash !== null) effectHashes.push(applied.proofUseHash);
      effectHashes.push(applied.receipt.effect_set_hash);
      pc = instruction.next_pc;
      continue;
    }

    if (instruction.kind === "branch_fact") {
      const present = field.facts.some(item => item.fact_hash === instruction.fact_hash);
      pc = present ? instruction.present_pc : instruction.absent_pc;
      continue;
    }

    if (instruction.kind === "jump") {
      pc = instruction.target_pc;
      continue;
    }

    if (instruction.kind === "invoke_v4") {
      const unit = program.unitByHash[instruction.unit_hash];
      const receipt = runV4Unit(unit);
      const bridge = bridgePayload(unit, receipt);
      const applied = appendBridge(
        field,
        unit,
        instruction.result_relation,
        bridge.payload,
        receipt.receipt_hash,
        bridge.steps,
      );
      field = applied.after;
      applyHashes.push(applied.receipt.receipt_hash);
      childHashes.push(receipt.receipt_hash);
      v4Steps += bridge.steps;
      if (bridge.observationHash !== null) observationHashes.push(bridge.observationHash);
      if (bridge.effectHash !== null) effectHashes.push(bridge.effectHash);
      pc = instruction.next_pc;
      continue;
    }

    status = "HALTED";
    break;
  }

  const resultHash = resultSemanticHash(status, field.field_hash, pc);
  const currentStateHash = stateHash(program.program_hash, field.field_hash, pc);
  const continuation = continuationValue(
    epoch,
    resultHash,
    currentStateHash,
    canonicalHash(observationHashes),
    canonicalHash(effectHashes),
    canonicalHash({ v5_steps: stepsUsed, v4_evaluation_steps: v4Steps }),
  );
  const nextCheckpoint = checkpointValue(
    program,
    field,
    pc,
    checkpoint.next_epoch_index + 1,
    continuation,
    status === "HALTED",
  );

  const body = {
    schema: QUANTUM_SCHEMA,
    program_hash: program.program_hash,
    epoch,
    status,
    steps_used: stepsUsed,
    v4_evaluation_steps: v4Steps,
    field,
    pc,
    apply_receipt_hashes: applyHashes,
    child_receipt_hashes: childHashes,
    result_hash: resultHash,
    continuation,
    next_checkpoint: nextCheckpoint,
  };
  return { ...body, quantum_hash: canonicalHash(body) };
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const request = parseStrictJson(Buffer.concat(chunks).toString("utf8"));
  requireFields(request, ["program", "checkpoint"], "TEVS_V31_REQUEST");
  const program = validateProgram(request.program);
  const checkpoint = validateCheckpoint(program, request.checkpoint);
  const result = runQuantum(program, checkpoint);
  process.stdout.write(`${canonicalJson(result)}\n`);
}

main().catch(error => {
  const code = error instanceof TevJsError || (error && typeof error.code === "string")
    ? error.code
    : "TEVS_V31_JS_INTERNAL";
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${code}: ${message}\n`);
  process.exitCode = 1;
});
