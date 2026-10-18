"""Focused source contracts for the user's vision feedback, not physical acceptance."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_feedback_parser_session_gate_and_legacy(tmp_path):
 script = r"""
const fs=require('fs'),assert=require('assert/strict');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;const load=require('./tests/unit/ts_source_loader.cjs')(dir);
const V=load('spokenVision'),C=load('cameraStability'),G=load('visionResponseGate');
const parse=text=>V.mergeLetterAnswer({},V.parseLetterAnswer(text));
for(const text of ['Aşağı dönük E harfi','aşağıya dönük elma','elmanın E’si baş aşağı']){const a=parse(text);assert.equal(a.letter,'E',text);assert.equal(a.rotation,180,text);assert(!a.clarify,text);}
for(const text of ['Pırasanın P’si','Pırasa','Düz pırasa','aşağı dönük pırasa','Baş aşağı ve aynalı Paris’in P’si'])assert.equal(parse(text).letter,'P',text);
assert.equal(parse('Sağa yatmış elma').letter,'E');assert.equal(parse('Fasulyenin F’si').letter,'F');
for(const text of ['Baş aşağı ve aynalı P','Aynalı ve baş aşağı P']){const a=parse(text);assert.equal(a.rotation,180);assert.equal(a.mirrored,true);assert(!a.clarify);}
for(const [text,r] of [['Sağa yatmış ve aynalı P',90],['Sola dönük ve aynalı P',270]]){const a=parse(text);assert.equal(a.rotation,r);assert(a.mirrored&&!a.clarify);}
let a=V.mergeLetterAnswer({},V.parseLetterAnswer('aşağı dönük'));a=V.mergeLetterAnswer(a,V.parseLetterAnswer('Elmanın E’si'));assert.equal(a.rotation,180);assert.equal(a.letter,'E');assert(!a.clarify);
a=V.mergeLetterAnswer({},V.parseLetterAnswer('P'));a=V.mergeLetterAnswer(a,V.parseLetterAnswer('baş aşağı ve aynalı'));assert.equal(a.letter,'P');assert.equal(a.rotation,180);assert(a.mirrored&&!a.clarify);
a=V.mergeLetterAnswer({},V.parseLetterAnswer('aynalı'));a=V.mergeLetterAnswer(a,V.parseLetterAnswer('baş aşağı P'));assert(a.mirrored&&a.rotation===180&&!a.clarify);
assert.equal(parse('E değil, F düz').letter,'F');assert.equal(parse('baş aşağı E değil F').rotation,180);assert.equal(parse('baş aşağı E değil F').letter,'F');assert.equal(V.mergeLetterAnswer({letter:'P'},V.parseLetterAnswer('ters')).clarify,'reverse');assert(parse('düz E veya F').clarify);assert(parse('Z düz').clarify);assert(parse('elma fasulye düz').clarify);
a=parse('ters P');assert.equal(a.clarify,'reverse');a=V.mergeLetterAnswer(a,V.parseLetterAnswer('baş aşağı'));assert.equal(a.letter,'P');assert(!a.clarify);
for(const text of ['göremiyorum','tekrar','duraklat','devam et','bitir']){assert(V.parseLetterAnswer(text).command);assert(!V.parseLetterAnswer(text).letter);}
for(const text of Object.values(V.LETTER_INSTRUCTIONS))assert(V.isLetterInstructionEcho(text),text);
for(const text of ['E','P','aşağı dönük','baş aşağı ve aynalı','aşağı dönük pırasa','sola yatmış P'])assert(!V.isLetterInstructionEcho(text),text);
const open={state:'open',ear:.3,method:'controlled'},closed={...open,state:'closed'},covered={...open,state:'covered'},uncertain={...open,state:'uncertain'};
const cond=(s,t=1000)=>({observedAt:t,cameraLive:true,modelActive:true,faceCount:1,qualityValid:true,positionValid:true,relativeScaleChange:0,distancePolicy:'head-anchors-hysteresis-v1',distanceState:'stable',right:s.eye==='RIGHT'?open:closed,left:s.eye==='RIGHT'?closed:open});
const s=new V.SpokenLetterSession(),geom=()=>({viewportWidthCssPx:s.sizePx,viewportHeightCssPx:s.sizePx,pathWidthCssPx:s.sizePx*.7,pathHeightCssPx:s.sizePx*.7,strokeWidthCssPx:s.sizePx*.1,measuredAt:1099,method:'dom-svg-css-pixels'});
const answer=()=>({letter:s.letter,rotation:s.transform.rotation,mirrored:s.transform.mirrored});
const reply=(a)=>s.respond(a,cond(s),1100,s.presentationId,geom());
s.present(1000);let size=s.sizePx;assert(reply(answer()));assert.equal(s.sizePx,size);s.present(1000);assert(reply(answer()));assert(s.sizePx<size);
size=s.sizePx;s.present(1000);assert(reply({letter:s.letter==='P'?'F':'P',rotation:s.transform.rotation,mirrored:s.transform.mirrored}));assert.equal(s.sizePx,size);assert.equal(s.trials.at(-1).letterCorrect,false);
s.present(1000);assert(reply({command:'not-visible'}));assert(s.sizePx>size);assert(s.trials.at(-1).notVisible);
size=s.sizePx;s.present(1000);s.letter='P';s.transform=V.legacyTransform('right');s.orientation='right';assert(reply(parse('sola yatmış P')));assert.equal(s.sizePx,size);assert(!s.trials.at(-1).combinedCorrect);
const oldId=s.presentationId;assert(!s.respond(parse('düz P'),cond(s),1100,oldId,geom()));
while(!s.completed){s.present(1000);const id=s.presentationId;assert(reply(answer()));assert(!s.respond(answer(),cond(s),1100,id,geom()));if(s.trials.length===12)assert.equal(s.sizePx,V.LETTER_RULES.startPx);}
assert.equal(s.trials.length,24);assert.equal(s.trials.filter(t=>t.eye==='RIGHT').length,12);assert.equal(s.trials.filter(t=>t.eye==='LEFT').length,12);
assert(s.trials.every(t=>t.protocolVersion===V.LETTER_PROTOCOL&&t.methodVersion===V.LETTER_METHOD&&t.transform.order==='mirror-then-rotate'));
const legacy={eye:'RIGHT',letter:'E',orientation:'down',answer:{letter:'E',orientation:'mirror'},valid:true,notVisible:false,protocolVersion:'spoken-letter-v1'};const before=JSON.stringify(legacy);assert(V.scoreLetterTrial(legacy).combinedCorrect);assert.equal(JSON.stringify(legacy),before);
const summary=V.performanceForEye([{...legacy,letter:'P',orientation:'right',answer:{letter:'P',orientation:'left'}},{...legacy,letter:'F',orientation:'upright',answer:{letter:'P',orientation:'upright'}}],'RIGHT');assert.equal(summary.letter.percentage,50);assert.equal(summary.orientation.percentage,50);assert.equal(summary.average,50);assert.equal(V.performanceForEye([],'RIGHT').average,null);
const gate=new G.VisionResponseGate(),fresh=cond({eye:'RIGHT'},1000);assert.equal(gate.assess(fresh,'RIGHT',1100),fresh);
const transient={...fresh,observedAt:1200,positionValid:false,relativeScaleChange:null,distanceState:'unknown',blocker:'distance-unknown',left:uncertain};assert.equal(gate.assess(transient,'RIGHT',1250),fresh);assert.equal(gate.assess(transient,'RIGHT',1400),transient);
for(const state of [closed,covered])assert.equal(V.letterConditionFailure({...fresh,left:state},'RIGHT',1100),null);
for(const change of [{left:open},{right:closed},{right:covered},{positionValid:false,relativeScaleChange:.2,distanceState:'near',blocker:'recede'},{observedAt:0}]){const g=new G.VisionResponseGate();g.assess(fresh,'RIGHT',1100);const bad={...fresh,...change};assert.equal(g.assess(bad,'RIGHT',1250),bad);assert(V.letterConditionFailure(bad,'RIGHT',1250));}
const points=Array.from({length:478},()=>({x:.5,y:.5}));points[234]={x:.3,y:.5};points[454]={x:.7,y:.5};points[10]={x:.5,y:.2};points[1]={x:.5,y:.5};const crop=C.visionCameraCrop(points,4/3);for(const id of [17,152,172,397])points[id]={x:.5,y:.9};assert.deepEqual(C.visionCameraCrop(points,4/3),crop);
// Match Next's JSON default-import interop while compiling actual source/data.
const interop={exports:{}};new Function('require','module',fs.readFileSync('tests/unit/ts_source_loader.cjs','utf8').replace('target: ts.ScriptTarget.ES2022','target: ts.ScriptTarget.ES2022, esModuleInterop: true'))(require,interop);
const H=interop.exports(dir)('healthHistorySeries'),geometry={viewportWidthCssPx:120,viewportHeightCssPx:120,pathWidthCssPx:80,pathHeightCssPx:100,strokeWidthCssPx:10,method:'dom-svg-css-pixels'};
const stored=[{...legacy,letter:'P',orientation:'right',answer:{letter:'P',orientation:'left'},renderedGeometry:geometry},{...legacy,letter:'F',orientation:'upright',answer:{letter:'P',orientation:'upright'},renderedGeometry:geometry}];
const oldRecord={id:'old',date:'2026-10-09T10:00:00Z',protocolVersion:'spoken-letter-v1',trials:stored,deviceContext:{width:1200,height:800,dpr:1},distanceMethod:'relative-face-scale-only',completed:true};
const newRecord={...oldRecord,id:'new',protocolVersion:V.LETTER_PROTOCOL,methodVersion:V.LETTER_METHOD};const saved=JSON.stringify([oldRecord,newRecord]),series=H.buildHistorySeries('vision',[oldRecord,newRecord]);assert.equal(series.filter(x=>x.criterion==='average').length,2);assert(series.every(x=>x.points.filter(p=>p.value!==null).length===1));assert(series.filter(x=>x.criterion==='average').every(x=>x.points.filter(p=>p.value!==null).every(p=>p.value===50&&!('numerator' in p))));assert.equal(JSON.stringify([oldRecord,newRecord]),saved);
console.log('PASS focused parser, partial ordering/correction, eight transforms, 24 trials, adaptation, geometry inputs, eye-state gate, timestamps, legacy, mouth-independent crop');
"""
 result = subprocess.run(['node','-e',script],cwd=ROOT,input=json.dumps({'dir':str(tmp_path)}),capture_output=True,text=True,encoding='utf8')
 assert result.returncode==0,result.stdout+result.stderr
