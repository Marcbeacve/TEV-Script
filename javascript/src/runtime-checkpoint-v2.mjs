import { canonicalHash, canonicalJson } from "./canonical.mjs";
import { parseStrictJson } from "./strict-json.mjs";
import { ScriptRuntimeV3 } from "./runtime-v3.mjs";
import { decodeV3Value, encodeV3Value } from "./ir-v3-values.mjs";
import { validateProgramIrV3 } from "./ir-v3-validation.mjs";
import { TevScriptError } from "./values.mjs";

const SCHEMA = "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2";
const LOCAL = /^[A-Za-z_][A-Za-z0-9_]*$/;
const SHA = /^[0-9a-f]{64}$/;
const ROOT_KEYS = Object.freeze([
  "entities", "ir_schema", "program_id", "schema", "semantic_hash",
  "source_schema", "source_semantic_hash",
]);

function fail(code, path, message) {
  throw new TevScriptError(code, `${path}: ${message}`);
}
function requireObject(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected object");
  }
  return value;
}
function exactKeys(value, path, expected) {
  const observed = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (observed.length !== wanted.length || observed.some((item, index) => item !== wanted[index])) {
    fail("TEVS_CHECKPOINT_V2_SHAPE", path, `field set mismatch; expected=${wanted.join(",")}, observed=${observed.join(",")}`);
  }
}
function requireString(value, path) {
  if (typeof value !== "string") fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected string");
  return value;
}
function requireLocal(value, path) {
  const result = requireString(value, path);
  if (!LOCAL.test(result)) fail("TEVS_CHECKPOINT_V2_IDENTIFIER", path, `expected identifier, got ${JSON.stringify(result)}`);
  return result;
}
function requireSha(value, path) {
  const result = requireString(value, path);
  if (!SHA.test(result)) fail("TEVS_CHECKPOINT_V2_SHA256", path, "expected lowercase SHA-256");
  return result;
}

export class RuntimeCheckpointV2 {
  constructor({ programId, irSchema, semanticHash, sourceSchema, sourceSemanticHash, entities }) {
    this.programId = programId;
    this.irSchema = irSchema;
    this.semanticHash = semanticHash;
    this.sourceSchema = sourceSchema;
    this.sourceSemanticHash = sourceSemanticHash;
    this.entities = entities.map(([entityId, state]) => [
      entityId,
      state.map(([name, typeId, value]) => [name, typeId, structuredClone(value)]),
    ]);
    Object.freeze(this.entities);
    Object.freeze(this);
  }

  static capture(runtime) {
    const entities = [];
    for (const entityId of [...runtime.entities.keys()].sort()) {
      const entity = runtime.entities.get(entityId);
      const state = [];
      for (const stateName of [...entity.state.keys()].sort()) {
        const typeId = entity.stateTypes.get(stateName);
        state.push([
          stateName,
          typeId,
          encodeV3Value(typeId, entity.state.get(stateName), runtime.typeTable, {
            context: `checkpoint ${entityId}.${stateName}`,
          }),
        ]);
      }
      entities.push([entityId, state]);
    }
    return new RuntimeCheckpointV2({
      programId: runtime.ir.program_id,
      irSchema: runtime.ir.schema,
      semanticHash: runtime.ir.semantic_hash,
      sourceSchema: runtime.ir.source_schema,
      sourceSemanticHash: runtime.ir.source_semantic_hash,
      entities,
    });
  }

  static parse(text) {
    const parsed = parseStrictJson(text);
    if (canonicalJson(parsed) !== text) {
      throw new TevScriptError(
        "TEVS_CHECKPOINT_V2_CANONICAL",
        "runtime checkpoint must use exact canonical JSON bytes",
      );
    }
    const root = requireObject(parsed, "$");
    exactKeys(root, "$", ROOT_KEYS);
    if (root.schema !== SCHEMA) fail("TEVS_CHECKPOINT_V2_SCHEMA", "$.schema", `expected ${SCHEMA}`);
    const programId = requireLocal(root.program_id, "$.program_id");
    const irSchema = requireString(root.ir_schema, "$.ir_schema");
    if (irSchema !== "TEV_SCRIPT_PROGRAM_IR_V3") {
      fail("TEVS_CHECKPOINT_V2_IR_SCHEMA", "$.ir_schema", "expected TEV_SCRIPT_PROGRAM_IR_V3");
    }
    const semanticHash = requireSha(root.semantic_hash, "$.semantic_hash");
    const sourceSchema = requireString(root.source_schema, "$.source_schema");
    if (sourceSchema !== "TEV_SCRIPT_LINKED_PROGRAM_V1" && sourceSchema !== "TEV_SCRIPT_PROGRAM_IR_V2") {
      fail("TEVS_CHECKPOINT_V2_SOURCE_SCHEMA", "$.source_schema", `unsupported source schema ${JSON.stringify(sourceSchema)}`);
    }
    const sourceSemanticHash = requireSha(root.source_semantic_hash, "$.source_semantic_hash");
    if (!Array.isArray(root.entities)) fail("TEVS_CHECKPOINT_V2_SHAPE", "$.entities", "expected array");
    const entities = [];
    let previous = null;
    const seen = new Set();
    root.entities.forEach((rawEntity, index) => {
      const path = `$.entities[${index}]`;
      const entity = requireObject(rawEntity, path);
      exactKeys(entity, path, ["entity_id", "state"]);
      const entityId = requireLocal(entity.entity_id, `${path}.entity_id`);
      if (seen.has(entityId) || (previous !== null && entityId <= previous)) {
        fail("TEVS_CHECKPOINT_V2_ENTITY_ORDER", `${path}.entity_id`, "entities must be unique and strictly sorted");
      }
      seen.add(entityId);
      previous = entityId;
      const rawState = requireObject(entity.state, `${path}.state`);
      const state = [];
      for (const stateName of Object.keys(rawState).sort()) {
        requireLocal(stateName, `${path}.state key`);
        const typed = requireObject(rawState[stateName], `${path}.state.${stateName}`);
        exactKeys(typed, `${path}.state.${stateName}`, ["type", "value"]);
        state.push([
          stateName,
          requireString(typed.type, `${path}.state.${stateName}.type`),
          structuredClone(typed.value),
        ]);
      }
      entities.push([entityId, state]);
    });
    return new RuntimeCheckpointV2({
      programId, irSchema, semanticHash, sourceSchema, sourceSemanticHash, entities,
    });
  }

