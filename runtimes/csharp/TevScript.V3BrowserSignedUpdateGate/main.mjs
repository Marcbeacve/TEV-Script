import { dotnet } from './_framework/dotnet.js';

const logNode = document.getElementById('tev-log');
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);
const witnessToken = new URLSearchParams(window.location.search).get('tev_witness_token') || '';
const SHA256 = /^[0-9a-f]{64}$/;
let witnessSent = false;
let managedReportReceived = false;
const runtimeMessages = [];

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

function describeError(error) {
  if (error === null || typeof error !== 'object') return String(error);
  const detail = {};
  for (const name of Object.getOwnPropertyNames(error)) detail[name] = error[name];
  return `${error.constructor?.name || 'Object'}:${JSON.stringify(detail)}`;
}

function append(value) {
  const line = String(value);
  logNode.textContent += line + '\n';
}

globalThis.tevIrV3SignedBrowserReport = (status, reportedPackageSha, reportedTargetHash, detail) => {
  if (managedReportReceived || witnessSent) {
    fail('DUPLICATE_OR_LATE_MANAGED_REPORT');
    return;
  }
  if (status !== 'PASS') {
    managedReportReceived = true;
    fail('DOTNET_GATE_FAIL:' + String(detail));
    return;
  }

  const packageSha = String(reportedPackageSha);
  const targetHash = String(reportedTargetHash);
  if (!SHA256.test(packageSha)) {
    managedReportReceived = true;
    fail('PACKAGE_SHA_MISSING_OR_INVALID');
    return;
  }
  if (!SHA256.test(targetHash)) {
    managedReportReceived = true;
    fail('TARGET_HASH_MISSING_OR_INVALID');
    return;
  }

  managedReportReceived = true;
  append('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_MANAGED_REPORT=PASS');
  append('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PACKAGE_SHA256=' + packageSha);
  append('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TARGET_HASH=' + targetHash);
  document.documentElement.setAttribute('data-tev-irv3-signed-browser', 'PASS');
  document.documentElement.setAttribute('data-tev-irv3-signed-package-sha256', packageSha);
  document.documentElement.setAttribute('data-tev-irv3-signed-target-hash', targetHash);
  document.title = 'TEV_IR_V3_SIGNED_BROWSER_PASS';
  emitWitness('PASS', `package=${packageSha};target=${targetHash}`);
};

console.log = (...args) => { append(args.join(' ')); originalLog(...args); };
console.error = (...args) => { append(args.join(' ')); originalError(...args); };

try {
  dotnet.withModuleConfig({
    out: (message) => { runtimeMessages.push(String(message)); append(message); originalLog(message); },
    err: (message) => { runtimeMessages.push(String(message)); append(message); originalError(message); },
  });
  const runtime = await dotnet.create();
  const exitCode = await runtime.runMain('TevScript.V3BrowserSignedUpdateGate');
  if (!managedReportReceived && !witnessSent) {
    fail('DOTNET_EXITED_WITHOUT_MANAGED_REPORT:' + String(exitCode));
  }
} catch (error) {
  append('TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_JS_EXCEPTION=' + error);
  fail('JS_EXCEPTION:' + describeError(error) + ':RUNTIME=' + runtimeMessages.slice(-20).join('|'));
  throw error;
}
