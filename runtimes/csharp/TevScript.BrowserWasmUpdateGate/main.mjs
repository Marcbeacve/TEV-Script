import { dotnet } from './_framework/dotnet.js';

const params = new URLSearchParams(location.search);
const phase = params.get('phase') || '';
const witnessToken = params.get('tev_witness_token') || '';
const logNode = document.getElementById('tev-log');
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);
const oracle = Object.create(null);
let dotnetPass = false;
let witnessSent = false;
let failureCode = '';
let failureType = '';
let restoreRecord = '';

globalThis.tevGate6DPhase = () => phase;
globalThis.tevGate6DStoreLoad = (key) => localStorage.getItem(String(key));
globalThis.tevGate6DStoreSave = (key, value) => localStorage.setItem(String(key), String(value));
globalThis.tevGate6DStoreRemove = (key) => localStorage.removeItem(String(key));

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
function base64Url(value) {
  return value.replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}
async function webCryptoOracle() {
  for (const key of ['X','Y','BODY_BASE64','SIGNATURE_BASE64']) {
    if (!oracle[key]) throw new Error('missing oracle field ' + key);
  }
  const publicKey = await crypto.subtle.importKey(
    'jwk',
    { kty:'EC', crv:'P-256', x:base64Url(oracle.X), y:base64Url(oracle.Y), ext:true, key_ops:['verify'] },
    { name:'ECDSA', namedCurve:'P-256' },
    false,
    ['verify']);
  const valid = await crypto.subtle.verify(
    { name:'ECDSA', hash:'SHA-256' },
    publicKey,
    base64ToBytes(oracle.SIGNATURE_BASE64),
    base64ToBytes(oracle.BODY_BASE64));
  if (!valid) throw new Error('WebCrypto rejected TEV ES256 fixture');
  originalLog('GATE6D_BROWSER_WEBCRYPTO_ORACLE=PASS');
  return true;
}
function emitWitness(status, detail) {
  if (witnessSent) return;
  witnessSent = true;
  const query = new URLSearchParams({gate:'gate6d-browser-' + phase,status,token:witnessToken,detail});
  void fetch('/__tev_witness?' + query.toString(), {method:'GET',cache:'no-store',keepalive:true})
    .catch((error) => originalError('GATE6D_WITNESS_TRANSPORT_ERROR', error));
}
async function maybeFinish() {
  if (!dotnetPass || witnessSent) return;
  try {
    await webCryptoOracle();
    document.documentElement.setAttribute('data-tev-gate6d', 'PASS');
    document.title = 'TEV_GATE6D_PASS_' + phase.toUpperCase();
    emitWitness('PASS', 'SIGNED_UPDATE_' + phase.toUpperCase() + '_WEBCRYPTO_PASS');
  } catch (error) {
    append('GATE6D_WEBCRYPTO_ORACLE_FAIL=' + error);
    emitWitness('FAIL', 'WEBCRYPTO_ORACLE_FAIL');
  }
}
function append(value) {
  const line = String(value);
  logNode.textContent += line + '\n';
  for (const key of ['X','Y','BODY_BASE64','SIGNATURE_BASE64']) {
    const prefix = 'GATE6D_ORACLE_' + key + '=';
    if (line.startsWith(prefix)) oracle[key] = line.slice(prefix.length);
  }
  if (line.startsWith('GATE6D_BROWSER_FAILURE_CODE='))
    failureCode = line.slice('GATE6D_BROWSER_FAILURE_CODE='.length);
  if (line.startsWith('GATE6D_BROWSER_FAILURE_TYPE='))
    failureType = line.slice('GATE6D_BROWSER_FAILURE_TYPE='.length);
  if (line.startsWith('GATE6D_BROWSER_RESTORE_STORE_RECORD='))
    restoreRecord = line.slice('GATE6D_BROWSER_RESTORE_STORE_RECORD='.length);
  if (line.includes('TEV_SCRIPT_BROWSER_WASM_SIGNED_UPDATE_GATE_6D=PASS')) {
    dotnetPass = true;
    void maybeFinish();
  }
  if (line.includes('TEV_SCRIPT_BROWSER_WASM_SIGNED_UPDATE_GATE_6D=FAIL')) {
    let detail = 'DOTNET_GATE_FAIL';
    if (restoreRecord === 'MISSING') detail += '_RESTORE_STORE_MISSING';
    else if (failureCode) detail += '_CODE_' + failureCode;
    else if (failureType) detail += '_TYPE_' + failureType;
    emitWitness('FAIL', detail);
  }
}
console.log=(...args)=>{append(args.join(' '));originalLog(...args);};
console.error=(...args)=>{append(args.join(' '));originalError(...args);};
try { await dotnet.run(); }
catch (error) { append('GATE6D_JS_HOST_EXCEPTION=' + error); emitWitness('FAIL','JS_EXCEPTION'); throw error; }
