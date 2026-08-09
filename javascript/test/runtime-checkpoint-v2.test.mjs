import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { canonicalJson } from "../src/canonical.mjs";
import { RuntimeCheckpointV2 } from "../src/runtime-checkpoint-v2.mjs";
import { ScriptRuntimeV3 } from "../src/runtime-v3.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "../..");
const cases = JSON.parse(fs.readFileSync(path.join(ROOT, "conformance/ir-v3-validator-cases.json"), "utf8"));
const program = cases.valid_program;

function clone(value) { return structuredClone(value); }
function mutateCanonical(checkpoint, mutate) {
  const object = checkpoint.toObject();
  mutate(object);
  return RuntimeCheckpointV2.parse(canonicalJson(object));
}

test("checkpoint V2 capture parse restore and continuation", () => {
  const runtime = new ScriptRuntimeV3(program);
  runtime.invoke("E", "start");
  const checkpoint = RuntimeCheckpointV2.capture(runtime);
  const bytes = checkpoint.toCanonicalJson();
  const parsed = RuntimeCheckpointV2.parse(bytes);
  assert.equal(parsed.toCanonicalJson(), bytes);
  assert.equal(parsed.checkpointHash, checkpoint.checkpointHash);

  const restored = parsed.restoreExact(program);
  assert.deepEqual(restored.canonicalState("E"), runtime.canonicalState("E"));
  const events = restored.invoke("E", "update");
  assert.equal(events.length, 1);
  assert.equal(events[0].event_id, "changed");
  assert.deepEqual(events[0].argument_types, ["Root.Pair", "Option<Int>"]);
  assert.deepEqual(
    restored.canonicalEventArguments(events[0]),
    [
      { $record: { type: "Root.Pair", fields: [
        { name: "a", value: { $int: "2" } },
        { name: "b", value: { $rat: ["3", "1"] } },
      ] } },
      { $option: { type: "Option<Int>", variant: "Some", value: { $int: "7" } } },
    ],
  );
});

test("checkpoint V2 rejects noncanonical bytes", () => {
  const checkpoint = RuntimeCheckpointV2.capture(new ScriptRuntimeV3(program));
  assert.throws(
    () => RuntimeCheckpointV2.parse(`${checkpoint.toCanonicalJson()}\n`),
    (error) => error.code === "TEVS_CHECKPOINT_V2_CANONICAL",
  );
});

test("checkpoint V2 rejects semantic hash tamper on restore", () => {
  const checkpoint = RuntimeCheckpointV2.capture(new ScriptRuntimeV3(program));
  const tampered = mutateCanonical(checkpoint, (object) => {
    object.semantic_hash = "0".repeat(64);
  });
  assert.throws(
    () => tampered.restoreExact(program),
    (error) => error.code === "TEVS_CHECKPOINT_V2_SEMANTIC_HASH",
  );
});

test("checkpoint V2 rejects state type tamper", () => {
  const runtime = new ScriptRuntimeV3(program);
  runtime.invoke("E", "start");
  const checkpoint = RuntimeCheckpointV2.capture(runtime);
  const tampered = mutateCanonical(checkpoint, (object) => {
    object.entities[0].state.opt.type = "Int";
  });
  assert.throws(
    () => tampered.restoreExact(program),
    (error) => error.code === "TEVS_CHECKPOINT_V2_STATE_TYPE",
  );
});

test("checkpoint V2 rejects nested algebraic value tamper", () => {
  const runtime = new ScriptRuntimeV3(program);
  runtime.invoke("E", "start");
  const checkpoint = RuntimeCheckpointV2.capture(runtime);
  const tampered = mutateCanonical(checkpoint, (object) => {
    object.entities[0].state.opt.value.$option.type = "Option<Rat>";
  });
  assert.throws(
    () => tampered.restoreExact(program),
    (error) => error.code === "TEVS_IR_V3_VALUE_INVALID",
  );
});
