#!/usr/bin/env node
import fs from 'node:fs';
import crypto from 'node:crypto';

const PROGRAM_SCHEMA='TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1';
const INSTRUCTION_SCHEMA='TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_INSTRUCTION_V1';
const CHECKPOINT_SCHEMA='TEV_SCRIPT_PROGRAM_IR_V5_PROCESS_CHECKPOINT_V1';
const FIELD_SCHEMA='TEV_SCRIPT_MAX_V3_SEMANTIC_FIELD_V1';
const TX_SCHEMA='TEV_SCRIPT_MAX_V3_FIELD_TRANSFORMATION_V1';
const APPLY_SCHEMA='TEV_SCRIPT_MAX_V3_APPLY_RECEIPT_V1';
const EPOCH_SCHEMA='TEV_SCRIPT_OMEGA_EPOCH_IDENTITY_V1';
const CONT_SCHEMA='TEV_SCRIPT_OMEGA_CONTINUATION_RECEIPT_V1';
const QUANTUM_SCHEMA='TEV_SCRIPT_MAX_V3_QUANTUM_RESULT_V1';
const LANGUAGE_VERSION='3.0.0';
const PROFILE='semantic_process';
const MAX_SAFE=9007199254740991;
const ID=/^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const HEX=/^[0-9a-f]{64}$/;

class TevRuntimeError extends Error {
  constructor(code,message){super(`${code}: ${message}`);this.code=code;}
}
const fail=(code,message)=>{throw new TevRuntimeError(code,message)};
const sha=value=>{if(typeof value!=='string'||!HEX.test(value))fail('TEVS_JS_HASH','expected lowercase 64-hex');return value;};
const integer=(value,name)=>{if(typeof value!=='number'||!Number.isSafeInteger(value)||value<0)fail('TEVS_JS_INTEGER',`${name} must be safe integer >=0`);return value;};

function parseStrictJson(text){
  let i=0;
  const ws=()=>{while(i<text.length&&/[\x20\x09\x0a\x0d]/.test(text[i]))i++;};
  const string=()=>{
    if(text[i]!=='"')fail('TEVS_JS_JSON_STRING','expected string');
    const start=i++;
    let escaped=false;
    for(;i<text.length;i++){
      const ch=text[i];
      if(!escaped&&ch==='"'){
        i++;
        const raw=text.slice(start,i);
        try{return JSON.parse(raw);}catch{fail('TEVS_JS_JSON_STRING','invalid string escape');}
      }
      if(!escaped&&ch==='\\'){escaped=true;continue;}
      if(escaped){escaped=false;continue;}
      if(ch.charCodeAt(0)<0x20)fail('TEVS_JS_JSON_STRING','unescaped control character');
    }
    fail('TEVS_JS_JSON_STRING','unterminated string');
  };
  const number=()=>{
    const start=i;
    if(text[i]==='-')i++;
    if(i>=text.length)fail('TEVS_JS_JSON_NUMBER','invalid number');
    if(text[i]==='0'){
      i++;
      if(i<text.length&&/[0-9]/.test(text[i]))fail('TEVS_JS_JSON_NUMBER','leading zero forbidden');
    }else if(/[1-9]/.test(text[i])){
      while(i<text.length&&/[0-9]/.test(text[i]))i++;
    }else fail('TEVS_JS_JSON_NUMBER','invalid integer');
    if(i<text.length&&/[.eE]/.test(text[i]))fail('TEVS_JS_JSON_FLOAT','floating JSON numbers forbidden');
    const raw=text.slice(start,i);
    if(raw==='-0')fail('TEVS_JS_JSON_NEGATIVE_ZERO','negative zero forbidden');
    const value=Number(raw);
    if(!Number.isSafeInteger(value)||Math.abs(value)>MAX_SAFE)fail('TEVS_JS_JSON_NUMBER_RANGE','integer outside portable safe range');
    return value;
  };
  const literal=(token,value)=>{if(text.slice(i,i+token.length)!==token)fail('TEVS_JS_JSON_TOKEN','invalid token');i+=token.length;return value;};
  const value=()=>{
    ws();
    if(i>=text.length)fail('TEVS_JS_JSON_EOF','unexpected EOF');
    const ch=text[i];
    if(ch==='"')return string();
    if(ch==='{')return object();
    if(ch==='[')return array();
    if(ch==='t')return literal('true',true);
    if(ch==='f')return literal('false',false);
    if(ch==='n')return literal('null',null);
    if(ch==='-'||/[0-9]/.test(ch))return number();
    fail('TEVS_JS_JSON_TOKEN','non-standard JSON token');
  };
  const array=()=>{
    i++;ws();const out=[];
    if(text[i]===']'){i++;return out;}
    for(;;){out.push(value());ws();if(text[i]===']'){i++;return out;}if(text[i]!==',')fail('TEVS_JS_JSON_ARRAY','expected comma');i++;}
  };
  const object=()=>{
    i++;ws();const out=Object.create(null);const seen=new Set();
    if(text[i]==='}'){i++;return out;}
    for(;;){
      ws();const key=string();
      if(seen.has(key))fail('TEVS_JS_JSON_DUPLICATE_KEY',`duplicate key ${key}`);
      seen.add(key);ws();if(text[i]!==':')fail('TEVS_JS_JSON_OBJECT','expected colon');i++;
      out[key]=value();ws();if(text[i]==='}'){i++;return out;}if(text[i]!==',')fail('TEVS_JS_JSON_OBJECT','expected comma');i++;
    }
  };
  const result=value();ws();if(i!==text.length)fail('TEVS_JS_JSON_TRAILING','trailing JSON content');return result;
}

