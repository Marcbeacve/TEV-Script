import type { Rational, TevScriptError } from "./runtime.mjs";
import type {
  IrV3RuntimeValue,
  RecordValueV3,
  TypeTableV3,
  VariantValueV3,
} from "./ir-v3-values.mjs";

export type TevCapabilityV3 = (...arguments_: IrV3RuntimeValue[]) => unknown;

export interface EmittedEventV3 {
  entity_id: string;
  event_id: string;
  argument_types: string[];
  arguments: IrV3RuntimeValue[];
}

export class ScriptRuntimeV3 {
  constructor(
    ir: object,
    capabilities?: Record<string, TevCapabilityV3>,
    options?: {expectedSourceSemanticHash?: string | null},
  );
  readonly ir: object;
  readonly typeTable: TypeTableV3;
  readonly emitted: EmittedEventV3[];
  readonly sourceSemanticHash: string;
  readonly semanticHash: string;
  invoke(entityId: string, eventId: string, ...arguments_: IrV3RuntimeValue[]): EmittedEventV3[];
  state(entityId: string): Record<string, IrV3RuntimeValue>;
  canonicalState(entityId: string): Record<string, unknown>;
  canonicalEventArguments(event: EmittedEventV3): unknown[];
}

export { Rational, TevScriptError, RecordValueV3, VariantValueV3 };
export { encodeV3Value } from "./ir-v3-values.mjs";
export { validateProgramIrV3 } from "./ir-v3-validation.mjs";
