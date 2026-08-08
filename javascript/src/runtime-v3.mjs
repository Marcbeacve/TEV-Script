import { compareValues, coerceRuntime, Rational, TevScriptError } from "./values.mjs";
import { validateProgramIrV3 } from "./ir-v3-validation.mjs";
import {
  RecordValueV3,
  VariantValueV3,
  decodeV3Value,
  encodeV3Value,
  v3ValuesEqual,
} from "./ir-v3-values.mjs";

const STABLE_ID = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const LOCAL_ID = /^[A-Za-z_][A-Za-z0-9_]*$/;

function requireLocalId(value, kind) {
  if (typeof value !== "string" || !LOCAL_ID.test(value)) {
    throw new TevScriptError("TEVS_IR_V3_INVOCATION_ID", `non-canonical ${kind} id ${JSON.stringify(value)}`);
  }
  return value;
}

function requireBindingId(value) {
  if (typeof value !== "string" || !STABLE_ID.test(value)) {
    throw new TevScriptError("TEVS_IR_V3_CAPABILITY_BINDING_ID", `non-canonical capability binding id ${JSON.stringify(value)}`);
  }
  return value;
}

function popArguments(stack, count) {
  if (count === 0) return [];
  if (stack.length < count) {
    throw new TevScriptError("TEVS_IR_V3_STACK_UNDERFLOW", "not enough values for operation");
  }
  return stack.splice(stack.length - count, count);
}

function add(left, right) {
  if (left instanceof Rational || right instanceof Rational) return Rational.from(left).add(right);
  return left + right;
}
function subtract(left, right) {
  if (left instanceof Rational || right instanceof Rational) return Rational.from(left).sub(right);
  return left - right;
}
function multiply(left, right) {
  if (left instanceof Rational || right instanceof Rational) return Rational.from(left).mul(right);
  return left * right;
}
function vectorOrScalar(left, right, operation) {
  if (Array.isArray(left) || Array.isArray(right)) {
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
      throw new TevScriptError("TEVS_IR_V3_VECTOR_OPERAND", "vector plus/minus requires equal vectors");
    }
    return left.map((value, index) => operation(value, right[index]));
  }
  return operation(left, right);
}

function unary(operator, value) {
  if (operator === "NOT") return !value;
  if (operator === "MINUS") {
    if (value instanceof Rational) return value.neg();
    return -value;
  }
  throw new TevScriptError("TEVS_IR_V3_RUNTIME_UNARY", `unknown unary operator ${operator}`);
}

function binaryV3(operator, leftType, rightType, left, right, table) {
  if (operator === "AND") return Boolean(left && right);
  if (operator === "OR") return Boolean(left || right);
  if (operator === "EQEQ" || operator === "NE") {
    let equal;
    if ((leftType === "Int" && rightType === "Rat") || (leftType === "Rat" && rightType === "Int")) {
      equal = Rational.from(left).equals(Rational.from(right));
    } else if (leftType === rightType) {
      equal = v3ValuesEqual(leftType, left, right, table);
    } else {
      throw new TevScriptError("TEVS_IR_V3_RUNTIME_BINARY", "invalid equality types");
    }
    return operator === "EQEQ" ? equal : !equal;
  }
  if (operator === "LT") return compareValues(left, right) < 0;
  if (operator === "LE") return compareValues(left, right) <= 0;
  if (operator === "GT") return compareValues(left, right) > 0;
  if (operator === "GE") return compareValues(left, right) >= 0;
  if (operator === "PLUS") return vectorOrScalar(left, right, add);
  if (operator === "MINUS") return vectorOrScalar(left, right, subtract);
  if (operator === "STAR") {
    if (Array.isArray(left) && !Array.isArray(right)) return left.map((item) => multiply(item, right));
    if (Array.isArray(right) && !Array.isArray(left)) return right.map((item) => multiply(left, item));
    return multiply(left, right);
  }
  if (operator === "SLASH") {
    if (Array.isArray(left)) return left.map((item) => Rational.from(item).div(right));
    return Rational.from(left).div(right);
  }
  throw new TevScriptError("TEVS_IR_V3_RUNTIME_BINARY", `unknown binary operator ${operator}`);
}

