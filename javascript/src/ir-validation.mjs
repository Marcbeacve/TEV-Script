import { canonicalHash } from "./canonical.mjs";
import { decodeTypedValue, TevScriptError } from "./values.mjs";
import { validateEntityHandlerFlow } from "./ir-flow.mjs";

export const IR_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V2";
export const LANGUAGE_VERSION = "0.2.0";
export const MAX_EVENT_CHAIN = 128;
export const MAX_ENTITIES = 128;
export const MAX_STATES_PER_ENTITY = 256;
export const MAX_HANDLERS_PER_ENTITY = 256;
export const MAX_LOCALS_PER_HANDLER = 256;
export const MAX_ARGUMENTS = 64;
export const MAX_INSTRUCTIONS_PER_HANDLER = 8192;

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;
const STABLE_ID = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const HASH = /^[0-9a-f]{64}$/;
const TYPE_NAMES = new Set(["Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit"]);
const VALUE_TYPE_NAMES = new Set(["Bool", "Int", "Rat", "Text", "Vec2", "Vec3"]);
const CAPABILITY_KINDS = new Set(["observation", "effect"]);
const BOUNDARY_FLAGS = [
  "dynamic_code",
  "reflection",
  "unbounded_loops",
  "implicit_physical_effects",
  "runtime_source_compilation",
  "automatic_authority_escalation",
];

function fail(path, message, code = "TEVS_RUNTIME_IR_CONTRACT") {
  throw new TevScriptError(code, `${path}: ${message}`);
}

function objectValue(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected an object");
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    fail(path, "expected a plain object");
  }
  if (Object.getOwnPropertySymbols(value).length !== 0) {
    fail(path, "symbol keys are forbidden");
  }
  return value;
}

function arrayValue(value, path, { minimum = 0, maximum = null } = {}) {
  if (!Array.isArray(value)) fail(path, "expected an array");
  if (value.length < minimum) fail(path, `expected at least ${minimum} items`);
  if (maximum !== null && value.length > maximum) fail(path, `expected at most ${maximum} items`);
  return value;
}

function exactKeys(value, path, expected) {
  const observed = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (observed.length !== wanted.length || observed.some((key, index) => key !== wanted[index])) {
    const observedSet = new Set(observed);
    const wantedSet = new Set(wanted);
    const missing = wanted.filter((key) => !observedSet.has(key));
    const extra = observed.filter((key) => !wantedSet.has(key));
    fail(path, `field set mismatch; missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`);
  }
}

function identifier(value, path) {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) fail(path, "expected an identifier");
  return value;
}

function stableId(value, path) {
  if (typeof value !== "string" || !STABLE_ID.test(value)) fail(path, "expected a stable identifier");
  return value;
}

function typeName(value, path, { allowUnit = true } = {}) {
  const allowed = allowUnit ? TYPE_NAMES : VALUE_TYPE_NAMES;
  if (!allowed.has(value)) fail(path, `unsupported type ${JSON.stringify(value)}`);
  return value;
}

function integer(value, path, { minimum, maximum }) {
  if (!Number.isSafeInteger(value)) fail(path, "expected a safe structural integer");
  if (value < minimum || value > maximum) fail(path, `integer must be in [${minimum}, ${maximum}]`);
  return value;
}

function hashValue(value, path) {
  if (typeof value !== "string" || !HASH.test(value)) fail(path, "expected lowercase SHA-256 hexadecimal");
  return value;
}

