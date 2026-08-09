export interface TevConformanceReceipt {
  schema: "TEV_SCRIPT_CONFORMANCE_RECEIPT_V1";
  scenario_id: string;
  program_hash: string;
  final_states: unknown[];
  emitted_events: unknown[];
  capability_trace: unknown[];
  receipt_hash: string;
}

export function runConformance(
  ir: Record<string, unknown>,
  scenario: Record<string, unknown>,
): TevConformanceReceipt;
