import { IR_SCHEMA, LANGUAGE_VERSION, validateProgramIr } from "./ir-validation.mjs";
const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;
const STABLE_ID = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;

function requireInvocationId(value) {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) {
    throw new TevScriptError("TEVS_RUNTIME_INVOCATION_ID", `non-canonical invocation id ${JSON.stringify(value)}`);
  }
  return value;
}

function requireBindingId(value) {
  if (typeof value !== "string" || !STABLE_ID.test(value)) {
    throw new TevScriptError("TEVS_RUNTIME_CAPABILITY_BINDING_ID", `non-canonical capability binding id ${String(value)}`);
  }
  return value;
}

import {
  Rational,
  TevScriptError,
  coerceRuntime,
  compareValues,
  decodeTypedValue,
  encodeTypedValue,
  valueEquals,
} from "./values.mjs";


function popArguments(stack, count) {
  if (count === 0) return [];
  if (stack.length < count) {
    throw new TevScriptError("TEVS_RUNTIME_STACK_UNDERFLOW", "not enough values for call");
  }
  return stack.splice(stack.length - count, count);
}

function vectorOrScalar(left, right, operation) {
  if (Array.isArray(left) || Array.isArray(right)) {
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
      throw new TevScriptError(
        "TEVS_RUNTIME_VECTOR_OPERAND",
        "vector addition/subtraction requires equal vectors",
      );
    }
    return left.map((value, index) => operation(value, right[index]));
  }
  return operation(left, right);
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

function unary(operator, value) {
  if (operator === "NOT") return !value;
  if (operator === "MINUS") {
    if (Array.isArray(value)) return value.map((item) => item.neg());
    if (value instanceof Rational) return value.neg();
    return -value;
  }
  throw new TevScriptError("TEVS_RUNTIME_UNARY", operator);
}

function binary(operator, left, right) {
  if (operator === "AND") return Boolean(left && right);
  if (operator === "OR") return Boolean(left || right);
  if (operator === "EQEQ") return valueEquals(left, right);
  if (operator === "NE") return !valueEquals(left, right);
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
  throw new TevScriptError("TEVS_RUNTIME_BINARY", operator);
}

function callPure(functionId, args) {
  if (functionId === "vec2" || functionId === "vec3") return args.map((item) => Rational.from(item));
  if (functionId === "max" || functionId === "min") {
    if (args.length !== 2) throw new TevScriptError("TEVS_RUNTIME_PURE_ARITY", functionId);
    const comparison = compareValues(args[0], args[1]);
    return functionId === "max"
      ? comparison >= 0 ? args[0] : args[1]
      : comparison <= 0 ? args[0] : args[1];
  }
  throw new TevScriptError("TEVS_RUNTIME_PURE_FUNCTION", `unknown pure function ${functionId}`);
}

export class ScriptRuntime {
  constructor(ir, capabilities = {}) {
    this.ir = structuredClone(ir);
    this.capabilities = { ...capabilities };
    for (const capabilityId of Reflect.ownKeys(this.capabilities)) requireBindingId(capabilityId);
    this.entities = new Map();
    this.emitted = [];
    this.validateProgram();
    for (const rawEntity of this.ir.entities) {
      const state = new Map();
      const stateTypes = new Map();
      for (const rawState of rawEntity.states) {
        state.set(rawState.name, decodeTypedValue(rawState.type, rawState.initial));
        stateTypes.set(rawState.name, rawState.type);
      }
      const handlers = new Map(rawEntity.handlers.map((handler) => [handler.event_id, handler]));
      this.entities.set(rawEntity.entity_id, {
        entityId: rawEntity.entity_id,
        state,
        stateTypes,
        handlers,
      });
    }
  }

  validateProgram() {
    validateProgramIr(this.ir);
  }

