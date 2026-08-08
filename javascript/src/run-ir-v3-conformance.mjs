import { readFile } from "node:fs/promises";
import process from "node:process";

import { runIrV3Conformance } from "./ir-v3-conformance.mjs";
import { parseStrictJson } from "./strict-json.mjs";

async function main() {
  if (process.argv.length !== 4) {
    process.stderr.write("usage: node run-ir-v3-conformance.mjs <program.json> <scenario.json>\n");
    process.exitCode = 2;
    return;
  }
  const [programPath, scenarioPath] = process.argv.slice(2);
  const [programText, scenarioText] = await Promise.all([
    readFile(programPath, "utf8"),
    readFile(scenarioPath, "utf8"),
  ]);
  const program = parseStrictJson(programText);
  const scenario = parseStrictJson(scenarioText);
  const bundle = runIrV3Conformance(program, scenario);
  process.stdout.write(bundle.canonicalJson);
}

main().catch((error) => {
  const code = error?.code ?? error?.name ?? "ERROR";
  process.stderr.write(`${code}: ${error?.message ?? String(error)}\n`);
  process.exitCode = 1;
});
