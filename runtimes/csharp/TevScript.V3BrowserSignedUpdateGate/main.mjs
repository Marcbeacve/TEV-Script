import { dotnet } from './_framework/dotnet.js';

const logNode = document.getElementById('tev-log');
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);
const witnessToken = new URLSearchParams(window.location.search).get('tev_witness_token') || '';
const SHA256 = /^[0-9a-f]{64}$/;
let packageSha = '';
let targetHash = '';
let witnessSent = false;
let gatePassed = false;

function emitWitness(status, detail) {
  if (witnessSent) return;
  witnessSent = true;
  const query = new URLSearchParams({
    gate: 'irv3signedbrowser',
    status: String(status),
    token: witnessToken,
    detail: String(detail),
  });
  void fetch('/__tev_witness?' + query.toString(), {
    method: 'GET',
    cache: 'no-store',
    keepalive: true,
  }).catch((error) => originalError('IR_V3_SIGNED_BROWSER_WITNESS_TRANSPORT_ERROR', error));
}

function fail(detail) {
  document.documentElement.setAttribute('data-tev-irv3-signed-browser', 'FAIL');
  document.title = 'TEV_IR_V3_SIGNED_BROWSER_FAIL';
  emitWitness('FAIL', detail);
}

function append(value) {
  const line = String(value);
  logNode.textContent += line + '\n';
  if (line.startsWith('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PACKAGE_SHA256='))
    packageSha = line.slice('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PACKAGE_SHA256='.length);
  if (line.startsWith('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TARGET_HASH='))
    targetHash = line.slice('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TARGET_HASH='.length);
  if (line.includes('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=FAIL')) {
    fail('DOTNET_GATE_FAIL');
    return;
  }
  if (line.includes('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=PASS')) {
    gatePassed = true;
    if (!SHA256.test(packageSha)) return fail('PACKAGE_SHA_MISSING_OR_INVALID');
    if (!SHA256.test(targetHash)) return fail('TARGET_HASH_MISSING_OR_INVALID');
    document.documentElement.setAttribute('data-tev-irv3-signed-browser', 'PASS');
    document.title = 'TEV_IR_V3_SIGNED_BROWSER_PASS';
    emitWitness('PASS', `package=${packageSha};target=${targetHash}`);
  }
}

console.log = (...args) => { append(args.join(' ')); originalLog(...args); };
console.error = (...args) => { append(args.join(' ')); originalError(...args); };

try {
  await dotnet.run();
  if (!gatePassed && !witnessSent) fail('DOTNET_EXITED_WITHOUT_GATE_WITNESS');
} catch (error) {
  append('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_JS_EXCEPTION=' + error);
  fail('JS_EXCEPTION');
  throw error;
}