function escapeString(value){
  let out='"';
  for(let i=0;i<value.length;i++){
    const code=value.charCodeAt(i);
    switch(code){
      case 0x22:out+='\\"';break;
      case 0x5c:out+='\\\\';break;
      case 0x08:out+='\\b';break;
      case 0x0c:out+='\\f';break;
      case 0x0a:out+='\\n';break;
      case 0x0d:out+='\\r';break;
      case 0x09:out+='\\t';break;
      default:if(code<0x20||code>0x7e)out+='\\u'+code.toString(16).padStart(4,'0');else out+=value[i];
    }
  }
  return out+'"';
}

function canonicalJson(value){
  if(value===null)return 'null';
  if(value===true)return 'true';
  if(value===false)return 'false';
  if(typeof value==='number'){
    if(!Number.isSafeInteger(value)||Math.abs(value)>MAX_SAFE||Object.is(value,-0))fail('TEVS_JS_CANONICAL_NUMBER','nonportable integer');
    return String(value);
  }
  if(typeof value==='string')return escapeString(value);
  if(Array.isArray(value))return '['+value.map(canonicalJson).join(',')+']';
  if(typeof value==='object')return '{'+Object.keys(value).sort().map(key=>escapeString(key)+':'+canonicalJson(value[key])).join(',')+'}';
  fail('TEVS_JS_CANONICAL_VALUE','unsupported canonical value');
}

const hash=value=>crypto.createHash('sha256').update(canonicalJson(value),'utf8').digest('hex');

function exactKeys(object,keys,code){
  if(object===null||typeof object!=='object'||Array.isArray(object))fail(code,'object required');
  const observed=Object.keys(object).sort(),expected=[...keys].sort();
  if(observed.length!==expected.length||observed.some((value,index)=>value!==expected[index]))fail(code,'field set mismatch');
}

function validateFact(fact){
  exactKeys(fact,['relation','arguments','fact_hash'],'TEVS_JS_FACT_FIELDS');
  if(typeof fact.relation!=='string'||!ID.test(fact.relation)||!Array.isArray(fact.arguments))fail('TEVS_JS_FACT','invalid fact');
  const expected=hash({relation:fact.relation,arguments:fact.arguments});
  if(sha(fact.fact_hash)!==expected)fail('TEVS_JS_FACT_HASH','fact hash mismatch');
  return fact;
}

function validateField(field){
  exactKeys(field,['schema','profile','facts','field_hash'],'TEVS_JS_FIELD_FIELDS');
  if(field.schema!==FIELD_SCHEMA||typeof field.profile!=='string'||!ID.test(field.profile)||!Array.isArray(field.facts))fail('TEVS_JS_FIELD','invalid Field');
  field.facts.forEach(validateFact);
  const hashes=field.facts.map(fact=>fact.fact_hash);
  if(new Set(hashes).size!==hashes.length||hashes.some((value,index)=>index&&hashes[index-1]>value))fail('TEVS_JS_FIELD_ORDER','facts not canonical');
  const body={schema:FIELD_SCHEMA,profile:field.profile,facts:field.facts};
  if(sha(field.field_hash)!==hash(body))fail('TEVS_JS_FIELD_HASH','Field hash mismatch');
  return field;
}

