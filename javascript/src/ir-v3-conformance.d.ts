export interface IrV3ConformanceReceiptBundle {
  receipt: Record<string, unknown>;
  canonicalJson: string;
  receiptHash: string;
}

export function runIrV3Conformance(
  ir: Record<string, unknown>,
  scenario: Record<string, unknown>,
): IrV3ConformanceReceiptBundle;
