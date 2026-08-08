import type { TypeTableV3 } from "./ir-v3-values.mjs";

export function validateEntityHandlerFlowV3(
  entity: Record<string, unknown>,
  handler: Record<string, unknown>,
  table: TypeTableV3,
  path: string,
): void;