function callPure(functionId, args) {
  if (functionId === "vec2" || functionId === "vec3") return args.map((item) => Rational.from(item));
  if (functionId === "max" || functionId === "min") {
    if (args.length !== 2) throw new TevScriptError("TEVS_IR_V3_PURE_ARITY", functionId);
    const comparison = compareValues(args[0], args[1]);
    return functionId === "max"
      ? comparison >= 0 ? args[0] : args[1]
      : comparison <= 0 ? args[0] : args[1];
  }
  throw new TevScriptError("TEVS_IR_V3_PURE_FUNCTION", `unknown pure intrinsic ${functionId}`);
}

function coerceRuntimeV3(typeId, value, table, context) {
  const descriptor = table.require(typeId, context);
  if (descriptor.kind === "primitive") {
    try {
      return coerceRuntime(value, typeId);
    } catch (error) {
      throw new TevScriptError(
        "TEVS_IR_V3_CAPABILITY_COERCION",
        `${context}: ${error.message}`,
      );
    }
  }
  if (value instanceof RecordValueV3 || value instanceof VariantValueV3) {
    const raw = encodeV3Value(typeId, value, table, { context });
    return decodeV3Value(typeId, raw, table, { context });
  }
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return decodeV3Value(typeId, value, table, { context });
  }
  throw new TevScriptError(
    "TEVS_IR_V3_CAPABILITY_COERCION",
    `${context}: composite value must be canonical encoded value or V3 semantic value`,
  );
}

export class ScriptRuntimeV3 {
  constructor(ir, capabilities = {}, { expectedSourceSemanticHash = null } = {}) {
    this.ir = structuredClone(ir);
    this.typeTable = validateProgramIrV3(this.ir, { expectedSourceSemanticHash });
    this.capabilities = { ...capabilities };
    for (const capabilityId of Reflect.ownKeys(this.capabilities)) requireBindingId(capabilityId);
    this.entities = new Map();
    this.emitted = [];

    for (const rawEntity of this.ir.entities) {
      const state = new Map();
      const stateTypes = new Map();
      for (const rawState of rawEntity.states) {
        state.set(
          rawState.name,
          decodeV3Value(rawState.type, rawState.initial, this.typeTable, {
            context: `state ${rawEntity.entity_id}.${rawState.name}`,
          }),
        );
        stateTypes.set(rawState.name, rawState.type);
      }
      const handlers = new Map(rawEntity.handlers.map((handler) => [handler.event_id, handler]));
      const emittedEventTypes = new Map(
        rawEntity.emitted_events.map((event) => [event.event_id, [...event.parameters]]),
      );
      this.entities.set(rawEntity.entity_id, {
        entityId: rawEntity.entity_id,
        state,
        stateTypes,
        handlers,
        emittedEventTypes,
      });
    }
  }

  get sourceSemanticHash() { return this.ir.source_semantic_hash; }
  get semanticHash() { return this.ir.semantic_hash; }

