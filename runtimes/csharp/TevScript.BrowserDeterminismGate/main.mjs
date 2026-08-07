import { dotnet } from './_framework/dotnet.js';

const params = new URLSearchParams(window.location.search);
const phase = params.get('phase') || '';
const witnessToken = params.get('tev_witness_token') || '';
const logNode = document.getElementById('tev-log');
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);

globalThis.tevGate7Phase = () => phase;
globalThis.tevGate7StoreLoad = (key) =>
  globalThis.localStorage.getItem(String(key)) || '';
globalThis.tevGate7StoreSave = (key, value) =>
  globalThis.localStorage.setItem(String(key), String(value));
globalThis.tevGate7StoreRemove = (key) =>
  globalThis.localStorage.removeItem(String(key));

const captured = {};
let witnessSent = false;

function capture(line) {
  const markerPrefixes = [
    'GATE7_BROWSER_FULL_RECEIPT_B64=',
    'GATE7_BROWSER_CHECKPOINT_HASH=',
    'GATE7_BROWSER_CONTINUATION_RECEIPT_B64=',
    'GATE7_BROWSER_SIGNED_UPDATE_RECEIPT_B64=',
    'GATE7_BROWSER_FAILURE_PHASE=',
    'GATE7_BROWSER_FAILURE_STAGE=',
    'GATE7_BROWSER_FAILURE_CODE=',
    'GATE7_BROWSER_FAILURE_TYPE=',
    'GATE7_BROWSER_FAILURE_MESSAGE_B64=',
  ];
  for (const prefix of markerPrefixes) {
    if (line.startsWith(prefix)) {
      captured[prefix.slice(0, -1)] = line.slice(prefix.length);
    }
  }
}

async function emitWitness(status, detail) {
  if (witnessSent) return;
  witnessSent = true;
  const body = JSON.stringify({
    gate: `gate7-browser-${phase}`,
    status: String(status),
    token: witnessToken,
    detail: String(detail),
    payload: captured,
  });
  try {
    await fetch('/__tev_gate7_witness', {
      method: 'POST',
      cache: 'no-store',
      keepalive: true,
      headers: { 'content-type': 'application/json' },
      body,
    });
  } catch (error) {
    originalError('GATE7_BROWSER_WITNESS_TRANSPORT_ERROR', error);
  }
}

function append(value) {
  const line = String(value);
  logNode.textContent += line + '\n';
  capture(line);

  if (line.includes('TEV_SCRIPT_BROWSER_DISTRIBUTED_DETERMINISM_GATE7=PASS')) {
    document.documentElement.setAttribute('data-tev-gate7', 'PASS');
    document.title = `TEV_GATE7_${phase.toUpperCase()}_PASS`;
    void emitWitness('PASS', 'DISTRIBUTED_DETERMINISM_PASS');
  }
  if (line.includes('TEV_SCRIPT_BROWSER_DISTRIBUTED_DETERMINISM_GATE7=FAIL')) {
    document.documentElement.setAttribute('data-tev-gate7', 'FAIL');
    document.title = `TEV_GATE7_${phase.toUpperCase()}_FAIL`;
    const stage = captured.GATE7_BROWSER_FAILURE_STAGE || 'UNKNOWN_STAGE';
    const type = captured.GATE7_BROWSER_FAILURE_TYPE || 'UNKNOWN_TYPE';
    const code = captured.GATE7_BROWSER_FAILURE_CODE || 'NONE';
    void emitWitness('FAIL', `DOTNET_GATE_FAIL_${stage}_${type}_${code}`);
  }
}

console.log = (...args) => {
  append(args.join(' '));
  originalLog(...args);
};
console.error = (...args) => {
  append(args.join(' '));
  originalError(...args);
};

try {
  await dotnet.run();
} catch (error) {
  append('GATE7_BROWSER_JS_HOST_EXCEPTION=' + error);
  await emitWitness('FAIL', 'JS_EXCEPTION');
  throw error;
}
