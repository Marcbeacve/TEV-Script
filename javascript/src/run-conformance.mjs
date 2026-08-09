import path from "node:path";
import process from "node:process";
import { canonicalJson } from "./canonical.mjs";
import { runConformance } from "./conformance.mjs";
import { readStrictJsonFile } from "./strict-json-node.mjs";

if (!process.argv[2]) {
  throw new Error("usage: node src/run-conformance.mjs <scenario.json>");
}

const scenarioPath = path.resolve(process.argv[2]);
const scenario = await readStrictJsonFile(scenarioPath);
const irPath = path.resolve(path.dirname(scenarioPath), scenario.program);
const ir = await readStrictJsonFile(irPath);
const receipt = runConformance(ir, scenario);
process.stdout.write(`${canonicalJson(receipt)}\n`);
