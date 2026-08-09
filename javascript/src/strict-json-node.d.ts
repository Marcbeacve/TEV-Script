export function readStrictJsonFile(
  filePath: string | URL,
  options?: { maxDepth?: number },
): Promise<unknown>;
