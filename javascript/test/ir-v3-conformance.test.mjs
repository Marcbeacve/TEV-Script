import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { canonicalHash, canonicalJson } from "../src/canonical.mjs";
import { runIrV3Conformance } from "../src/ir-v3-conformance.mjs";

const CASES = JSON.parse(
  readFileSync(new URL("../../conformance/ir-v3-validator-cases.json", import.meta.url), "utf8"),
);
const SCENARIO = JSON.parse(
  readFileSync(new URL("../../conformance/ir-v3-portable.scenario.json", import.meta.url), "utf8"),
);
const PROGRAM = CASES.valid_program;

function clone(value) {
  return structuredClone(value);
}

test("IR V3 JavaScript conformance receipt is self-consistent", () => {
  const bundle = runIrV3Conformance(clone(PROGRAM), clone(SCENARIO));
  const receipt = bundle.receipt;
  assert.equal(receipt.schema, "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1");
  assert.equal(receipt.scenario_id, "algebraic_roundtrip");
  assert.equal(receipt.scenario_hash, canonicalHash(SCENARIO));
  assert.equal(receipt.program_semantic_hash, PROGRAM.semantic_hash);
  assert.equal(receipt.source_semantic_hash, "1".repeat(64));
  const body = Object.fromEntries(
    Object.entries(receipt).filter(([key]) => key !== "receipt_hash"),
  );
  assert.equal(receipt.receipt_hash, canonicalHash(body));
  assert.equal(bundle.canonicalJson, canonicalJson(receipt));
  assert.equal(bundle.receiptHash, receipt.receipt_hash);
});

test("IR V3 JavaScript conformance receipt records the same typed event witness", () => {
  const receipt = runIrV3Conformance(clone(PROGRAM), clone(SCENARIO)).receipt;
  assert.deepEqual(receipt.steps.map((step) => step.event_id), ["start", "update", "pulse"]);
  assert.equal(receipt.steps[0].state_hash, receipt.steps[1].state_hash);
  assert.notEqual(receipt.steps[1].state_hash, receipt.steps[2].state_hash);
  assert.deepEqual(receipt.steps[0].emitted, []);
  assert.equal(receipt.steps[1].emitted.length, 1);
  const changed = receipt.steps[1].emitted[0];
  assert.deepEqual([changed.entity_id, changed.event_id], ["E", "changed"]);
  assert.deepEqual(changed.arguments.map((item) => item.type), ["Root.Pair", "Option<Int>"]);
  assert.deepEqual(changed.arguments[0].value, {
    $record: {
      type: "Root.Pair",
      fields: [
        { name: "a", value: { $int: "2" } },
        { name: "b", value: { $rat: ["3", "1"] } },
      ],
    },
  });
  assert.deepEqual(changed.arguments[1].value, {
    $option: {
      type: "Option<Int>",
      variant: "Some",
      value: { $int: "7" },
    },
  });
});

test("IR V3 JavaScript conformance transcript follows runtime call order", () => {
  const receipt = runIrV3Conformance(clone(PROGRAM), clone(SCENARIO)).receipt;
  assert.deepEqual(
    receipt.capability_calls.map((item) => item.capability_id),
    ["world.read", "sink.write"],
  );
  assert.deepEqual(receipt.capability_calls.map((item) => item.index), [0, 1]);
  assert.deepEqual(receipt.capability_calls[0].arguments, []);
  assert.equal(receipt.capability_calls[0].return.type, "Root.Pair");
  assert.deepEqual(
    receipt.capability_calls[1].arguments,
    [receipt.capability_calls[0].return],
  );
  assert.equal(Object.hasOwn(receipt.capability_calls[1], "return"), false);
});

test("IR V3 JavaScript conformance final state contains scripted record", () => {
  const receipt = runIrV3Conformance(clone(PROGRAM), clone(SCENARIO)).receipt;
  const finalEntity = receipt.final_state[0];
  assert.equal(finalEntity.entity_id, "E");
  assert.equal(finalEntity.state.pair.type, "Root.Pair");
  assert.deepEqual(
    finalEntity.state.pair.value,
    SCENARIO.capabilities[1].calls[0].return.value,
  );
  assert.equal(receipt.final_state_hash, canonicalHash(receipt.final_state));
});

test("IR V3 JavaScript conformance detects scenario program hash tamper", () => {
  const scenario = clone(SCENARIO);
  scenario.program_semantic_hash = "0".repeat(64);
  assert.throws(
    () => runIrV3Conformance(clone(PROGRAM), scenario),
    (error) => error.code === "TEVS_IR_V3_CONFORMANCE_PROGRAM_HASH",
  );
});

test("IR V3 JavaScript conformance detects scripted capability argument divergence", () => {
  const scenario = clone(SCENARIO);
  scenario.capabilities[0].calls[0].arguments[0].value.$record.fields[0].value = { $int: "99" };
  assert.throws(
    () => runIrV3Conformance(clone(PROGRAM), scenario),
    (error) => error.code === "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARGUMENTS",
  );
});

test("IR V3 JavaScript conformance rejects extra scripted calls", () => {
  const scenario = clone(SCENARIO);
  scenario.capabilities[1].calls.push(clone(scenario.capabilities[1].calls[0]));
  assert.throws(
    () => runIrV3Conformance(clone(PROGRAM), scenario),
    (error) => error.code === "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_UNDERFLOW",
  );
});

test("IR V3 JavaScript conformance rejects missing scripted calls", () => {
  const scenario = clone(SCENARIO);
  scenario.capabilities[1].calls.length = 0;
  assert.throws(
    () => runIrV3Conformance(clone(PROGRAM), scenario),
    (error) => error.code === "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_OVERFLOW",
  );
});

test("IR V3 JavaScript conformance requires canonical capability-script ordering", () => {
  const scenario = clone(SCENARIO);
  scenario.capabilities.reverse();
  assert.throws(
    () => runIrV3Conformance(clone(PROGRAM), scenario),
    (error) => error.code === "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ORDER",
  );
});
