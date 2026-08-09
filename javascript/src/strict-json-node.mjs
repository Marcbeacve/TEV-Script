import { readFile } from "node:fs/promises";
import { parseStrictJson, StrictJsonError } from "./strict-json.mjs";

export async function readStrictJsonFile(filePath, options = {}) {
  const bytes = await readFile(filePath);
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (error) {
    throw new StrictJsonError(
      "TEVS_JSON_UTF8",
      "JSON input must be valid UTF-8",
      null,
      { cause: error },
    );
  }
  return parseStrictJson(text, options);
}
