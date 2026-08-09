export class CanonicalError extends Error {
  readonly code: string;
  constructor(code: string, message: string);
}

export function scalarCompare(left: string, right: string): number;
export function canonicalJson(value: unknown): string;
export function sha256Hex(text: string): string;
export function canonicalHash(value: unknown): string;
