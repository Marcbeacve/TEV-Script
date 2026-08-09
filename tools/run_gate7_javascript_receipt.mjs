import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { canonicalJson } from '../javascript/src/canonical.mjs';
import { runConformance } from '../javascript/src/conformance.mjs';

function arg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  if (index >= 0 && index + 1 < process.argv.length) return process.argv[index + 1];
  if (fallback !== null) return fallback;
  throw new Error(`missing ${name}`);
}

const programPath = arg('--program');
const scenarioPath = arg('--scenario');
const outPath = arg('--out');
const repeat = Number(arg('--repeat', '1'));

const ir = JSON.parse(fs.readFileSync(programPath, 'utf8'));
const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));

let expected = null;
for (let index = 0; index < repeat; index += 1) {
  const receipt = runConformance(ir, scenario);
  const data = Buffer.from(canonicalJson(receipt) + '\n', 'utf8');
  if (expected === null) expected = data;
  else if (!expected.equals(data)) {
    throw new Error(`JAVASCRIPT_REPLAY_DIVERGENCE run=${index}`);
  }
}

fs.writeFileSync(outPath, expected);
console.log(`GATE7_JAVASCRIPT_REPLAY_${repeat}=PASS`);
