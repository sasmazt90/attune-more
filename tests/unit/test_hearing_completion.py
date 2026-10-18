"""Deterministic transport faults and token invariants, not hearing acceptance."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_playback_completion_cancellation_and_tokens(tmp_path):
 script=r'''
const fs=require('fs'),assert=require('assert/strict'),load=require('./tests/unit/ts_source_loader.cjs')(JSON.parse(fs.readFileSync(0,'utf8')).dir);
global.window=new EventTarget();global.document=new EventTarget();Object.defineProperty(global,'navigator',{value:{mediaDevices:new EventTarget()},configurable:true});
global.requestAnimationFrame=()=>1;global.cancelAnimationFrame=()=>{};
let mode='complete',liveGraphs=0;
class Context extends EventTarget{
 constructor(){super();this.sampleRate=48000;this.currentTime=0;this.state='running';this.destination={};}
 resume(){return Promise.resolve();}close(){this.state='closed';return Promise.resolve();}
 createBuffer(ch,length,rate){const data=Array.from({length:ch},()=>new Float32Array(length));return {duration:length/rate,copyToChannel:(a,c)=>data[c].set(a),getChannelData:c=>data[c]};}
 createAnalyser(){liveGraphs++;return {connect(){},disconnect(){liveGraphs--;}};}
 createBufferSource(){const c=this;return {connect(){},disconnect(){},start(at){if(mode==='throw')throw Error('START_FAILED');if(mode==='early')setTimeout(()=>{c.currentTime=at+.001;this.onended?.()},0);if(mode==='complete')setTimeout(()=>{c.currentTime=at+this.buffer.duration;this.onended?.()},0);},stop(){this.onended?.()}};}
}
global.AudioContext=Context;
(async()=>{
 const {HearingAudio}=load('hearingAudio'),{DigitTrialGate}=load('hearingProgress');
 const engine=new HearingAudio(()=>{});let timing;
 const receipt=await engine.tone(1000,-40,.01,'left',t=>timing=t);assert(receipt.audioEndedAt>=receipt.audioExpectedEnd);assert.equal(timing.audioStartedAt,.02);assert.equal(liveGraphs,0);
 mode='early';await assert.rejects(engine.tone(1000,-40,.1,'right'),/AUDIO_INCOMPLETE/);assert.equal(liveGraphs,0);
 mode='throw';await assert.rejects(engine.tone(1000,-40,.1,'right'),/START_FAILED/);assert.equal(liveGraphs,0);
 mode='missing';const pending=engine.tone(1000,-40,.1,'right');await new Promise(r=>setTimeout(r,0));engine.stop();await assert.rejects(pending,/AUDIO_CANCELLED/);assert.equal(liveGraphs,0);
 await assert.rejects(engine.tone(1000,-40,.01,'right'),/AUDIO_END_NOT_CONFIRMED/);assert.equal(liveGraphs,0);
 engine.close();engine.close();await assert.rejects(engine.tone(1000,-40,.1,'right'),/AUDIO_CLOSED/);
 const gate=new DigitTrialGate(),old=gate.begin();assert(!gate.take(old));assert(gate.open(old));assert(gate.take(old));assert(!gate.take(old));const fresh=gate.begin();assert(!gate.open(old));assert(!gate.take(old));assert(gate.open(fresh));gate.cancel();assert(!gate.take(fresh));const next=gate.begin();assert(gate.open(next));assert(!gate.take(fresh));assert(gate.take(next));
 console.log('PASS completion/early/start throw/missing/cancel/idempotent close/stale+duplicate+unplayed tokens');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
 result=subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True,encoding='utf8',timeout=15)
 assert result.returncode==0,result.stdout+result.stderr
