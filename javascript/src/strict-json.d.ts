export class StrictJsonError extends Error {
  readonly code: string;
  readonly offset: number | null;
}

export function parseStrictJson(
  text: string,
  options?: { maxDepth?: number },
): unknown;
