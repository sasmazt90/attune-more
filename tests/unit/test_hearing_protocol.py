"""Simulated responses and actual PCM; never human hearing acceptance."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_digital_staircases_signals_and_snr(tmp_path):
 script=r'''
const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const path=JSON.parse(fs.readFileSync(0,'utf8')).path;
fs.writeFileSync(path,ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/hearingProtocol.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);
const H=require(path),C=H.HEARING_CONFIG;
assert(Math.abs(H.amplitude(5)/H.amplitude(0)-Math.pow(10,5/20))<1e-12);
for(const hz of C.frequencies){const p=H.tonePCM(hz,-40,1,48000);assert(p[0]===0&&p.at(-1)===0);assert(H.peak(p)<=.010001);assert(Math.abs(H.rms(p)-.01/Math.sqrt(2))<.0003);let energy=0;for(let i=0;i<p.length;i++)energy+=p[i]*Math.sin(2*Math.PI*hz*i/48000);assert(energy/p.length>.004);}
assert.throws(()=>H.tonePCM(1000,-29,1,48000));
for(const args of [[NaN,-40,1,48000],[1000,NaN,1,48000],[1000,-40,Infinity,48000],[1000,-40,1,NaN],[9000,-40,1,48000],[1000,-40,3,48000]])assert.throws(()=>H.tonePCM(...args));

let s=new H.FrequencyStaircase(),out;for(let i=0;i<40&&!out;i++)out=s.response(s.level>=-50);assert.equal(out.status,'threshold');assert.equal(out.value,-50);assert(s.asc.get(-50).heard>=2);
s=new H.FrequencyStaircase();out=null;for(let i=0;i<40&&!out;i++)out=s.response(false);assert.deepEqual(out,{value:null,status:'upper-limit'});
s=new H.FrequencyStaircase();out=null;for(let i=0;i<40&&!out;i++)out=s.response(true);assert.equal(out.status,'lower-limit');assert.equal(out.value,null);
s=new H.FrequencyStaircase();s.trials=29;out=s.response(false);assert.deepEqual(out,{value:null,status:'max-trials'});assert.throws(()=>s.response(false),/STAIRCASE_FINISHED/);
const rand=H.seeded(42);assert.equal(rand(),H.seeded(42)());
const speech=new Float32Array(48000),noise=new Float32Array(48000);for(let i=0;i<48000;i++){speech[i]=Math.sin(i*.1)*.1;noise[i]=Math.sin(i*.17)*.1;}
for(const snr of [-15,0,15]){const m=H.mixDigits(speech,noise,snr);assert(Math.abs(m.actualSNR-snr)<1e-9);assert(m.peak<=C.mixturePeak+1e-7);assert(Math.abs(20*Math.log10(m.speechRMS/m.noiseRMS)-snr)<1e-9);}
assert.throws(()=>H.mixDigits(speech,noise,NaN));assert.throws(()=>H.mixDigits(speech,new Float32Array(2),0));assert.throws(()=>H.mixDigits(new Float32Array(48000),noise,0));
const invalid=speech.slice();invalid[20]=NaN;assert.throws(()=>H.mixDigits(invalid,noise,0));
const d=new H.DigitStaircase();assert.equal(d.snr,0);d.respond([1,2,3],[1,2,3],true);assert.equal(d.scored.length,0);assert.equal(d.snr,0);
for(let i=0;i<24;i++)d.respond([1,2,3],d.snr>=-2?[1,2,3]:[9,9,9]);assert.equal(d.scored.length,24);assert(d.result().value!==null);assert(d.result().repeated===1);
const cap=new H.DigitStaircase();for(let i=0;i<24;i++)cap.respond([1,2,3],[9,9,9]);assert.equal(cap.snr,15);assert.equal(cap.result().value,null);
const partial=new H.DigitStaircase();partial.respond([1,2,3],[1,2,9]);partial.respond([1,2,3],[1,2,3],true);assert.equal(partial.result().digitAccuracy,2/3);assert.equal(partial.result().tripletAccuracy,0);assert.equal(partial.result().validTrials,1);assert.equal(partial.result().repeated,1);
'''
 r=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'path':str(tmp_path/'hearing.js')}),text=True,capture_output=True,encoding='utf8');assert r.returncode==0,r.stdout+r.stderr
