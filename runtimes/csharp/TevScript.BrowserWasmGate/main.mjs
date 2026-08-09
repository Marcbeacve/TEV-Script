import { dotnet } from './_framework/dotnet.js';

const logNode = document.getElementById('tev-log');
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);
const witnessToken =
  new URLSearchParams(window.location.search).get('tev_witness_token') || '';

let witnessSent = false;

function emitWitness(status, detail) {
  if (witnessSent) {
    return;
  }
  witnessSent = true;

  const query = new URLSearchParams({
    gate: 'gate6b',
    status: String(status),
    token: witnessToken,
    detail: String(detail),
  });

  void fetch('/__tev_witness?' + query.toString(), {
    method: 'GET',
    cache: 'no-store',
    keepalive: true,
  }).catch((error) => {
    originalError('GATE6B_WITNESS_TRANSPORT_ERROR', error);
  });
}

function append(value) {
  const line = String(value);
  logNode.textContent += line + '\n';

  if (line.includes('TEV_SCRIPT_PURE_CORE_BROWSER_WASM_GATE_6B=PASS')) {
    document.documentElement.setAttribute('data-tev-gate6b', 'PASS');
    document.title = 'TEV_GATE6B_PASS';
    emitWitness('PASS', 'TEV_CORE_BROWSER_WASM_PASS');
  }

  if (line.includes('TEV_SCRIPT_PURE_CORE_BROWSER_WASM_GATE_6B=FAIL')) {
    document.documentElement.setAttribute('data-tev-gate6b', 'FAIL');
    document.title = 'TEV_GATE6B_FAIL';
    emitWitness('FAIL', 'TEV_CORE_BROWSER_WASM_FAIL');
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
  append('GATE6B_JS_HOST_EXCEPTION=' + error);
  document.documentElement.setAttribute('data-tev-gate6b', 'FAIL');
  document.title = 'TEV_GATE6B_FAIL';
  emitWitness('FAIL', 'JS_EXCEPTION');
  throw error;
}