function validateTransformation(transformation){
  exactKeys(transformation,['schema','transformation_id','required_before_hash','result_profile','remove_fact_hashes','add_facts','effect_set_hash','resource_vector_hash','proof_requirement_hashes','transformation_hash'],'TEVS_JS_TX_FIELDS');
  if(transformation.schema!==TX_SCHEMA||typeof transformation.transformation_id!=='string'||!ID.test(transformation.transformation_id))fail('TEVS_JS_TX','invalid transformation');
  if(transformation.required_before_hash!==null)sha(transformation.required_before_hash);
  if(transformation.result_profile!==null&&(typeof transformation.result_profile!=='string'||!ID.test(transformation.result_profile)))fail('TEVS_JS_TX_PROFILE','invalid result profile');
  if(!Array.isArray(transformation.remove_fact_hashes)||!Array.isArray(transformation.add_facts)||!Array.isArray(transformation.proof_requirement_hashes))fail('TEVS_JS_TX_ARRAY','invalid transformation arrays');
  transformation.remove_fact_hashes.forEach(sha);transformation.add_facts.forEach(validateFact);sha(transformation.effect_set_hash);sha(transformation.resource_vector_hash);transformation.proof_requirement_hashes.forEach(sha);
  const removes=[...transformation.remove_fact_hashes],adds=transformation.add_facts.map(fact=>fact.fact_hash),proofs=[...transformation.proof_requirement_hashes];
  for(const values of [removes,adds,proofs])if(new Set(values).size!==values.length||values.some((value,index)=>index&&values[index-1]>value))fail('TEVS_JS_TX_ORDER','transformation arrays not canonical');
  if(removes.some(value=>adds.includes(value)))fail('TEVS_JS_TX_COLLISION','remove/add collision');
  const body={schema:TX_SCHEMA,transformation_id:transformation.transformation_id,required_before_hash:transformation.required_before_hash,result_profile:transformation.result_profile,remove_fact_hashes:removes,add_facts:transformation.add_facts,effect_set_hash:transformation.effect_set_hash,resource_vector_hash:transformation.resource_vector_hash,proof_requirement_hashes:proofs};
  if(sha(transformation.transformation_hash)!==hash(body))fail('TEVS_JS_TX_HASH','transformation hash mismatch');
  return transformation;
}

function validateInstruction(instruction){
  exactKeys(instruction,['schema','kind','transformation_hash','next_pc','fact_hash','present_pc','absent_pc','target_pc','instruction_hash'],'TEVS_JS_INS_FIELDS');
  if(instruction.schema!==INSTRUCTION_SCHEMA||!['apply','branch_fact','jump','halt'].includes(instruction.kind))fail('TEVS_JS_INS','invalid instruction');
  const body={schema:INSTRUCTION_SCHEMA,kind:instruction.kind,transformation_hash:null,next_pc:null,fact_hash:null,present_pc:null,absent_pc:null,target_pc:null};
  if(instruction.kind==='apply'){body.transformation_hash=sha(instruction.transformation_hash);body.next_pc=integer(instruction.next_pc,'next_pc');}
  else if(instruction.kind==='branch_fact'){body.fact_hash=sha(instruction.fact_hash);body.present_pc=integer(instruction.present_pc,'present_pc');body.absent_pc=integer(instruction.absent_pc,'absent_pc');}
  else if(instruction.kind==='jump')body.target_pc=integer(instruction.target_pc,'target_pc');
  for(const key of ['transformation_hash','next_pc','fact_hash','present_pc','absent_pc','target_pc'])if(instruction[key]!==body[key])fail('TEVS_JS_INS_NORMAL','instruction unused fields must be null');
  if(sha(instruction.instruction_hash)!==hash(body))fail('TEVS_JS_INS_HASH','instruction hash mismatch');
  return instruction;
}

