import type { TypeTableV3 } from "./ir-v3-values.mjs";

export const IR_V3_SCHEMA: "TEV_SCRIPT_PROGRAM_IR_V3";
export const IR_V3_LANGUAGE_VERSION: "1.0.0";

export function validateProgramIrV3(
  ir: object,
  options?: {expectedSourceSemanticHash?: string | null},
): TypeTableV3;
