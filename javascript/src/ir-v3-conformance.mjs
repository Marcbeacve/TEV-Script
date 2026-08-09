import { canonicalHash, canonicalJson } from "./canonical.mjs";
import {
  decodeV3Value,
  encodeV3Value,
  TevScriptError,
} from "./ir-v3-values.mjs";
import { validateProgramIrV3 } from "./ir-v3-validation.mjs";
import { ScriptRuntimeV3 } from "./runtime-v3.mjs";

const STABLE = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const LOCAL = /^[A-Za-z_][A-Za-z0-9_]*$/;
const HASH = /^[0-9a-f]{64}$/;

function fail(code, path, message) {
  throw new TevScriptError(code, `${path}: ${message}`);
}

function objectValue(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, "expected object");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, "expected string object keys");
  }
  return value;
}

function arrayValue(value, path, minimum, maximum) {
  if (!Array.isArray(value) || value.length < minimum || value.length > maximum) {
    fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, `expected array length in [${minimum}, ${maximum}]`);
  }
  return value;
}

function exactKeys(value, path, expected) {
  const observed = Object.keys(value).sort();
  const target = [...expected].sort();
  if (observed.length !== target.length || observed.some((key, index) => key !== target[index])) {
    const missing = target.filter((key) => !observed.includes(key));
    const extra = observed.filter((key) => !target.includes(key));
    fail(
      "TEVS_IR_V3_CONFORMANCE_SHAPE",
      path,
      `field set mismatch; missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`,
    );
  }
}

function stableId(value, path) {
  if (typeof value !== "string" || !STABLE.test(value)) {
    fail("TEVS_IR_V3_CONFORMANCE_IDENTIFIER", path, `invalid stable id ${JSON.stringify(value)}`);
  }
  return value;
}

function localId(value, path) {
  if (typeof value !== "string" || !LOCAL.test(value)) {
    fail("TEVS_IR_V3_CONFORMANCE_IDENTIFIER", path, `invalid local id ${JSON.stringify(value)}`);
  }
  return value;
}

function sha256(value, path) {
  if (typeof value !== "string" || !HASH.test(value)) {
    fail("TEVS_IR_V3_CONFORMANCE_HASH", path, "expected lowercase SHA-256");
  }
  return value;
}

function globalCapabilityContracts(ir) {
  const result = new Map();
  for (const entity of ir.entities) {
    for (const capability of entity.capabilities) {
      const contract = {
        parameters: [...capability.parameters],
        returnType: capability.return_type,
        kind: capability.kind,
      };
      const previous = result.get(capability.capability_id);
      if (previous !== undefined && canonicalJson(previous) !== canonicalJson(contract)) {
        fail(
          "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CONFLICT",
          capability.capability_id,
          "program contains conflicting capability contracts",
        );
      }
      result.set(capability.capability_id, contract);
    }
  }
  return result;
}

function validateScriptedCall(call, parameters, returnType, runtime, path) {
  exactKeys(
    call,
    path,
    returnType === "Unit" ? new Set(["arguments"]) : new Set(["arguments", "return"]),
  );
  const arguments_ = arrayValue(call.arguments, `${path}.arguments`, 0, 64);
  if (arguments_.length !== parameters.length) {
    fail(
      "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARITY",
      path,
      `expected ${parameters.length} arguments, got ${arguments_.length}`,
    );
  }
  parameters.forEach((typeId, index) => {
    const typed = objectValue(arguments_[index], `${path}.arguments[${index}]`);
    exactKeys(typed, `${path}.arguments[${index}]`, new Set(["type", "value"]));
    if (typed.type !== typeId) {
      fail(
        "TEVS_IR_V3_CONFORMANCE_CAPABILITY_TYPE",
        path,
        `argument ${index} expected ${typeId}, got ${JSON.stringify(typed.type)}`,
      );
    }
    decodeV3Value(typeId, typed.value, runtime.typeTable, {
      context: `${path}.arguments[${index}]`,
    });
  });
  if (returnType !== "Unit") {
    const rawReturn = objectValue(call.return, `${path}.return`);
    exactKeys(rawReturn, `${path}.return`, new Set(["type", "value"]));
    if (rawReturn.type !== returnType) {
      fail(
        "TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN_TYPE",
        path,
        `expected return ${returnType}, got ${JSON.stringify(rawReturn.type)}`,
      );
    }
    decodeV3Value(returnType, rawReturn.value, runtime.typeTable, {
      context: `${path}.return`,
    });
  }
}