function validateTypedValue(type, value, path) {
  try {
    decodeTypedValue(type, value);
  } catch (error) {
    fail(path, `invalid ${type} value: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function validateParameter(raw, path, { allowUnit }) {
  const item = objectValue(raw, path);
  exactKeys(item, path, ["name", "type"]);
  return [identifier(item.name, `${path}.name`), typeName(item.type, `${path}.type`, { allowUnit })];
}

function validateInstruction(raw, path, context) {
  const item = objectValue(raw, path);
  const op = item.op;
  if (typeof op !== "string") fail(`${path}.op`, "expected opcode string");

  if (op === "CONST") {
    exactKeys(item, path, ["op", "type", "value"]);
    const type = typeName(item.type, `${path}.type`, { allowUnit: false });
    validateTypedValue(type, item.value, `${path}.value`);
    return;
  }

  if (["LOAD_STATE", "STORE_STATE", "LOAD_LOCAL", "STORE_LOCAL", "LOAD_PARAM"].includes(op)) {
    exactKeys(item, path, ["op", "name", "type"]);
    const name = identifier(item.name, `${path}.name`);
    const type = typeName(item.type, `${path}.type`, { allowUnit: false });
    const namespace = ["LOAD_STATE", "STORE_STATE"].includes(op)
      ? context.states
      : ["LOAD_LOCAL", "STORE_LOCAL"].includes(op)
        ? context.locals
        : context.parameters;
    if (namespace.get(name) !== type) fail(path, `${op} references unknown or mismatched name ${JSON.stringify(name)}`);
    return;
  }

  if (op === "CONVERT_INT_TO_RAT") {
    exactKeys(item, path, ["op"]);
    return;
  }

  if (op === "UNARY") {
    exactKeys(item, path, ["op", "operator", "type"]);
    if (!["NOT", "MINUS"].includes(item.operator)) fail(`${path}.operator`, "unsupported unary operator");
    const type = typeName(item.type, `${path}.type`, { allowUnit: false });
    if (item.operator === "NOT" && type !== "Bool") fail(path, "NOT must produce Bool");
    if (item.operator === "MINUS" && !["Int", "Rat"].includes(type)) fail(path, "MINUS must produce Int or Rat");
    return;
  }

  if (op === "BINARY") {
    exactKeys(item, path, ["op", "operator", "left_type", "right_type", "result_type"]);
    if (!["AND", "OR", "EQEQ", "NE", "LT", "LE", "GT", "GE", "PLUS", "MINUS", "STAR", "SLASH"].includes(item.operator)) {
      fail(`${path}.operator`, "unsupported binary operator");
    }
    for (const field of ["left_type", "right_type", "result_type"]) {
      typeName(item[field], `${path}.${field}`, { allowUnit: false });
    }
    return;
  }

  if (op === "CALL_PURE") {
    exactKeys(item, path, ["op", "function_id", "argc", "return_type"]);
    const functionId = stableId(item.function_id, `${path}.function_id`);
    const argc = integer(item.argc, `${path}.argc`, { minimum: 0, maximum: MAX_ARGUMENTS });
    const returnType = typeName(item.return_type, `${path}.return_type`);
    const fixed = functionId === "vec2" ? [2, "Vec2"] : functionId === "vec3" ? [3, "Vec3"] : null;
    if (fixed !== null && (fixed[0] !== argc || fixed[1] !== returnType)) {
      fail(path, "pure function signature does not match the V0.2 contract");
    }
    if (["max", "min"].includes(functionId)) {
      if (argc !== 2 || !["Int", "Rat"].includes(returnType)) fail(path, "max/min signature is invalid");
    } else if (fixed === null) {
      fail(path, "unknown pure function");
    }
    return;
  }

  if (op === "CALL_CAPABILITY") {
    exactKeys(item, path, ["op", "capability_id", "argc", "return_type", "kind"]);
    const capabilityId = stableId(item.capability_id, `${path}.capability_id`);
    const argc = integer(item.argc, `${path}.argc`, { minimum: 0, maximum: MAX_ARGUMENTS });
    const returnType = typeName(item.return_type, `${path}.return_type`);
    if (!CAPABILITY_KINDS.has(item.kind)) fail(`${path}.kind`, "capability kind must be observation or effect");
    const signature = context.capabilities.get(capabilityId);
    if (!signature || signature.parameters.length !== argc || signature.returnType !== returnType || signature.kind !== item.kind) {
      fail(path, `capability instruction does not match declaration ${JSON.stringify(capabilityId)}`);
    }
    return;
  }

  if (op === "EMIT_EVENT") {
    exactKeys(item, path, ["op", "event_id", "argc", "argument_types"]);
    const eventId = identifier(item.event_id, `${path}.event_id`);
    const argc = integer(item.argc, `${path}.argc`, { minimum: 0, maximum: MAX_ARGUMENTS });
    const argumentTypes = arrayValue(item.argument_types, `${path}.argument_types`, { maximum: MAX_ARGUMENTS })
      .map((value, index) => typeName(value, `${path}.argument_types[${index}]`, { allowUnit: false }));
    const expected = context.events.get(eventId);
    if (argumentTypes.length !== argc || !expected || expected.length !== argumentTypes.length
        || expected.some((value, index) => value !== argumentTypes[index])) {
      fail(path, `event instruction does not match declaration ${JSON.stringify(eventId)}`);
    }
    return;
  }

  if (["JUMP", "JUMP_IF_FALSE"].includes(op)) {
    exactKeys(item, path, ["op", "target"]);
    const target = integer(item.target, `${path}.target`, { minimum: 0, maximum: context.instructionCount });
    if (target <= context.index) fail(`${path}.target`, "backward or self jumps are forbidden in V0.2");
    return;
  }

  if (op === "RETURN") {
    exactKeys(item, path, ["op"]);
    return;
  }

  fail(`${path}.op`, `unknown opcode ${JSON.stringify(op)}`, "TEVS_RUNTIME_OPCODE");
}

function validateEntity(raw, path) {
  const item = objectValue(raw, path);
  exactKeys(item, path, ["entity_id", "states", "handlers", "capabilities", "emitted_events"]);
  const entityId = identifier(item.entity_id, `${path}.entity_id`);

  const states = new Map();
  for (const [index, rawState] of arrayValue(item.states, `${path}.states`, { maximum: MAX_STATES_PER_ENTITY }).entries()) {
    const statePath = `${path}.states[${index}]`;
    const state = objectValue(rawState, statePath);
    exactKeys(state, statePath, ["name", "type", "initial"]);
    const name = identifier(state.name, `${statePath}.name`);
    if (states.has(name)) fail(`${statePath}.name`, `duplicate state ${JSON.stringify(name)}`);
    const type = typeName(state.type, `${statePath}.type`, { allowUnit: false });
    validateTypedValue(type, state.initial, `${statePath}.initial`);
    states.set(name, type);
  }

  const capabilities = new Map();
  for (const [index, rawCapability] of arrayValue(item.capabilities, `${path}.capabilities`).entries()) {
    const capabilityPath = `${path}.capabilities[${index}]`;
    const capability = objectValue(rawCapability, capabilityPath);
    exactKeys(capability, capabilityPath, ["capability_id", "parameters", "return_type", "kind"]);
    const capabilityId = stableId(capability.capability_id, `${capabilityPath}.capability_id`);
    if (capabilities.has(capabilityId)) fail(`${capabilityPath}.capability_id`, `duplicate capability ${JSON.stringify(capabilityId)}`);
    const parameters = arrayValue(capability.parameters, `${capabilityPath}.parameters`, { maximum: MAX_ARGUMENTS })
      .map((value, position) => typeName(value, `${capabilityPath}.parameters[${position}]`, { allowUnit: false }));
    const returnType = typeName(capability.return_type, `${capabilityPath}.return_type`);
    if (!CAPABILITY_KINDS.has(capability.kind)) fail(`${capabilityPath}.kind`, "capability kind must be observation or effect");
    capabilities.set(capabilityId, { parameters, returnType, kind: capability.kind });
  }

  const events = new Map();
  for (const [index, rawEvent] of arrayValue(item.emitted_events, `${path}.emitted_events`).entries()) {
    const eventPath = `${path}.emitted_events[${index}]`;
    const event = objectValue(rawEvent, eventPath);
    exactKeys(event, eventPath, ["event_id", "parameters"]);
    const eventId = identifier(event.event_id, `${eventPath}.event_id`);
    if (events.has(eventId)) fail(`${eventPath}.event_id`, `duplicate emitted event ${JSON.stringify(eventId)}`);
    const parameters = arrayValue(event.parameters, `${eventPath}.parameters`, { maximum: MAX_ARGUMENTS })
      .map((value, position) => typeName(value, `${eventPath}.parameters[${position}]`, { allowUnit: false }));
    events.set(eventId, parameters);
  }

  const handlerIds = new Set();
  for (const [handlerIndex, rawHandler] of arrayValue(item.handlers, `${path}.handlers`, { maximum: MAX_HANDLERS_PER_ENTITY }).entries()) {
    const handlerPath = `${path}.handlers[${handlerIndex}]`;
    const handler = objectValue(rawHandler, handlerPath);
    exactKeys(handler, handlerPath, ["event_id", "parameters", "locals", "instructions", "instruction_budget"]);
    const eventId = identifier(handler.event_id, `${handlerPath}.event_id`);
    if (handlerIds.has(eventId)) fail(`${handlerPath}.event_id`, `duplicate handler ${JSON.stringify(eventId)}`);
    handlerIds.add(eventId);

    const parameters = new Map();
    for (const [index, rawParameter] of arrayValue(handler.parameters, `${handlerPath}.parameters`, { maximum: MAX_ARGUMENTS }).entries()) {
      const [name, type] = validateParameter(rawParameter, `${handlerPath}.parameters[${index}]`, { allowUnit: false });
      if (parameters.has(name) || states.has(name)) fail(`${handlerPath}.parameters[${index}].name`, `duplicate or state-shadowing parameter ${JSON.stringify(name)}`);
      parameters.set(name, type);
    }

    const locals = new Map();
    for (const [index, rawLocal] of arrayValue(handler.locals, `${handlerPath}.locals`, { maximum: MAX_LOCALS_PER_HANDLER }).entries()) {
      const [name, type] = validateParameter(rawLocal, `${handlerPath}.locals[${index}]`, { allowUnit: false });
      if (locals.has(name) || parameters.has(name) || states.has(name)) fail(`${handlerPath}.locals[${index}].name`, `duplicate or shadowing local ${JSON.stringify(name)}`);
      locals.set(name, type);
    }

    const instructions = arrayValue(handler.instructions, `${handlerPath}.instructions`, { minimum: 1, maximum: MAX_INSTRUCTIONS_PER_HANDLER });
    const budget = integer(handler.instruction_budget, `${handlerPath}.instruction_budget`, { minimum: 1, maximum: MAX_INSTRUCTIONS_PER_HANDLER });
    if (instructions.length > budget) fail(`${handlerPath}.instruction_budget`, "budget is smaller than instruction count");
    if (instructions.at(-1)?.op !== "RETURN") fail(`${handlerPath}.instructions`, "handler must end in RETURN");
    for (const [index, instruction] of instructions.entries()) {
      validateInstruction(instruction, `${handlerPath}.instructions[${index}]`, {
        index,
        instructionCount: instructions.length,
        states,
        parameters,
        locals,
        capabilities,
        events,
      });
    }
    validateEntityHandlerFlow(item, handler, handlerPath);
  }

  return entityId;
}

export function validateProgramIr(ir) {
  const root = objectValue(ir, "$");
  exactKeys(root, "$", ["schema", "language_version", "program_id", "entities", "boundary", "semantic_hash", "debug", "debug_hash"]);
  if (root.schema !== IR_SCHEMA) fail("$.schema", `expected ${IR_SCHEMA}`, "TEVS_RUNTIME_SCHEMA");
  if (root.language_version !== LANGUAGE_VERSION) fail("$.language_version", `expected ${LANGUAGE_VERSION}`, "TEVS_RUNTIME_LANGUAGE_VERSION");
  identifier(root.program_id, "$.program_id");
  hashValue(root.semantic_hash, "$.semantic_hash");
  hashValue(root.debug_hash, "$.debug_hash");

  const boundary = objectValue(root.boundary, "$.boundary");
  exactKeys(boundary, "$.boundary", [...BOUNDARY_FLAGS, "maximum_event_chain"]);
  for (const flag of BOUNDARY_FLAGS) {
    if (boundary[flag] !== false) fail(`$.boundary.${flag}`, "must be false", "TEVS_RUNTIME_BOUNDARY");
  }
  integer(boundary.maximum_event_chain, "$.boundary.maximum_event_chain", { minimum: 1, maximum: MAX_EVENT_CHAIN });

  const debug = objectValue(root.debug, "$.debug");
  if (canonicalHash(debug) !== root.debug_hash) fail("$.debug_hash", "debug hash does not match", "TEVS_RUNTIME_DEBUG_HASH");

  const entityIds = new Set();
  for (const [index, entity] of arrayValue(root.entities, "$.entities", { minimum: 1, maximum: MAX_ENTITIES }).entries()) {
    const entityId = validateEntity(entity, `$.entities[${index}]`);
    if (entityIds.has(entityId)) fail(`$.entities[${index}].entity_id`, `duplicate entity ${JSON.stringify(entityId)}`);
    entityIds.add(entityId);
  }

  const semantic = {};
  for (const [key, value] of Object.entries(root)) {
    if (!["semantic_hash", "debug", "debug_hash"].includes(key)) semantic[key] = value;
  }
  if (canonicalHash(semantic) !== root.semantic_hash) fail("$.semantic_hash", "program semantic hash does not match", "TEVS_RUNTIME_SEMANTIC_HASH");
}