function validateProgram(program){
  exactKeys(program,['schema','language_version','profile','program_id','source_semantic_hash','initial_field','transformations','instructions','entry_pc','quantum_step_limit','authority_hash','program_hash'],'TEVS_JS_PROGRAM_FIELDS');
  if(program.schema!==PROGRAM_SCHEMA||program.language_version!==LANGUAGE_VERSION||program.profile!==PROFILE||typeof program.program_id!=='string'||!ID.test(program.program_id))fail('TEVS_JS_PROGRAM','unsupported program');
  sha(program.source_semantic_hash);sha(program.authority_hash);validateField(program.initial_field);
  if(!Array.isArray(program.transformations)||!Array.isArray(program.instructions)||program.instructions.length<1||program.instructions.length>65536)fail('TEVS_JS_PROGRAM_ARRAY','invalid program tables');
  program.transformations.forEach(validateTransformation);
  if(program.transformations.some(transformation=>transformation.proof_requirement_hashes.length))fail('TEVS_JS_PROGRAM_PROOF_OPEN','proof-open transformation');
  const transformationHashes=program.transformations.map(transformation=>transformation.transformation_hash);
  if(new Set(transformationHashes).size!==transformationHashes.length||transformationHashes.some((value,index)=>index&&transformationHashes[index-1]>value))fail('TEVS_JS_PROGRAM_TX_ORDER','transformations not canonical');
  program.instructions.forEach(validateInstruction);
  integer(program.entry_pc,'entry_pc');integer(program.quantum_step_limit,'quantum_step_limit');
  if(program.entry_pc>=program.instructions.length||program.quantum_step_limit<1||program.quantum_step_limit>1000000)fail('TEVS_JS_PROGRAM_BOUND','program bound invalid');
  const known=new Set(transformationHashes);
  for(const instruction of program.instructions){
    for(const pc of [instruction.next_pc,instruction.present_pc,instruction.absent_pc,instruction.target_pc])if(pc!==null&&pc>=program.instructions.length)fail('TEVS_JS_PROGRAM_TARGET','target out of range');
    if(instruction.kind==='apply'&&!known.has(instruction.transformation_hash))fail('TEVS_JS_PROGRAM_TX','unknown transformation');
  }
  const body={schema:PROGRAM_SCHEMA,language_version:LANGUAGE_VERSION,profile:PROFILE,program_id:program.program_id,source_semantic_hash:program.source_semantic_hash,initial_field:program.initial_field,transformations:program.transformations,instructions:program.instructions,entry_pc:program.entry_pc,quantum_step_limit:program.quantum_step_limit,authority_hash:program.authority_hash};
  if(sha(program.program_hash)!==hash(body))fail('TEVS_JS_PROGRAM_HASH','program hash mismatch');
  return program;
}

function processStateHash(programHash,fieldHash,pc){return hash({program_hash:sha(programHash),field_hash:sha(fieldHash),pc:integer(pc,'pc')});}

function validateContinuation(continuation){
  exactKeys(continuation,['schema','epoch_hash','epoch_index','previous_continuation_hash','result_hash','state_hash','observations_hash','effects_hash','resources_hash','continuation_hash'],'TEVS_JS_CONT_FIELDS');
  if(continuation.schema!==CONT_SCHEMA)fail('TEVS_JS_CONT_SCHEMA','invalid continuation schema');
  sha(continuation.epoch_hash);integer(continuation.epoch_index,'epoch_index');
  if(continuation.epoch_index===0){if(continuation.previous_continuation_hash!==null)fail('TEVS_JS_CONT_PREVIOUS','epoch0 previous must be null');}
  else sha(continuation.previous_continuation_hash);
  for(const key of ['result_hash','state_hash','observations_hash','effects_hash','resources_hash'])sha(continuation[key]);
  const body={schema:CONT_SCHEMA,epoch_hash:continuation.epoch_hash,epoch_index:continuation.epoch_index,previous_continuation_hash:continuation.previous_continuation_hash,result_hash:continuation.result_hash,state_hash:continuation.state_hash,observations_hash:continuation.observations_hash,effects_hash:continuation.effects_hash,resources_hash:continuation.resources_hash};
  if(sha(continuation.continuation_hash)!==hash(body))fail('TEVS_JS_CONT_HASH','continuation hash mismatch');
  return continuation;
}