class ScenarioHost {
  constructor(runtime, scenarioScripts) {
    this.runtime = runtime;
    this.contracts = globalCapabilityContracts(runtime.ir);
    this.scripts = new Map();
    this.transcript = [];
    let previousId = null;

    scenarioScripts.forEach((raw, index) => {
      const path = `$.capabilities[${index}]`;
      const item = objectValue(raw, path);
      exactKeys(item, path, new Set(["capability_id", "calls"]));
      const capabilityId = stableId(item.capability_id, `${path}.capability_id`);
      if (this.scripts.has(capabilityId)) {
        fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_DUPLICATE", path, `duplicate capability script ${JSON.stringify(capabilityId)}`);
      }
      if (previousId !== null && capabilityId <= previousId) {
        fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_ORDER", path, "capability scripts must be strictly sorted by id");
      }
      previousId = capabilityId;
      const contract = this.contracts.get(capabilityId);
      if (contract === undefined) {
        fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_UNKNOWN", path, `scenario scripts undeclared capability ${JSON.stringify(capabilityId)}`);
      }
      const calls = arrayValue(item.calls, `${path}.calls`, 0, 4096);
      calls.forEach((call, callIndex) => validateScriptedCall(
        objectValue(call, `${path}.calls[${callIndex}]`),
        contract.parameters,
        contract.returnType,
        runtime,
        `${path}.calls[${callIndex}]`,
      ));
      this.scripts.set(capabilityId, {
        capabilityId,
        parameters: contract.parameters,
        returnType: contract.returnType,
        calls,
        cursor: 0,
      });
    });
  }

  bindings() {
    return Object.fromEntries(
      [...this.scripts].map(([capabilityId, script]) => [
        capabilityId,
        (...arguments_) => this.invokeScript(script, arguments_),
      ]),
    );
  }

  invokeScript(script, arguments_) {
    if (script.cursor >= script.calls.length) {
      fail(
        "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_OVERFLOW",
        script.capabilityId,
        "runtime invoked capability more times than scripted",
      );
    }
    const expected = script.calls[script.cursor];
    const callIndex = this.transcript.length;
    const encodedArguments = script.parameters.map((typeId, index) => ({
      type: typeId,
      value: encodeV3Value(
        typeId,
        arguments_[index],
        this.runtime.typeTable,
        { context: `capability ${script.capabilityId} argument ${index}` },
      ),
    }));
    if (canonicalJson(encodedArguments) !== canonicalJson(expected.arguments)) {
      fail(
        "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARGUMENTS",
        script.capabilityId,
        `call ${script.cursor} arguments differ from scripted canonical values`,
      );
    }
    const transcriptEntry = {
      index: callIndex,
      capability_id: script.capabilityId,
      arguments: encodedArguments,
    };
    script.cursor += 1;
    if (script.returnType === "Unit") {
      if (Object.hasOwn(expected, "return")) {
        fail(
          "TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN",
          script.capabilityId,
          "Unit scripted call must not contain return",
        );
      }
      this.transcript.push(transcriptEntry);
      return undefined;
    }
    const rawReturn = objectValue(expected.return, `capability ${script.capabilityId}.return`);
    transcriptEntry.return = rawReturn;
    this.transcript.push(transcriptEntry);
    return decodeV3Value(
      script.returnType,
      rawReturn.value,
      this.runtime.typeTable,
      { context: `capability ${script.capabilityId} scripted return` },
    );
  }

  verifyConsumed() {
    const pending = Object.fromEntries(
      [...this.scripts]
        .filter(([, script]) => script.cursor !== script.calls.length)
        .map(([capabilityId, script]) => [capabilityId, script.calls.length - script.cursor]),
    );
    if (Object.keys(pending).length !== 0) {
      fail(
        "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_UNDERFLOW",
        "$.capabilities",
        `scripted capability calls not consumed exactly: ${canonicalJson(pending)}`,
      );
    }
  }
}

function stateWitness(runtime) {
  return [...runtime.entities.keys()].sort().map((entityId) => {
    const entity = runtime.entities.get(entityId);
    const state = Object.fromEntries(
      [...entity.state.keys()].sort().map((stateName) => [
        stateName,
        {
          type: entity.stateTypes.get(stateName),
          value: encodeV3Value(
            entity.stateTypes.get(stateName),
            entity.state.get(stateName),
            runtime.typeTable,
            { context: `state witness ${entityId}.${stateName}` },
          ),
        },
      ]),
    );
    return { entity_id: entityId, state };
  });
}

function eventWitness(event, runtime) {
  return {
    entity_id: event.entity_id,
    event_id: event.event_id,
    arguments: event.argument_types.map((typeId, index) => ({
      type: typeId,
      value: encodeV3Value(
        typeId,
        event.arguments[index],
        runtime.typeTable,
        { context: `event witness ${event.event_id}[${index}]` },
      ),
    })),
  };
}