  toObject() {
    return {
      schema: SCHEMA,
      program_id: this.programId,
      ir_schema: this.irSchema,
      semantic_hash: this.semanticHash,
      source_schema: this.sourceSchema,
      source_semantic_hash: this.sourceSemanticHash,
      entities: this.entities.map(([entityId, state]) => ({
        entity_id: entityId,
        state: Object.fromEntries(state.map(([name, typeId, value]) => [
          name,
          { type: typeId, value: structuredClone(value) },
        ])),
      })),
    };
  }

  toCanonicalJson() { return canonicalJson(this.toObject()); }
  get checkpointHash() { return canonicalHash(this.toObject()); }

  restoreExact(ir, capabilities = {}) {
    const target = structuredClone(ir);
    const table = validateProgramIrV3(target, {
      expectedSourceSemanticHash: this.sourceSemanticHash,
    });
    if (target.program_id !== this.programId) fail("TEVS_CHECKPOINT_V2_PROGRAM_ID", "$.program_id", "checkpoint program id does not match target");
    if (target.schema !== this.irSchema) fail("TEVS_CHECKPOINT_V2_IR_SCHEMA", "$.ir_schema", "checkpoint IR schema does not match target");
    if (target.semantic_hash !== this.semanticHash) fail("TEVS_CHECKPOINT_V2_SEMANTIC_HASH", "$.semantic_hash", "checkpoint semantic hash does not match target");
    if (target.source_schema !== this.sourceSchema) fail("TEVS_CHECKPOINT_V2_SOURCE_SCHEMA", "$.source_schema", "checkpoint source schema does not match target");
    if (target.source_semantic_hash !== this.sourceSemanticHash) fail("TEVS_CHECKPOINT_V2_SOURCE_HASH", "$.source_semantic_hash", "checkpoint source hash does not match target");

    const expectedEntities = new Map(target.entities.map((entity) => [entity.entity_id, entity]));
    const checkpointEntities = new Map(this.entities);
    if (expectedEntities.size !== checkpointEntities.size
        || [...expectedEntities.keys()].some((id) => !checkpointEntities.has(id))) {
      fail("TEVS_CHECKPOINT_V2_ENTITY_SET", "$.entities", "checkpoint entity set does not exactly match target");
    }

    const decodedState = new Map();
    for (const entityId of [...expectedEntities.keys()].sort()) {
      const definition = expectedEntities.get(entityId);
      const expectedStates = new Map(definition.states.map((state) => [state.name, state.type]));
      const checkpointState = new Map(checkpointEntities.get(entityId).map(([name, typeId, value]) => [name, [typeId, value]]));
      if (expectedStates.size !== checkpointState.size
          || [...expectedStates.keys()].some((name) => !checkpointState.has(name))) {
        fail("TEVS_CHECKPOINT_V2_STATE_SET", `entity ${entityId}`, "checkpoint state set does not exactly match target");
      }
      const values = new Map();
      for (const stateName of [...expectedStates.keys()].sort()) {
        const expectedType = expectedStates.get(stateName);
        const [observedType, rawValue] = checkpointState.get(stateName);
        if (observedType !== expectedType) {
          fail("TEVS_CHECKPOINT_V2_STATE_TYPE", `${entityId}.${stateName}`, `expected ${expectedType}, got ${observedType}`);
        }
        values.set(
          stateName,
          decodeV3Value(expectedType, rawValue, table, { context: `checkpoint ${entityId}.${stateName}` }),
        );
      }
      decodedState.set(entityId, values);
    }

    const runtime = new ScriptRuntimeV3(target, capabilities, {
      expectedSourceSemanticHash: this.sourceSemanticHash,
    });
    for (const [entityId, values] of decodedState) {
      const entity = runtime.entities.get(entityId);
      entity.state.clear();
      for (const [name, value] of values) entity.state.set(name, value);
    }
    return runtime;
  }
}

export const RUNTIME_CHECKPOINT_V2_SCHEMA = SCHEMA;