  invoke(entityId, eventId, ...args) {
    entityId = requireLocalId(entityId, "entity");
    eventId = requireLocalId(eventId, "event");
    const entity = this.entities.get(entityId);
    if (!entity) throw new TevScriptError("TEVS_IR_V3_ENTITY_UNKNOWN", `unknown entity ${JSON.stringify(entityId)}`);
    const start = this.emitted.length;
    const queue = [[eventId, args]];
    const maximum = Number(this.ir.boundary.maximum_event_chain);
    let processed = 0;

    while (queue.length > 0) {
      processed += 1;
      if (processed > maximum) throw new TevScriptError("TEVS_IR_V3_EVENT_BUDGET", `event chain exceeds ${maximum}`);
      const [currentEvent, rawArguments] = queue.shift();
      const handler = entity.handlers.get(currentEvent);
      if (!handler) {
        let signature = entity.emittedEventTypes.get(currentEvent);
        if (!signature) {
          if (rawArguments.length !== 0) {
            throw new TevScriptError(
              "TEVS_IR_V3_EVENT_SIGNATURE_UNKNOWN",
              `unhandled event ${JSON.stringify(currentEvent)} has arguments but no portable signature`,
            );
          }
          signature = [];
        }
        if (signature.length !== rawArguments.length) {
          throw new TevScriptError("TEVS_IR_V3_EVENT_ARITY", `event ${JSON.stringify(currentEvent)} expects ${signature.length} arguments`);
        }
        const coerced = signature.map((typeId, index) =>
          coerceRuntimeV3(typeId, rawArguments[index], this.typeTable, `invoke ${entityId}.${currentEvent}[${index}]`));
        this.emitted.push({
          entity_id: entityId,
          event_id: currentEvent,
          argument_types: [...signature],
          arguments: coerced,
        });
        continue;
      }
      if (handler.parameters.length !== rawArguments.length) {
        throw new TevScriptError("TEVS_IR_V3_EVENT_ARITY", `event ${JSON.stringify(currentEvent)} expects ${handler.parameters.length} arguments`);
      }
      const parameters = new Map();
      handler.parameters.forEach((parameter, index) => {
        parameters.set(
          parameter.name,
          coerceRuntimeV3(parameter.type, rawArguments[index], this.typeTable, `invoke ${entityId}.${currentEvent}[${index}]`),
        );
      });
      const generated = this.executeHandler(entity, handler, parameters);
      for (const item of generated) {
        const event = {
          entity_id: entityId,
          event_id: item.eventId,
          argument_types: [...item.argumentTypes],
          arguments: item.args,
        };
        this.emitted.push(event);
        if (entity.handlers.has(item.eventId)) queue.push([item.eventId, item.args]);
      }
    }
    return this.emitted.slice(start);
  }

