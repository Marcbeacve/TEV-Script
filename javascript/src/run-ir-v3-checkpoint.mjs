import fs from "node:fs";
import { RuntimeCheckpointV2 } from "./runtime-checkpoint-v2.mjs";
import { ScriptRuntimeV3 } from "./runtime-v3.mjs";
import { parseStrictJson } from "./strict-json.mjs";

function main(argv) {
  if (argv.length !== 1) {
    console.error("usage: run-ir-v3-checkpoint.mjs <validator-cases.json>");
    return 2;
  }
  const cases = parseStrictJson(fs.readFileSync(argv[0], "utf8"));
  const program = cases.valid_program;
  const runtime = new ScriptRuntimeV3(program);
  runtime.invoke("E", "start");
  const checkpoint = RuntimeCheckpointV2.capture(runtime);
  process.stdout.write(checkpoint.toCanonicalJson());
  return 0;
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(`${error.code ?? error.name}: ${error.message}`);
  process.exitCode = 1;
}