function validateCheckpoint(program,checkpoint){
  exactKeys(checkpoint,['schema','program_hash','field','pc','next_epoch_index','previous_continuation','halted','checkpoint_hash'],'TEVS_JS_CP_FIELDS');
  if(checkpoint.schema!==CHECKPOINT_SCHEMA||checkpoint.program_hash!==program.program_hash)fail('TEVS_JS_CP_PROGRAM','checkpoint program mismatch');
  validateField(checkpoint.field);integer(checkpoint.pc,'pc');integer(checkpoint.next_epoch_index,'next_epoch_index');
  if(checkpoint.pc>=program.instructions.length||typeof checkpoint.halted!=='boolean')fail('TEVS_JS_CP','invalid checkpoint');
  if(checkpoint.next_epoch_index===0){if(checkpoint.previous_continuation!==null)fail('TEVS_JS_CP_PREVIOUS','epoch0 cannot have previous');}
  else{
    if(checkpoint.previous_continuation===null)fail('TEVS_JS_CP_PREVIOUS','resumed checkpoint requires previous');
    validateContinuation(checkpoint.previous_continuation);
    if(checkpoint.previous_continuation.epoch_index!==checkpoint.next_epoch_index-1||checkpoint.previous_continuation.state_hash!==processStateHash(program.program_hash,checkpoint.field.field_hash,checkpoint.pc))fail('TEVS_JS_CP_STATE','checkpoint continuation mismatch');
  }
  if(checkpoint.halted&&program.instructions[checkpoint.pc].kind!=='halt')fail('TEVS_JS_CP_HALTED','halted checkpoint not at halt');
  const body={schema:CHECKPOINT_SCHEMA,program_hash:program.program_hash,field:checkpoint.field,pc:checkpoint.pc,next_epoch_index:checkpoint.next_epoch_index,previous_continuation:checkpoint.previous_continuation,halted:checkpoint.halted};
  if(sha(checkpoint.checkpoint_hash)!==hash(body))fail('TEVS_JS_CP_HASH','checkpoint hash mismatch');
  return checkpoint;
}

function initialCheckpoint(program){
  const body={schema:CHECKPOINT_SCHEMA,program_hash:program.program_hash,field:program.initial_field,pc:program.entry_pc,next_epoch_index:0,previous_continuation:null,halted:false};
  return {...body,checkpoint_hash:hash(body)};
}

function applyField(field,transformation){
  validateField(field);validateTransformation(transformation);
  if(transformation.required_before_hash!==null&&transformation.required_before_hash!==field.field_hash)fail('TEVS_JS_APPLY_BEFORE','before pin mismatch');
  const facts=new Map(field.facts.map(fact=>[fact.fact_hash,fact]));
  for(const factHash of transformation.remove_fact_hashes){if(!facts.has(factHash))fail('TEVS_JS_APPLY_REMOVE','remove absent fact');facts.delete(factHash);}
  for(const fact of transformation.add_facts){if(facts.has(fact.fact_hash))fail('TEVS_JS_APPLY_ADD','duplicate add');facts.set(fact.fact_hash,fact);}
  const ordered=[...facts.values()].sort((left,right)=>left.fact_hash.localeCompare(right.fact_hash));
  const fieldBody={schema:FIELD_SCHEMA,profile:transformation.result_profile??field.profile,facts:ordered};
  const after={...fieldBody,field_hash:hash(fieldBody)};
  const status=transformation.proof_requirement_hashes.length?'PROOF_REQUIRED':'PASS';
  const receiptBody={schema:APPLY_SCHEMA,before_field_hash:field.field_hash,transformation_hash:transformation.transformation_hash,after_field_hash:after.field_hash,effect_set_hash:transformation.effect_set_hash,resource_vector_hash:transformation.resource_vector_hash,proof_requirement_hashes:transformation.proof_requirement_hashes,status};
  return [after,{...receiptBody,receipt_hash:hash(receiptBody)}];
}

function epochIdentity(index,computation,inputState,authority,previous){
  integer(index,'epoch_index');sha(computation);sha(inputState);sha(authority);
  if(index===0){if(previous!==null)fail('TEVS_JS_EPOCH_PREVIOUS','epoch0 previous');}else sha(previous);
  const body={schema:EPOCH_SCHEMA,epoch_index:index,computation_hash:computation,input_state_hash:inputState,authority_hash:authority,previous_continuation_hash:previous};
  return {...body,epoch_hash:hash(body)};
}

