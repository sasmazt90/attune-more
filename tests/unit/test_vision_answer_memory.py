"""Identity, field retention and deduplication contracts for the live answer memory."""
import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def test_target_memory(tmp_path):
    script=r"""
const fs=require('fs'),assert=require('assert/strict'),load=require('./tests/unit/ts_source_loader.cjs')(JSON.parse(fs.readFileSync(0,'utf8')).dir);
const {VisionAnswerMemory}=load('visionAnswerMemory'),V=load('spokenVision'),m=new VisionAnswerMemory();
const t={sessionId:'s',eye:'RIGHT',targetId:'one'},append=(key,text)=>m.append(t,key,text,V.parseLetterAnswer(text));
assert(m.bind(t));assert(append('a:0','sağa yatmış'));assert.equal(m.answer.rotation,90);assert.equal(m.missing,'letter');
assert(!m.bind({...t}));assert(!append('a:0','sağa yatmış'));assert.equal(m.fragmentCount,1);assert(append('b:0',"Pırasanın P'si"));assert.equal(m.answer.letter,'P');assert.equal(m.answer.rotation,90);assert.equal(m.missing,null);assert.equal(m.heard,"sağa yatmış · Pırasanın P'si");
assert(append('b:1','P değil F'));assert.equal(m.answer.letter,'F');assert.equal(m.answer.rotation,90);m.markProcessed();assert(!append('late','E'));assert(!m.bind({...t}));assert(m.processed);
const next={...t,targetId:'two'};assert(m.bind(next));assert.equal(m.heard,'');assert.equal(m.fragmentCount,0);assert.equal(m.answer.rotation,undefined);assert(!m.append(t,'old','E',V.parseLetterAnswer('E')));
m.bind(t);assert(append('c:0','E'));assert.equal(m.missing,'orientation');assert(append('c:1','aşağı dönük'));assert.equal(m.answer.rotation,180);assert.equal(m.missing,null);
m.clear();m.bind(t);for(const [i,text] of ['baş aşağı','aynalı','P'].entries())assert(append('d:'+i,text));assert.equal(m.answer.rotation,180);assert(m.answer.mirrored);assert.equal(m.answer.letter,'P');assert.equal(m.missing,null);
assert(m.bind({...t,eye:'LEFT'}));assert.equal(m.heard,'');assert(!m.processed);m.clear();assert(!m.matches({...t,eye:'LEFT'}));
m.bind(t);m.append(t,'uncertain-direction','sağa yatmış',V.parseLetterAnswer('sağa yatmış'),.3);append('confident-letter','P');assert.equal(m.answer.rotation,90);assert.equal(m.missing,'orientation');append('confirm-direction','sağa yatmış');assert.equal(m.missing,null);
m.clear();m.bind(t);m.append(t,'uncertain-mirror','aynalı',V.parseLetterAnswer('aynalı'),.3);append('good-direction','baş aşağı');append('good-letter','P');assert.equal(m.missing,'orientation');assert(m.answer.mirrored);append('confirm-mirror','aynalı');assert.equal(m.missing,null);
"""
    result=subprocess.run(['node','-e',script],input=json.dumps({'dir':str(tmp_path)}),text=True,capture_output=True,cwd=ROOT)
    assert result.returncode==0,result.stdout+result.stderr