function decodeInvocationArguments(runtime, entityId, eventId, arguments_) {
  const entity = runtime.entities.get(entityId);
  if (!entity) fail("TEVS_IR_V3_CONFORMANCE_ENTITY", entityId, "unknown scenario entity");
  const handler = entity.handlers.get(eventId);
  let expected;
  if (handler !== undefined) expected = handler.parameters.map((item) => item.type);
  else {
    expected = entity.emittedEventTypes.get(eventId);
    if (expected === undefined) {
      if (arguments_.length !== 0) {
        fail(
          "TEVS_IR_V3_CONFORMANCE_EVENT_SIGNATURE",
          eventId,
          "unhandled scenario event with arguments has no portable signature",
        );
      }
      expected = [];
    }
  }
  if (expected.length !== arguments_.length) {
    fail(
      "TEVS_IR_V3_CONFORMANCE_EVENT_ARITY",
      eventId,
      `expected ${expected.length} arguments, got ${arguments_.length}`,
    );
  }
  return expected.map((expectedType, index) => {
    const typed = objectValue(arguments_[index], `scenario argument ${index}`);
    exactKeys(typed, `scenario argument ${index}`, new Set(["type", "value"]));
    if (typed.type !== expectedType) {
      fail(
        "TEVS_IR_V3_CONFORMANCE_EVENT_TYPE",
        eventId,
        `argument ${index} expected ${expectedType}, got ${JSON.stringify(typed.type)}`,
      );
    }
    return decodeV3Value(expectedType, typed.value, runtime.typeTable, {
      context: `scenario ${entityId}.${eventId}[${index}]`,
    });
  });
}

function validateScenario(scenario, program) {
  exactKeys(
    scenario,
    "$",
    new Set([
      "schema", "scenario_id", "program_semantic_hash",
      "source_semantic_hash", "capabilities", "steps",
    ]),
  );
  if (scenario.schema !== "TEV_SCRIPT_IR_V3_SCENARIO_V1") {
    fail("TEVS_IR_V3_CONFORMANCE_SCENARIO_SCHEMA", "$.schema", "unexpected scenario schema");
  }
  stableId(scenario.scenario_id, "$.scenario_id");
  const programHash = sha256(scenario.program_semantic_hash, "$.program_semantic_hash");
  const sourceHash = sha256(scenario.source_semantic_hash, "$.source_semantic_hash");
  if (programHash !== program.semantic_hash) {
    fail("TEVS_IR_V3_CONFORMANCE_PROGRAM_HASH", "$.program_semantic_hash", "scenario targets a different IR V3 semantic hash");
  }
  if (sourceHash !== program.source_semantic_hash) {
    fail("TEVS_IR_V3_CONFORMANCE_SOURCE_HASH", "$.source_semantic_hash", "scenario targets a different source semantic hash");
  }
  arrayValue(scenario.capabilities, "$.capabilities", 0, 8192);
  const steps = arrayValue(scenario.steps, "$.steps", 0, 1024);
  steps.forEach((raw, index) => {
    const step = objectValue(raw, `$.steps[${index}]`);
    exactKeys(step, `$.steps[${index}]`, new Set(["entity_id", "event_id", "arguments"]));
    localId(step.entity_id, `$.steps[${index}].entity_id`);
    localId(step.event_id, `$.steps[${index}].event_id`);
    arrayValue(step.arguments, `$.steps[${index}].arguments`, 0, 64);
  });
  return scenario;
}

export function runIrV3Conformance(ir, scenario) {
  const program = structuredClone(ir);
  validateProgramIrV3(program);
  const scenarioObject = validateScenario(structuredClone(scenario), program);
  const scenarioHash = canonicalHash(scenarioObject);

  const bootstrap = new ScriptRuntimeV3(program, {}, {
    expectedSourceSemanticHash: scenarioObject.source_semantic_hash,
  });
  const host = new ScenarioHost(
    bootstrap,
    arrayValue(scenarioObject.capabilities, "$.capabilities", 0, 8192),
  );
  const runtime = new ScriptRuntimeV3(program, host.bindings(), {
    expectedSourceSemanticHash: scenarioObject.source_semantic_hash,
  });
  host.runtime = runtime;

  const initialState = stateWitness(runtime);
  const initialStateHash = canonicalHash(initialState);
  const steps = [];
  scenarioObject.steps.forEach((rawStep, index) => {
    const entityId = rawStep.entity_id;
    const eventId = rawStep.event_id;
    const arguments_ = decodeInvocationArguments(runtime, entityId, eventId, rawStep.arguments);
    const emitted = runtime.invoke(entityId, eventId, ...arguments_);
    const state = stateWitness(runtime);
    steps.push({
      index,
      entity_id: entityId,
      event_id: eventId,
      emitted: emitted.map((event) => eventWitness(event, runtime)),
      state_hash: canonicalHash(state),
    });
  });

  host.verifyConsumed();
  const finalState = stateWitness(runtime);
  const finalStateHash = canonicalHash(finalState);
  const body = {
    schema: "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1",
    scenario_id: scenarioObject.scenario_id,
    scenario_hash: scenarioHash,
    program_semantic_hash: program.semantic_hash,
    source_semantic_hash: program.source_semantic_hash,
    initial_state_hash: initialStateHash,
    steps,
    capability_calls: host.transcript,
    final_state: finalState,
    final_state_hash: finalStateHash,
  };
  const receiptHash = canonicalHash(body);
  const receipt = { ...body, receipt_hash: receiptHash };
  return {
    receipt,
    canonicalJson: canonicalJson(receipt),
    receiptHash,
  };
}