function continuationReceipt(epoch,result,state,observations,effects,resources){
  for(const value of [result,state,observations,effects,resources])sha(value);
  const body={schema:CONT_SCHEMA,epoch_hash:epoch.epoch_hash,epoch_index:epoch.epoch_index,previous_continuation_hash:epoch.previous_continuation_hash,result_hash:result,state_hash:state,observations_hash:observations,effects_hash:effects,resources_hash:resources};
  return {...body,continuation_hash:hash(body)};
}

function runQuantum(program,checkpoint){
  validateProgram(program);validateCheckpoint(program,checkpoint);
  if(checkpoint.halted)fail('TEVS_JS_RUNTIME_HALTED','halted checkpoint cannot resume');
  const inputState=processStateHash(program.program_hash,checkpoint.field.field_hash,checkpoint.pc);
  const previous=checkpoint.previous_continuation===null?null:checkpoint.previous_continuation.continuation_hash;
  const epoch=epochIdentity(checkpoint.next_epoch_index,program.program_hash,inputState,program.authority_hash,previous);
  let field=checkpoint.field,pc=checkpoint.pc,steps=0,status='SUSPENDED';
  const applied=[],effectHashes=[];
  const transformations=new Map(program.transformations.map(transformation=>[transformation.transformation_hash,transformation]));
  while(steps<program.quantum_step_limit){
    const instruction=program.instructions[pc];steps++;
    if(instruction.kind==='apply'){
      const [next,receipt]=applyField(field,transformations.get(instruction.transformation_hash));
      if(receipt.status!=='PASS')fail('TEVS_JS_RUNTIME_APPLY_OPEN','proof-open apply');
      field=next;applied.push(receipt.receipt_hash);effectHashes.push(receipt.effect_set_hash);pc=instruction.next_pc;
    }else if(instruction.kind==='branch_fact'){
      const present=field.facts.some(fact=>fact.fact_hash===instruction.fact_hash);pc=present?instruction.present_pc:instruction.absent_pc;
    }else if(instruction.kind==='jump')pc=instruction.target_pc;
    else{status='HALTED';break;}
  }
  const resultHash=hash({status,field_hash:field.field_hash,pc});
  const stateHash=processStateHash(program.program_hash,field.field_hash,pc);
  const continuation=continuationReceipt(epoch,resultHash,stateHash,hash([]),hash(effectHashes),hash({steps_used:steps}));
  const checkpointBody={schema:CHECKPOINT_SCHEMA,program_hash:program.program_hash,field,pc,next_epoch_index:checkpoint.next_epoch_index+1,previous_continuation:continuation,halted:status==='HALTED'};
  const nextCheckpoint={...checkpointBody,checkpoint_hash:hash(checkpointBody)};
  const quantumBody={schema:QUANTUM_SCHEMA,program_hash:program.program_hash,epoch,status,steps_used:steps,field,pc,apply_receipt_hashes:applied,result_hash:resultHash,continuation,next_checkpoint:nextCheckpoint};
  return {...quantumBody,quantum_hash:hash(quantumBody)};
}

function main(argv){
  let programPath=null,checkpointPath=null;
  for(let index=0;index<argv.length;index++){
    if(argv[index]==='--program')programPath=argv[++index];
    else if(argv[index]==='--checkpoint')checkpointPath=argv[++index];
    else fail('TEVS_JS_CLI_ARG',`unknown argument ${argv[index]}`);
  }
  if(!programPath)fail('TEVS_JS_CLI_ARG','--program required');
  const program=parseStrictJson(fs.readFileSync(programPath,'utf8'));validateProgram(program);
  const checkpoint=checkpointPath?parseStrictJson(fs.readFileSync(checkpointPath,'utf8')):initialCheckpoint(program);
  process.stdout.write(canonicalJson(runQuantum(program,checkpoint))+'\n');
}

if(import.meta.url===`file://${process.argv[1]}`){
  try{main(process.argv.slice(2));}
  catch(error){
    if(error instanceof TevRuntimeError){
      process.stderr.write(canonicalJson({schema:'TEV_SCRIPT_V3_JS_RUNTIME_DIAGNOSTIC_V1',status:'FAIL',code:error.code,message:error.message})+'\n');
      process.exit(2);
    }
    throw error;
  }
}

export {canonicalJson,hash,parseStrictJson,validateProgram,validateCheckpoint,initialCheckpoint,runQuantum};
