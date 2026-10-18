"""Actual record transaction guard, isolated storage; no extra full session."""
import json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_hearing_save_revoke_null_and_duplicate_guard(tmp_path):
 script=r'''
const fs=require('fs'),assert=require('assert/strict'),loaderModule={exports:{}};
// Match production tsconfig esModuleInterop for JSON default imports.
new Function('require','module',fs.readFileSync('./tests/unit/ts_source_loader.cjs','utf8').replace('target: ts.ScriptTarget.ES2022','target: ts.ScriptTarget.ES2022, esModuleInterop: true'))(require,loaderModule);
const load=loaderModule.exports(JSON.parse(fs.readFileSync(0,'utf8')).dir);
global.window=new EventTarget();Object.defineProperty(global,'navigator',{value:{locks:{request:async(_name,fn)=>fn()}},configurable:true});global.localStorage={data:new Map(),getItem(k){return this.data.get(k)??null},setItem(k,v){this.data.set(k,String(v))},removeItem(k){this.data.delete(k)}};
const {appendHealthRecord}=load('healthRecords');
const consent={version:1,services:{hearing:{at:'2026-10-17T00:00:00Z',permissions:['local']}}};localStorage.setItem('attune_health_processing_v1',JSON.stringify(consent));
const old={id:'existing-preserved',timestamp:'2020-01-01T00:00:00Z',methodVersion:'old',deviceSession:'prior-device',unit:'dB-SNR',value:null,validTrials:24};localStorage.setItem('attune_hearing_history_v1',JSON.stringify([old]));localStorage.setItem('attune_hearing_latest_v1',JSON.stringify(old));
const record={id:'controlled-new',unit:'dBFS-peak',value:[{ear:'left',frequency:1000,value:null,status:'upper-limit'}],methodVersion:'digital-hearing-v1',deviceSession:'engineering-device'};
(async()=>{
 const before=JSON.stringify([...localStorage.data]);localStorage.setItem('attune_privacy_hearing_save_allowed','false');const denied=JSON.stringify([...localStorage.data]);
 await assert.rejects(appendHealthRecord('hearing',record,{},()=>localStorage.getItem('attune_privacy_hearing_save_allowed')!=='false'),/Kayıt izni/);assert.equal(JSON.stringify([...localStorage.data]),denied);
 localStorage.setItem('attune_privacy_hearing_save_allowed','true');await appendHealthRecord('hearing',record);await appendHealthRecord('hearing',record);const history=JSON.parse(localStorage.getItem('attune_hearing_history_v1'));assert.equal(history.length,2);assert.deepEqual(history[1],old);assert.equal(history[0].value[0].value,null);assert.equal(history[1].value,null);assert.notEqual(history[0].unit,history[1].unit);assert.notEqual(history[0].methodVersion,history[1].methodVersion);assert.notEqual(history[0].deviceSession,history[1].deviceSession);
 localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{}}));const revoked=JSON.stringify([...localStorage.data]);await assert.rejects(appendHealthRecord('hearing',{...record,id:'forbidden'}),/Kayıt izni/);assert.equal(JSON.stringify([...localStorage.data]),revoked);
 console.log('PASS save-off/revoke no writes; one ID once; null/different units/device/method/old data preserved');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
 result=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True,encoding='utf8',env={**os.environ,'NODE_PATH':str(ROOT/'node_modules')},timeout=15)
 assert result.returncode==0,result.stdout+result.stderr
