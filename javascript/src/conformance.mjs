import { canonicalHash } from "./canonical.mjs";
import { ScriptRuntime, encodeTypedValue } from "./runtime.mjs";
import { decodeTypedValue } from "./values.mjs";

function capabilitySignatures(ir, entityId) {
  const entity = ir.entities.find((item) => item.entity_id === entityId);
  if (!entity) throw new Error(`unknown entity ${entityId}`);
  return new Map(entity.capabilities.map((item) => [item.capability_id, item]));
}

function encodeArguments(signature, args) {
  return signature.parameters.map((typeName, index) => encodeTypedValue(typeName, args[index]));
}

export function runConformance(ir, scenario) {
  const trace = [];
  const entityId = scenario.entity_id;
  const signatures = capabilitySignatures(ir, entityId);
  const capabilityConfig = scenario.capabilities ?? {};
  const capabilities = {};

  for (const [capabilityId, signature] of signatures) {
    const config = capabilityConfig[capabilityId];
    if (!config) throw new Error(`scenario lacks capability ${capabilityId}`);
    capabilities[capabilityId] = (...args) => {
      let result = null;
      if (config.mode === "constant") {
        result = decodeTypedValue(config.value_type, config.value);
      } else if (config.mode !== "trace") {
        throw new Error(`unsupported capability mode ${config.mode}`);
      }
      trace.push({
        capability_id: capabilityId,
        arguments: encodeArguments(signature, args),
        result: signature.return_type === "Unit"
          ? null
          : encodeTypedValue(signature.return_type, result),
      });
      return result;
    };
  }

  const runtime = new ScriptRuntime(ir, capabilities);
  for (const invocation of scenario.invocations) {
    const args = invocation.arguments.map((item) =>
      decodeTypedValue(item.type, item.value));
    runtime.invoke(invocation.entity_id, invocation.event_id, ...args);
  }

  const semantic = {
    schema: "TEV_SCRIPT_CONFORMANCE_RECEIPT_V1",
    scenario_id: scenario.scenario_id,
    program_hash: ir.semantic_hash,
    final_states: ir.entities.map((entity) => ({
      entity_id: entity.entity_id,
      state: runtime.encodedState(entity.entity_id),
    })),
    emitted_events: runtime.emitted.map((event) => {
      const eventDefinition = ir.entities
        .find((entity) => entity.entity_id === event.entity_id)
        ?.emitted_events.find((item) => item.event_id === event.event_id);
      const types = eventDefinition?.parameters ?? [];
      return {
        entity_id: event.entity_id,
        event_id: event.event_id,
        arguments: event.arguments.map((value, index) => encodeTypedValue(types[index], value)),
      };
    }),
    capability_trace: trace,
  };
  return { ...semantic, receipt_hash: canonicalHash(semantic) };
}