  executeHandler(entity, handler, parameters) {
    const instructions = handler.instructions;
    const budget = Number(handler.instruction_budget);
    const stack = [];
    const locals = new Map();
    const emitted = [];
    let pc = 0;
    let executed = 0;

    while (pc < instructions.length) {
      executed += 1;
      if (executed > budget) {
        throw new TevScriptError(
          "TEVS_IR_V3_INSTRUCTION_BUDGET",
          `handler ${JSON.stringify(handler.event_id)} exceeded instruction budget ${budget}`,
        );
      }
      const instruction = instructions[pc];
      switch (instruction.op) {
        case "CONST":
          stack.push(decodeV3Value(instruction.type, instruction.value, this.typeTable, {
            context: `instruction ${handler.event_id}:${pc}`,
          }));
          break;
        case "LOAD_STATE": stack.push(entity.state.get(instruction.name)); break;
        case "STORE_STATE": entity.state.set(instruction.name, stack.pop()); break;
        case "LOAD_LOCAL": stack.push(locals.get(instruction.name)); break;
        case "STORE_LOCAL": locals.set(instruction.name, stack.pop()); break;
        case "LOAD_PARAM": stack.push(parameters.get(instruction.name)); break;
        case "CONVERT_INT_TO_RAT": stack.push(new Rational(stack.pop())); break;
        case "UNARY": stack.push(unary(instruction.operator, stack.pop())); break;
        case "BINARY": {
          const right = stack.pop(); const left = stack.pop();
          stack.push(binaryV3(
            instruction.operator,
            instruction.left_type,
            instruction.right_type,
            left,
            right,
            this.typeTable,
          ));
          break;
        }
        case "CALL_PURE": {
          const arguments_ = popArguments(stack, Number(instruction.argc));
          const result = callPure(instruction.function_id, arguments_);
          if (instruction.return_type !== "Unit") stack.push(result);
          break;
        }
        case "CALL_CAPABILITY": {
          const capability = this.capabilities[instruction.capability_id];
          if (typeof capability !== "function") {
            throw new TevScriptError("TEVS_IR_V3_CAPABILITY_MISSING", `capability ${JSON.stringify(instruction.capability_id)} is not bound`);
          }
          const arguments_ = popArguments(stack, Number(instruction.argc));
          const result = capability(...arguments_);
          if (instruction.return_type !== "Unit") {
            stack.push(coerceRuntimeV3(
              instruction.return_type,
              result,
              this.typeTable,
              `capability ${instruction.capability_id} return`,
            ));
          }
          break;
        }
        case "EMIT_EVENT": {
          const argumentTypes = [...instruction.argument_types];
          const values = popArguments(stack, Number(instruction.argc));
          const arguments_ = argumentTypes.map((typeId, index) =>
            coerceRuntimeV3(typeId, values[index], this.typeTable, `emit ${instruction.event_id}[${index}]`));
          emitted.push({ eventId: instruction.event_id, argumentTypes, args: arguments_ });
          break;
        }
        case "MAKE_RECORD": {
          const descriptor = this.typeTable.require(instruction.type);
          const values = popArguments(stack, instruction.fields.length);
          const byName = new Map(instruction.fields.map((name, index) => [name, values[index]]));
          const record = new RecordValueV3(
            instruction.type,
            descriptor.fields.map(([name]) => [name, byName.get(name)]),
          );
          stack.push(decodeV3Value(
            instruction.type,
            encodeV3Value(instruction.type, record, this.typeTable),
            this.typeTable,
          ));
          break;
        }
        case "LOAD_FIELD": {
          const record = stack.pop();
          if (!(record instanceof RecordValueV3)) {
            throw new TevScriptError("TEVS_IR_V3_RUNTIME_RECORD", "LOAD_FIELD received non-record value");
          }
          stack.push(record.field(instruction.field));
          break;
        }
        case "MAKE_VARIANT": {
          const value = instruction.argc === 0
            ? new VariantValueV3(instruction.type, instruction.variant)
            : new VariantValueV3(instruction.type, instruction.variant, stack.pop());
          stack.push(decodeV3Value(
            instruction.type,
            encodeV3Value(instruction.type, value, this.typeTable),
            this.typeTable,
          ));
          break;
        }
        case "TEST_VARIANT": {
          const value = stack.pop();
          if (!(value instanceof VariantValueV3)) {
            throw new TevScriptError("TEVS_IR_V3_RUNTIME_VARIANT", "TEST_VARIANT received non-variant value");
          }
          stack.push(value.variant === instruction.variant);
          break;
        }
        case "LOAD_VARIANT_PAYLOAD": {
          const value = stack.pop();
          if (!(value instanceof VariantValueV3)
              || value.variant !== instruction.variant
              || !value.hasPayload) {
            throw new TevScriptError(
              "TEVS_IR_V3_VARIANT_UNWRAP",
              `cannot load payload for variant ${JSON.stringify(instruction.variant)}`,
            );
          }
          stack.push(value.payload);
          break;
        }
        case "JUMP_IF_FALSE": {
          const condition = stack.pop();
          if (condition !== true) { pc = Number(instruction.target); continue; }
          break;
        }
        case "JUMP": pc = Number(instruction.target); continue;
        case "RETURN": pc = instructions.length; continue;
        default: throw new TevScriptError("TEVS_IR_V3_OPCODE", `unknown V3 opcode ${JSON.stringify(instruction.op)}`);
      }
      pc += 1;
    }
    if (stack.length !== 0) {
      throw new TevScriptError(
        "TEVS_IR_V3_RUNTIME_STACK_LEAK",
        `handler ${JSON.stringify(handler.event_id)} left ${stack.length} values on stack`,
      );
    }
    return emitted;
  }

  state(entityId) {
    const entity = this.entities.get(entityId);
    if (!entity) throw new TevScriptError("TEVS_IR_V3_ENTITY_UNKNOWN", `unknown entity ${JSON.stringify(entityId)}`);
    return Object.fromEntries(entity.state);
  }

  canonicalState(entityId) {
    const entity = this.entities.get(entityId);
    if (!entity) throw new TevScriptError("TEVS_IR_V3_ENTITY_UNKNOWN", `unknown entity ${JSON.stringify(entityId)}`);
    return Object.fromEntries(
      [...entity.state.keys()].sort().map((name) => [
        name,
        encodeV3Value(entity.stateTypes.get(name), entity.state.get(name), this.typeTable, {
          context: `state ${entityId}.${name}`,
        }),
      ]),
    );
  }

  canonicalEventArguments(event) {
    return event.argument_types.map((typeId, index) =>
      encodeV3Value(typeId, event.arguments[index], this.typeTable, { context: `event ${event.event_id}[${index}]` }));
  }
}

export { validateProgramIrV3 } from "./ir-v3-validation.mjs";
export {
  RecordValueV3,
  VariantValueV3,
  Rational,
  TevScriptError,
  encodeV3Value,
} from "./ir-v3-values.mjs";