  invoke(entityId, eventId, ...args) {
    entityId = requireInvocationId(entityId);
    eventId = requireInvocationId(eventId);
    const entity = this.entities.get(entityId);
    if (!entity) throw new TevScriptError("TEVS_RUNTIME_ENTITY_UNKNOWN", `unknown entity ${entityId}`);
    const start = this.emitted.length;
    const queue = [[eventId, args]];
    const maximum = Number(this.ir.boundary.maximum_event_chain);
    let processed = 0;
    while (queue.length > 0) {
      processed += 1;
      if (processed > maximum) {
        throw new TevScriptError("TEVS_RUNTIME_EVENT_BUDGET", `event chain exceeds ${maximum}`);
      }
      const [currentEvent, currentArgs] = queue.shift();
      const handler = entity.handlers.get(currentEvent);
      if (!handler) {
        this.emitted.push({ entity_id: entityId, event_id: currentEvent, arguments: currentArgs });
        continue;
      }
      if (handler.parameters.length !== currentArgs.length) {
        throw new TevScriptError(
          "TEVS_RUNTIME_EVENT_ARITY",
          `event ${currentEvent} expects ${handler.parameters.length} arguments`,
        );
      }
      const parameters = new Map();
      handler.parameters.forEach((parameter, index) => {
        parameters.set(parameter.name, coerceRuntime(currentArgs[index], parameter.type));
      });
      const generated = this.executeHandler(entity, handler, parameters);
      for (const item of generated) {
        this.emitted.push({ entity_id: entityId, event_id: item.eventId, arguments: item.args });
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
          "TEVS_RUNTIME_INSTRUCTION_BUDGET",
          `handler ${handler.event_id} exceeded its instruction budget`,
        );
      }
      const instruction = instructions[pc];
      switch (instruction.op) {
        case "CONST": stack.push(decodeTypedValue(instruction.type, instruction.value)); break;
        case "LOAD_STATE": stack.push(entity.state.get(instruction.name)); break;
        case "STORE_STATE": entity.state.set(instruction.name, stack.pop()); break;
        case "LOAD_LOCAL": stack.push(locals.get(instruction.name)); break;
        case "STORE_LOCAL": locals.set(instruction.name, stack.pop()); break;
        case "LOAD_PARAM": stack.push(parameters.get(instruction.name)); break;
        case "CONVERT_INT_TO_RAT": stack.push(new Rational(stack.pop())); break;
        case "UNARY": stack.push(unary(instruction.operator, stack.pop())); break;
        case "BINARY": {
          const right = stack.pop();
          const left = stack.pop();
          stack.push(binary(instruction.operator, left, right));
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
            throw new TevScriptError(
              "TEVS_RUNTIME_CAPABILITY_MISSING",
              `capability ${instruction.capability_id} is not bound`,
            );
          }
          const arguments_ = popArguments(stack, Number(instruction.argc));
          const result = capability(...arguments_);
          if (instruction.return_type !== "Unit") {
            stack.push(coerceRuntime(result, instruction.return_type));
          }
          break;
        }
        case "EMIT_EVENT": {
          const arguments_ = popArguments(stack, Number(instruction.argc));
          emitted.push({ eventId: instruction.event_id, args: arguments_ });
          break;
        }
        case "JUMP_IF_FALSE": {
          const condition = stack.pop();
          if (condition !== true) {
            pc = Number(instruction.target);
            continue;
          }
          break;
        }
        case "JUMP": pc = Number(instruction.target); continue;
        case "RETURN": pc = instructions.length; continue;
        default: throw new TevScriptError("TEVS_RUNTIME_OPCODE", `unknown opcode ${instruction.op}`);
      }
      pc += 1;
    }
    if (stack.length !== 0) {
      throw new TevScriptError(
        "TEVS_RUNTIME_STACK_LEAK",
        `handler ${handler.event_id} left ${stack.length} values on the stack`,
      );
    }
    return emitted;
  }

  rawState(entityId) {
    const entity = this.entities.get(entityId);
    if (!entity) throw new TevScriptError("TEVS_RUNTIME_ENTITY_UNKNOWN", `unknown entity ${entityId}`);
    return entity;
  }

  encodedState(entityId) {
    const entity = this.rawState(entityId);
    const result = {};
    const names = Array.from(entity.state.keys()).sort();
    for (const name of names) {
      result[name] = {
        type: entity.stateTypes.get(name),
        value: encodeTypedValue(entity.stateTypes.get(name), entity.state.get(name)),
      };
    }
    return result;
  }
}

export { IR_SCHEMA, LANGUAGE_VERSION, validateProgramIr } from "./ir-validation.mjs";
export { Rational, TevScriptError, encodeTypedValue } from "./values.mjs";
