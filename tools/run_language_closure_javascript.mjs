import path from "node:path";
import { fileURLToPath } from "node:url";
import { readStrictJsonFile } from "../javascript/src/strict-json-node.mjs";
import { canonicalHash } from "../javascript/src/canonical.mjs";
import { ScriptRuntime, TevScriptError } from "../javascript/src/runtime.mjs";
import { validateProgramIr } from "../javascript/src/ir-validation.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function semanticPart(program) {
  return Object.fromEntries(
    Object.entries(program).filter(([key]) => !["semantic_hash", "debug", "debug_hash"].includes(key)),
  );
}

function selectedHandler(program, entityId, eventId) {
  const entity = program.entities.find((item) => item.entity_id === entityId);
  return entity.handlers.find((item) => item.event_id === eventId);
}

function expectCode(action, code, id) {
  try {
    action();
  } catch (error) {
    if (error instanceof TevScriptError && error.code === code) return;
    throw error;
  }
  throw new Error(`negative case accepted: ${id}`);
}

const corpus = await readStrictJsonFile(path.join(root, "conformance/language-negative-v1.json"));
const base = await readStrictJsonFile(path.join(root, corpus.base_program));
validateProgramIr(base);
console.log("LANGUAGE_CLOSURE_JAVASCRIPT_VALID_BASE=PASS");

let count = 0;
for (const testCase of corpus.cases) {
  const mutated = structuredClone(base);
  const handler = selectedHandler(mutated, corpus.entity_id, corpus.handler_event_id);
  handler.locals = structuredClone(testCase.locals);
  handler.instructions = structuredClone(testCase.instructions);
  handler.instruction_budget = Math.max(1, handler.instructions.length);
  mutated.semantic_hash = canonicalHash(semanticPart(mutated));
  expectCode(() => validateProgramIr(mutated), corpus.expected_code, testCase.id);
  count += 1;
}
if (count !== 8) throw new Error(`expected 8 negative cases, got ${count}`);
console.log("LANGUAGE_CLOSURE_JAVASCRIPT_NEGATIVE_CORPUS=8_PASS");

expectCode(
  () => new ScriptRuntime(base).invoke("Player", " start "),
  "TEVS_RUNTIME_INVOCATION_ID",
  "invocation-id",
);
console.log("LANGUAGE_CLOSURE_JAVASCRIPT_ABI_CANONICAL_ID=PASS");

expectCode(
  () => new ScriptRuntime(base, { " debug.log": () => null }),
  "TEVS_RUNTIME_CAPABILITY_BINDING_ID",
  "capability-binding-id",
);
console.log("LANGUAGE_CLOSURE_JAVASCRIPT_CAPABILITY_BINDING_ID=PASS");
console.log("TEV_SCRIPT_LANGUAGE_CLOSURE_JAVASCRIPT=PASS");
