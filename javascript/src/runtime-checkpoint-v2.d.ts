import type { ScriptRuntimeV3, TevCapabilityV3 } from "./runtime-v3.mjs";

export class RuntimeCheckpointV2 {
  readonly programId: string;
  readonly irSchema: string;
  readonly semanticHash: string;
  readonly sourceSchema: string;
  readonly sourceSemanticHash: string;
  readonly entities: readonly (readonly [string, readonly (readonly [string, string, unknown])[]])[];
  static capture(runtime: ScriptRuntimeV3): RuntimeCheckpointV2;
  static parse(text: string): RuntimeCheckpointV2;
  toObject(): object;
  toCanonicalJson(): string;
  readonly checkpointHash: string;
  restoreExact(ir: object, capabilities?: Record<string, TevCapabilityV3>): ScriptRuntimeV3;
}

export const RUNTIME_CHECKPOINT_V2_SCHEMA: "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2";
