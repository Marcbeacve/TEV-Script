import { dotnet } from './_framework/dotnet.js';

const logNode = document.getElementById('tev-log');
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);
const witnessToken = new URLSearchParams(window.location.search).get('tev_witness_token') || '';
const SHA256 = /^[0-9a-f]{64}$/;

let receiptHash = '';
let checkpointHash = '';
let witnessSent = false;
let gatePassed = false;

function emitWitness(status, detail) {
  if (witnessSent) return;
  witnessSent = true;
  const query = new URLSearchParams({
    gate: 'irv3browser',
    status: String(status),
    token: witnessToken,
    detail: String(detail),
  });
  void fetch('/__tev_witness?' + query.toString(), {
    method: 'GET',
    cache: 'no-store',
    keepalive: true,
  }).catch((error) => {
    originalError('IR_V3_BROWSER_WITNESS_TRANSPORT_ERROR', error);
  });
}

function fail(detail) {
  document.documentElement.setAttribute('data-tev-irv3-browser', 'FAIL');
  document.title = 'TEV_IR_V3_BROWSER_FAIL';
  emitWitness('FAIL', detail);
}

function append(value) {
  const line = String(value);
  logNode.textContent += line + '\n';

  if (line.startsWith('TEV_SCRIPT_IR_V3_BROWSER_RECEIPT_HASH=')) {
    receiptHash = line.slice('TEV_SCRIPT_IR_V3_BROWSER_RECEIPT_HASH='.length);
  }
  if (line.startsWith('TEV_SCRIPT_IR_V3_BROWSER_CHECKPOINT_HASH=')) {
    checkpointHash = line.slice('TEV_SCRIPT_IR_V3_BROWSER_CHECKPOINT_HASH='.length);
  }

  if (line.includes('TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=FAIL')) {
    fail('DOTNET_GATE_FAIL');
    return;
  }

  if (line.includes('TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=PASS')) {
    gatePassed = true;
    if (!SHA256.test(receiptHash)) {
      fail('RECEIPT_HASH_MISSING_OR_INVALID');
      return;
    }
    if (!SHA256.test(checkpointHash)) {
      fail('CHECKPOINT_HASH_MISSING_OR_INVALID');
      return;
    }
    document.documentElement.setAttribute('data-tev-irv3-browser', 'PASS');
    document.documentElement.setAttribute('data-tev-irv3-receipt-hash', receiptHash);
    document.documentElement.setAttribute('data-tev-irv3-checkpoint-hash', checkpointHash);
    document.title = 'TEV_IR_V3_BROWSER_PASS';
    emitWitness('PASS', `receipt=${receiptHash};checkpoint=${checkpointHash}`);
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
  if (!gatePassed && !witnessSent) {
    fail('DOTNET_EXITED_WITHOUT_GATE_WITNESS');
  }
} catch (error) {
  append('TEV_SCRIPT_IR_V3_BROWSER_JS_HOST_EXCEPTION=' + error);
  fail('JS_EXCEPTION');
  throw error;
}
